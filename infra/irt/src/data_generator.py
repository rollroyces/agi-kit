"""Synthetic ARC-like response matrix generator.

We simulate a (N_solvers, N_items) binary response matrix that mimics
the kind of data we'd see if a population of ARC-AGI solvers attempted
a population of ARC tasks:

    theta_i   ~ N(0, theta_sd)             solver abilities
    a_j       ~ LogNormal(mu_a, sigma_a)   item discriminations (>0)
    b_j       ~ N(mu_b, b_sd)              item difficulties
    c_j       ~ Beta(c_a, c_b)             item guessing (3PL only)
    P_ij      = icc(theta_i, a_j, b_j [, c_j])
    X_ij      ~ Bernoulli(P_ij)
    Then with probability `noise_rate` we flip X_ij to simulate
    mis-clicks, transcription errors, or unstable inference.

The defaults give a wide spread of difficulty (roughly b in [-3, +3])
and discriminations centred near 1 -- so most items are reasonably
informative but a handful are near useless (a close to 0).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .irt_model import icc_2pl, icc_3pl


@dataclass
class SimulationConfig:
    n_solvers: int = 30
    n_items: int = 50
    theta_sd: float = 1.5          # spread of solver abilities
    mu_a: float = 0.0              # log-mean of discriminations
    sigma_a: float = 0.5           # log-sd of discriminations
    mu_b: float = 0.0              # mean difficulty
    b_sd: float = 1.5              # spread of difficulty
    c_a: float = 2.0               # Beta shape 1 for guessing
    c_b: float = 10.0              # Beta shape 2 for guessing
    noise_rate: float = 0.07       # post-hoc response flipping
    seed: int = 20240930


def generate_responses(
    config: SimulationConfig | None = None,
    *,
    model: str = "2pl",
    seed: int | None = None,
):
    """Generate (X, theta_true, a_true, b_true[, c_true]) from a config.

    Parameters
    ----------
    config : SimulationConfig, optional.
    model  : "2pl" (default) or "3pl".
    seed   : override config.seed if given.

    Returns
    -------
    dict with keys: X, theta, a, b, c (None for 2pl), config.
    """
    cfg = config or SimulationConfig()
    if seed is not None:
        cfg = SimulationConfig(**{**cfg.__dict__, "seed": seed})

    rng = np.random.default_rng(cfg.seed)
    theta = rng.normal(0.0, cfg.theta_sd, cfg.n_solvers)
    log_a = rng.normal(cfg.mu_a, cfg.sigma_a, cfg.n_items)
    a = np.exp(log_a)
    b = rng.normal(cfg.mu_b, cfg.b_sd, cfg.n_items)
    c = None
    if model.lower() == "3pl":
        c = rng.beta(cfg.c_a, cfg.c_b, cfg.n_items)

    if c is None:
        P = icc_2pl(theta[:, None], a[None, :], b[None, :])
    else:
        P = icc_3pl(theta[:, None], a[None, :], b[None, :], c[None, :])

    P = np.clip(P, 1e-6, 1.0 - 1e-6)
    X = (rng.uniform(size=P.shape) < P).astype(np.int8)

    if cfg.noise_rate > 0:
        flip = rng.uniform(size=X.shape) < cfg.noise_rate
        X = np.where(flip, 1 - X, X).astype(np.int8)

    return {
        "X": X,
        "theta": theta,
        "a": a,
        "b": b,
        "c": c,
        "config": cfg,
    }


def solver_raw_accuracy(X: np.ndarray) -> np.ndarray:
    """Per-row mean accuracy (length N)."""
    return X.mean(axis=1)


def item_raw_pvalue(X: np.ndarray) -> np.ndarray:
    """Per-column p-value (length J)."""
    return X.mean(axis=0)


__all__ = [
    "SimulationConfig",
    "generate_responses",
    "solver_raw_accuracy",
    "item_raw_pvalue",
]