"""High-level fitter helpers used by the pipeline driver."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data_generator import solver_raw_accuracy
from .irt_model import (
    fit_irt,
    item_fit_residuals,
    model_summary,
)


def fit_synthetic(
    X: np.ndarray,
    *,
    model: str = "2pl",
    seed: int = 0,
    max_iter: int = 500,
):
    """Fit an IRT model and return (fit, residuals, summary)."""
    fit = fit_irt(X, model=model, seed=seed, max_iter=max_iter)
    residuals = item_fit_residuals(X, fit.theta, fit.a, fit.b, fit.c)
    summary = model_summary(fit, X)
    return fit, residuals, summary


def solver_dataframe(fit, X) -> pd.DataFrame:
    """Per-solver table: id, raw accuracy, theta."""
    raw = solver_raw_accuracy(X)
    return pd.DataFrame(
        {
            "solver": np.arange(len(fit.theta)),
            "raw_accuracy": raw,
            "theta": fit.theta,
        }
    )


def item_dataframe(fit) -> pd.DataFrame:
    """Per-item table: id, discrimination a, difficulty b, [c]."""
    rows = {
        "item": np.arange(len(fit.a)),
        "a": fit.a,
        "b": fit.b,
    }
    if fit.c is not None:
        rows["c"] = fit.c
    return pd.DataFrame(rows)


def save_artifacts(
    out_dir: Path,
    *,
    fit,
    residuals,
    summary,
    X: np.ndarray,
    true_params: dict | None = None,
):
    """Write CSV / JSON / TXT artifacts into ``out_dir`` (created if missing)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    solvers = solver_dataframe(fit, X)
    items = item_dataframe(fit)
    if true_params is not None:
        items = items.assign(
            a_true=true_params.get("a"),
            b_true=true_params.get("b"),
        )
        solvers = solvers.assign(theta_true=true_params.get("theta"))

    solvers.to_csv(out_dir / "solver_abilities.csv", index=False)
    items.to_csv(out_dir / "item_parameters.csv", index=False)

    residuals_df = pd.DataFrame(
        {
            "item": np.arange(len(fit.a)),
            "signed_residual": residuals["signed_residual"],
            "chi_square": residuals["chi_square"],
        }
    )
    residuals_df.to_csv(out_dir / "item_fit_residuals.csv", index=False)

    # JSON summary
    (out_dir / "model_fit_summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2)
    )

    # Human-readable TXT
    txt_lines = [
        f"IRT {summary['model']} fit summary",
        "=" * 40,
        f"solvers          : {summary['n_solvers']}",
        f"items            : {summary['n_items']}",
        f"converged        : {summary['converged']}",
        f"iterations       : {summary['n_iters']}",
        f"log-likelihood   : {summary['log_likelihood']:.4f}",
        f"n_parameters     : {summary['n_params']}",
        f"AIC              : {summary['AIC']:.2f}",
        f"BIC              : {summary['BIC']:.2f}",
        f"theta mean (sd)  : {summary['theta_mean']:.3f} ({summary['theta_sd']:.3f})",
        f"a mean           : {summary['a_mean']:.3f}",
        f"b mean (sd)      : {summary['b_mean']:.3f} ({summary['b_sd']:.3f})",
    ]
    (out_dir / "model_fit_summary.txt").write_text("\n".join(txt_lines) + "\n")


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


__all__ = [
    "fit_synthetic",
    "solver_dataframe",
    "item_dataframe",
    "save_artifacts",
]