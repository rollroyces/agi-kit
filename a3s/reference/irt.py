"""A3S §9 — Reporting: IRT 2PL/3PL wrapper.

Wraps :func:`02-irt.src.irt_model.fit_irt` and exposes the §9 ``irt``
section: ``theta``, ``theta_ci95``, ``model``, ``n_solvers``, ``n_items``.

Usage::

    from reference.irt import fit_irt_report, CI95

    import numpy as np
    X = np.random.RandomState(0).randint(0, 2, size=(20, 10))
    report = fit_irt_report(X, model="2pl")
    print(report["theta"], report["theta_ci95"])
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any, Dict, Optional

import numpy as np

_THIS = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.abspath(os.path.join(_THIS, "..", ".."))

import importlib.util as _ilu  # noqa: E402
_IRT_PATH = os.path.join(_PROJECT, "02-irt", "src", "irt_model.py")
_spec = _ilu.spec_from_file_location("_a3s_inner_irt_model", _IRT_PATH)
_inner = _ilu.module_from_spec(_spec)
sys.modules["_a3s_inner_irt_model"] = _inner   # dataclass needs this
_spec.loader.exec_module(_inner)
fit_irt       = _inner.fit_irt
model_summary = _inner.model_summary


def _normal_ci95(mean: float, sd: float, n: int) -> tuple:
    """Wald-style 95% CI: mean ± 1.96 * sd / sqrt(n)."""
    if n <= 1 or not math.isfinite(sd) or sd == 0.0:
        return (float(mean), float(mean))
    half = 1.959963984540054 * sd / math.sqrt(n)
    return (float(mean - half), float(mean + half))


def fit_irt_report(X: np.ndarray,
                   *,
                   model: str = "2pl",
                   seed: int = 0,
                   max_iter: int = 500) -> Dict[str, Any]:
    """Fit IRT on a binary response matrix and emit the §9 ``irt`` block."""
    fit = fit_irt(X, model=model, seed=seed, max_iter=max_iter)
    summary = model_summary(fit, X)
    n_solvers = int(summary["n_solvers"])
    theta_sd = float(summary["theta_sd"])
    theta_mean = float(summary["theta_mean"])
    lo, hi = _normal_ci95(theta_mean, theta_sd, n_solvers)

    return {
        "model":      summary["model"],
        "theta":      theta_mean,
        "theta_ci95": [lo, hi],
        "theta_sd":   theta_sd,
        "n_solvers":  n_solvers,
        "n_items":    int(summary["n_items"]),
        "converged":  bool(summary["converged"]),
        "n_iters":    int(summary["n_iters"]),
        "log_likelihood": float(summary["log_likelihood"]),
        "AIC":        float(summary["AIC"]),
        "BIC":        float(summary["BIC"]),
    }


def CI95(mean: float, sd: float, n: int) -> tuple:
    """Public alias for the Wald-CI helper (used by reporting tests)."""
    return _normal_ci95(mean, sd, n)


# --- usage example -----------------------------------------------------------

if __name__ == "__main__":
    rng = np.random.default_rng(0)
    # Synthetic 2PL data: 20 solvers x 15 items with moderate discrimination.
    X = (rng.uniform(size=(20, 15)) < 0.5).astype(int)
    r = fit_irt_report(X, model="2pl")
    assert r["model"] == "2PL"
    assert isinstance(r["theta_ci95"], list) and len(r["theta_ci95"]) == 2
    print(f"irt.py: theta={r['theta']:.3f} ci95={r['theta_ci95']} "
          f"converged={r['converged']}")
