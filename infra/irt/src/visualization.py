"""Plots for the IRT calibration pipeline."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display
import matplotlib.pyplot as plt
import numpy as np

from .irt_model import icc_2pl, icc_3pl


def _save(fig, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    return path


def plot_icc_curves(fit, *, items=None, theta_grid=None, out_path: Path):
    """Item characteristic curves for 4-6 representative items.

    Picks items that span the difficulty range (lowest, median, highest
    b) and include a mix of discriminations so the figure shows slope
    variation as well.
    """
    j = np.arange(len(fit.a))
    if items is None:
        order = np.argsort(fit.b)
        picks = []
        for frac in (0.05, 0.30, 0.50, 0.70, 0.95):
            picks.append(order[int(frac * (len(order) - 1))])
        # de-dup while preserving order
        seen, items = set(), []
        for p in picks:
            if p not in seen:
                seen.add(p)
                items.append(int(p))
        items = items[:6]

    if theta_grid is None:
        theta_grid = np.linspace(-3.5, 3.5, 401)

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    for jj in items:
        if fit.c is None:
            p = icc_2pl(theta_grid, fit.a[jj], fit.b[jj])
        else:
            p = icc_3pl(theta_grid, fit.a[jj], fit.b[jj], fit.c[jj])
        ax.plot(theta_grid, p, label=f"item {jj}: a={fit.a[jj]:.2f}, b={fit.b[jj]:+.2f}")
    ax.set_xlabel("solver ability  $\\theta$")
    ax.set_ylabel("P(correct)")
    ax.set_title("Item characteristic curves (2PL)")
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlim(theta_grid[0], theta_grid[-1])
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9, loc="lower right")
    return _save(fig, out_path)


def plot_ability_histogram(fit, *, out_path: Path, bins: int = 12):
    """Histogram of solver ability estimates with N(0,1) overlay."""
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.hist(fit.theta, bins=bins, density=True, alpha=0.7,
            color="#3a76a8", edgecolor="white", label="estimated $\\hat{\\theta}$")
    grid = np.linspace(-4, 4, 400)
    ax.plot(grid, np.exp(-0.5 * grid ** 2) / np.sqrt(2 * np.pi),
            color="#222", lw=1.5, ls="--", label="N(0, 1) prior")
    ax.set_xlabel("ability  $\\theta$")
    ax.set_ylabel("density")
    ax.set_title("Distribution of solver abilities")
    ax.legend()
    ax.grid(alpha=0.3)
    return _save(fig, out_path)


def plot_accuracy_vs_theta(solvers, *, pairs=None, out_path: Path):
    """Scatter of raw accuracy vs theta; highlights same-accuracy pairs."""
    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    ax.scatter(solvers["theta"], solvers["raw_accuracy"],
               s=42, alpha=0.75, color="#3a76a8", edgecolor="white")
    ax.set_xlabel("IRT ability  $\\hat{\\theta}$")
    ax.set_ylabel("raw accuracy")
    ax.set_title("Raw accuracy vs IRT ability")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.3)

    if pairs:
        for i, j in pairs:
            xi, xj = solvers.loc[i, "theta"], solvers.loc[j, "theta"]
            yi, yj = solvers.loc[i, "raw_accuracy"], solvers.loc[j, "raw_accuracy"]
            ax.plot([xi, xj], [yi, yj], color="#c0392b", lw=1.2, zorder=1)
            ax.annotate(
                f"s{i}",
                xy=(xi, yi),
                xytext=(6, 6),
                textcoords="offset points",
                fontsize=9,
                color="#c0392b",
            )
            ax.annotate(
                f"s{j}",
                xy=(xj, yj),
                xytext=(6, 6),
                textcoords="offset points",
                fontsize=9,
                color="#c0392b",
            )

    # light identity-trend overlay: loess-ish smoothing via moving average
    order = np.argsort(solvers["theta"].values)
    th_sorted = solvers["theta"].values[order]
    acc_sorted = solvers["raw_accuracy"].values[order]
    win = max(3, len(th_sorted) // 8)
    if len(th_sorted) > win:
        kernel = np.ones(win) / win
        smooth = np.convolve(acc_sorted, kernel, mode="same")
        ax.plot(th_sorted, smooth, color="#222", lw=1.2, ls="--",
                label="moving-avg trend")
        ax.legend()

    return _save(fig, out_path)


def plot_true_vs_estimated(true_params, fit, *, out_path: Path):
    """Scatter of true vs estimated theta / a / b for sanity."""
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.0))

    axes[0].scatter(true_params["theta"], fit.theta, s=30, alpha=0.7,
                    color="#3a76a8", edgecolor="white")
    lo = min(true_params["theta"].min(), fit.theta.min())
    hi = max(true_params["theta"].max(), fit.theta.max())
    axes[0].plot([lo, hi], [lo, hi], color="#c0392b", lw=1, ls="--")
    axes[0].set_xlabel("true $\\theta$"); axes[0].set_ylabel("est. $\\hat{\\theta}$")
    axes[0].set_title("Solver ability recovery")
    axes[0].grid(alpha=0.3)

    axes[1].scatter(true_params["a"], fit.a, s=30, alpha=0.7,
                    color="#3a76a8", edgecolor="white")
    lo = min(true_params["a"].min(), fit.a.min())
    hi = max(true_params["a"].max(), fit.a.max())
    axes[1].plot([lo, hi], [lo, hi], color="#c0392b", lw=1, ls="--")
    axes[1].set_xlabel("true $a$"); axes[1].set_ylabel("est. $\\hat{a}$")
    axes[1].set_title("Discrimination recovery")
    axes[1].grid(alpha=0.3)

    axes[2].scatter(true_params["b"], fit.b, s=30, alpha=0.7,
                    color="#3a76a8", edgecolor="white")
    lo = min(true_params["b"].min(), fit.b.min())
    hi = max(true_params["b"].max(), fit.b.max())
    axes[2].plot([lo, hi], [lo, hi], color="#c0392b", lw=1, ls="--")
    axes[2].set_xlabel("true $b$"); axes[2].set_ylabel("est. $\\hat{b}$")
    axes[2].set_title("Difficulty recovery")
    axes[2].grid(alpha=0.3)

    fig.suptitle("Parameter recovery (true vs estimated)", y=1.02)
    return _save(fig, out_path)


__all__ = [
    "plot_icc_curves",
    "plot_ability_histogram",
    "plot_accuracy_vs_theta",
    "plot_true_vs_estimated",
]