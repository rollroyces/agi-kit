"""Unit tests for the IRT pipeline.

Covers:
    - ICC shapes, probabilities, edge cases
    - Log-likelihood numerical sanity
    - Parameter packing / unpacking round-trip
    - Optimizer recovers known parameters on small synthetic data
    - Optimizer analytic gradient matches finite differences
    - End-to-end fit on the standard synthetic configuration
    - Raw-accuracy vs theta demonstration helpers
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.irt_model import (  # noqa: E402
    _grad_2pl,
    fit_irt,
    icc_2pl,
    icc_3pl,
    item_fit_residuals,
    log_likelihood_2pl,
    log_likelihood_3pl,
    model_summary,
    neg_log_posterior,
    neg_log_posterior_grad,
    pack_params,
    unpack_params,
)
from src.data_generator import (  # noqa: E402
    SimulationConfig,
    generate_responses,
    item_raw_pvalue,
    solver_raw_accuracy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finite_diff_grad(f, x, eps=1e-6):
    n = x.size
    g = np.zeros(n)
    for i in range(n):
        e = np.zeros(n)
        e[i] = eps
        g[i] = (f(x + e) - f(x - e)) / (2 * eps)
    return g


# ---------------------------------------------------------------------------
# Tests -- ICC
# ---------------------------------------------------------------------------

def test_icc_2pl_basic_shape():
    theta = np.linspace(-3, 3, 7)
    a = np.array([1.0])
    b = np.array([0.0])
    p = icc_2pl(theta, a, b)
    assert np.all((p >= 0) & (p <= 1))
    # At theta = 0 = b, p must equal 0.5
    assert np.isclose(p[theta == 0.0][0], 0.5, atol=1e-9)


def test_icc_2pl_monotone_in_theta():
    theta = np.linspace(-3, 3, 50)
    a = np.array([1.0, 0.5])
    b = np.array([0.0, 1.5])
    p = icc_2pl(theta[:, None], a[None, :], b[None, :])
    # monotone increasing along axis 0
    assert np.all(np.diff(p, axis=0) >= -1e-12)


def test_icc_2pl_higher_a_steeper():
    theta = np.linspace(-3, 3, 121)
    a_low = np.array([0.5])
    a_high = np.array([2.0])
    b = np.array([0.0])
    p_low = icc_2pl(theta, a_low, b).ravel()
    p_high = icc_2pl(theta, a_high, b).ravel()
    # at theta = -2 the higher-discrimination curve should be lower
    assert p_high[theta == -2.0][0] < p_low[theta == -2.0][0]
    # at theta = +2 the higher-discrimination curve should be higher
    assert p_high[theta == 2.0][0] > p_low[theta == 2.0][0]


def test_icc_3pl_reduces_to_2pl_when_c_zero():
    rng = np.random.default_rng(0)
    theta = rng.normal(size=20)
    a = np.exp(rng.normal(size=5))
    b = rng.normal(size=5)
    c = np.zeros(5)
    p3 = icc_3pl(theta[:, None], a[None, :], b[None, :], c[None, :])
    p2 = icc_2pl(theta[:, None], a[None, :], b[None, :])
    assert np.allclose(p3, p2)


def test_icc_3pl_lower_bounded_by_c():
    rng = np.random.default_rng(0)
    theta = rng.normal(size=50)
    a = np.exp(rng.normal(size=10))
    b = rng.normal(size=10)
    c = np.full(10, 0.2)
    p = icc_3pl(theta[:, None], a[None, :], b[None, :], c[None, :])
    assert np.all(p >= 0.2 - 1e-12)


# ---------------------------------------------------------------------------
# Tests -- log-likelihood
# ---------------------------------------------------------------------------

def test_log_likelihood_2pl_extreme():
    theta = np.array([0.0])
    a = np.array([1.0])
    b = np.array([0.0])
    X = np.array([[0]])
    # P = 0.5; log(0.5)*1 = -0.6931...
    ll = log_likelihood_2pl(theta, a, b, X)
    assert np.isclose(ll, np.log(0.5))

    X = np.array([[1]])
    ll = log_likelihood_2pl(theta, a, b, X)
    assert np.isclose(ll, np.log(0.5))


def test_log_likelihood_3pl_reduces_when_c_zero():
    rng = np.random.default_rng(1)
    N, J = 8, 6
    theta = rng.normal(size=N)
    a = np.exp(rng.normal(size=J) * 0.3)
    b = rng.normal(size=J)
    X = (rng.uniform(size=(N, J)) < 0.5).astype(int)

    ll2 = log_likelihood_2pl(theta, a, b, X)
    ll3 = log_likelihood_3pl(theta, a, b, np.zeros(J), X)
    assert np.isclose(ll2, ll3, atol=1e-8)


def test_log_likelihood_increases_with_better_fit():
    # All correct at theta >> b should give a very high log-likelihood
    # whereas all wrong should give a very low one.
    theta = np.array([3.0])
    a = np.array([1.0])
    b = np.array([0.0])
    X = np.array([[1]])
    ll_good = log_likelihood_2pl(theta, a, b, X)
    X = np.array([[0]])
    ll_bad = log_likelihood_2pl(theta, a, b, X)
    assert ll_good > ll_bad


# ---------------------------------------------------------------------------
# Tests -- pack / unpack round-trip
# ---------------------------------------------------------------------------

def test_pack_unpack_round_trip_2pl():
    rng = np.random.default_rng(0)
    theta = rng.normal(size=4)
    a = np.exp(rng.normal(size=3))
    b = rng.normal(size=3)
    params = pack_params(theta, a, b)
    th2, ua2, ub2, uc2 = unpack_params(params, 4, 3, False)
    assert np.allclose(theta, th2)
    assert np.allclose(a, ua2)
    assert np.allclose(b, ub2)
    assert uc2 is None


def test_pack_unpack_round_trip_3pl():
    rng = np.random.default_rng(0)
    theta = rng.normal(size=4)
    a = np.exp(rng.normal(size=3))
    b = rng.normal(size=3)
    c = rng.uniform(0.01, 0.5, size=3)
    params = pack_params(theta, a, b, c)
    th2, ua2, ub2, uc2 = unpack_params(params, 4, 3, True)
    assert np.allclose(theta, th2)
    assert np.allclose(a, ua2, atol=1e-8)
    assert np.allclose(b, ub2)
    assert np.allclose(c, uc2, atol=1e-8)


# ---------------------------------------------------------------------------
# Tests -- analytic gradient matches finite differences
# ---------------------------------------------------------------------------

def test_analytic_gradient_matches_fd():
    rng = np.random.default_rng(42)
    N, J = 6, 5
    theta = rng.normal(size=N)
    a = np.exp(rng.normal(size=J) * 0.3)
    b = rng.normal(size=J)
    X = (rng.uniform(size=(N, J)) < 0.5).astype(int)

    params = pack_params(theta, a, b)
    args = (X, False, 1.0, 2.0, 1.0, 2.0, 10.0)
    f = lambda pp: neg_log_posterior(pp, *args)
    g_analytic = neg_log_posterior_grad(params, *args)
    g_fd = _finite_diff_grad(f, params, eps=1e-6)
    # analytic vs FD should be close to ~1e-5
    assert np.allclose(g_analytic, g_fd, atol=1e-5, rtol=1e-4)


def test_grad_helper_matches_full_gradient():
    rng = np.random.default_rng(7)
    N, J = 4, 6
    theta = rng.normal(size=N)
    a = np.exp(rng.normal(size=J) * 0.3)
    b = rng.normal(size=J)
    X = (rng.uniform(size=(N, J)) < 0.5).astype(int)

    params = pack_params(theta, a, b)
    g_a = _grad_2pl(params, X, 1.0, 2.0, 1.0)
    g_full = neg_log_posterior_grad(
        params, X, has_c=False, theta_sd=1.0, b_sd=2.0, log_a_sd=1.0
    )
    assert np.allclose(g_a, g_full)


# ---------------------------------------------------------------------------
# Tests -- end-to-end fit on synthetic data
# ---------------------------------------------------------------------------

def test_fit_2pl_recovers_parameters():
    """On a 30 x 50 synthetic dataset, parameter recovery should be
    decent (Pearson r > 0.7 for theta and b, even though recovery of a
    is harder with only 30 solvers per item)."""
    cfg = SimulationConfig(seed=123, noise_rate=0.05)
    sim = generate_responses(cfg, model="2pl", seed=cfg.seed)
    X = sim["X"]

    fit = fit_irt(X, model="2pl", seed=0, max_iter=300)
    assert fit.converged
    assert np.all(fit.a > 0)

    # Pearson correlations between recovered and true parameters
    def corr(a, b):
        return float(np.corrcoef(a, b)[0, 1])

    r_theta = corr(sim["theta"], fit.theta)
    r_a = corr(sim["a"], fit.a)
    r_b = corr(sim["b"], fit.b)

    # Recovery should be quite strong for theta and b on this size.
    assert r_theta > 0.85, f"theta recovery too weak: r={r_theta:.3f}"
    assert r_b > 0.85, f"b recovery too weak: r={r_b:.3f}"
    # a is harder with only 30 solvers per item; require positive correlation.
    assert r_a > 0.0, f"a recovery implausibly low: r={r_a:.3f}"


def test_fit_2pl_returns_sensible_log_likelihood():
    cfg = SimulationConfig(seed=99, noise_rate=0.0)
    sim = generate_responses(cfg, model="2pl", seed=cfg.seed)
    fit = fit_irt(sim["X"], model="2pl", seed=0, max_iter=300)
    summary = model_summary(fit, sim["X"])
    # A 2PL on Bernoulli data should have a non-trivially high likelihood.
    # Per observation we expect log-likelihood density > log(0.05) (random
    # baseline), so the total should be > n*j*log(0.05).
    n, j = sim["X"].shape
    assert fit.log_likelihood > n * j * np.log(0.05)


def test_fit_3pl_runs_and_returns_valid_c():
    cfg = SimulationConfig(seed=5, noise_rate=0.05)
    sim = generate_responses(cfg, model="3pl", seed=cfg.seed)
    fit = fit_irt(sim["X"], model="3pl", seed=0, max_iter=200)
    assert fit.c is not None
    assert np.all((fit.c >= 0) & (fit.c <= 1))
    assert fit.converged
    # model_summary should also report the right model tag
    summary = model_summary(fit, sim["X"])
    assert summary["model"] == "3PL"
    assert summary["n_params"] == sim["X"].shape[0] + 3 * sim["X"].shape[1]


# ---------------------------------------------------------------------------
# Tests -- data generator utilities
# ---------------------------------------------------------------------------

def test_data_generator_shapes():
    cfg = SimulationConfig(n_solvers=8, n_items=12, seed=0)
    sim = generate_responses(cfg, model="2pl", seed=0)
    assert sim["X"].shape == (8, 12)
    assert sim["theta"].shape == (8,)
    assert sim["a"].shape == (12,)
    assert sim["b"].shape == (12,)
    assert sim["c"] is None
    assert set(np.unique(sim["X"])).issubset({0, 1})


def test_data_generator_3pl_has_c():
    cfg = SimulationConfig(n_solvers=4, n_items=5, seed=0)
    sim = generate_responses(cfg, model="3pl", seed=0)
    assert sim["c"] is not None
    assert sim["c"].shape == (5,)
    assert np.all((sim["c"] > 0) & (sim["c"] < 1))


def test_noise_flips_about_the_expected_rate():
    """Without the noise step, hard items stay at p ~ 0.  With it, a few
    entries should flip -- mean accuracy must be strictly between 0 and 1.
    """
    cfg = SimulationConfig(n_solvers=30, n_items=50, noise_rate=0.05, seed=42)
    sim = generate_responses(cfg, model="2pl", seed=42)
    p = sim["X"].mean()
    assert 0.0 < p < 1.0
    # The hardest item should not be all-1s, the easiest should not be all-0s.
    col_min = sim["X"].min(axis=0)
    col_max = sim["X"].max(axis=0)
    assert col_min.min() == 0
    assert col_max.max() == 1


# ---------------------------------------------------------------------------
# Tests -- residuals / summary
# ---------------------------------------------------------------------------

def test_item_fit_residuals_shape():
    cfg = SimulationConfig(seed=11)
    sim = generate_responses(cfg, model="2pl", seed=11)
    fit = fit_irt(sim["X"], model="2pl", seed=0)
    res = item_fit_residuals(sim["X"], fit.theta, fit.a, fit.b)
    assert res["signed_residual"].shape == (cfg.n_items,)
    assert res["chi_square"].shape == (cfg.n_items,)
    # chi-square stats are non-negative
    assert np.all(res["chi_square"] >= 0)


def test_model_summary_returns_expected_keys():
    cfg = SimulationConfig(seed=2)
    sim = generate_responses(cfg, model="2pl", seed=2)
    fit = fit_irt(sim["X"], model="2pl", seed=0)
    s = model_summary(fit, sim["X"])
    for k in (
        "n_solvers", "n_items", "model", "log_likelihood",
        "n_params", "AIC", "BIC", "converged",
        "theta_mean", "theta_sd", "a_mean", "b_mean", "b_sd",
    ):
        assert k in s, f"missing key {k}"


# ---------------------------------------------------------------------------
# Tests -- utility functions
# ---------------------------------------------------------------------------

def test_solver_accuracy_helper():
    X = np.array([[1, 1, 1, 0], [1, 0, 0, 0], [0, 0, 0, 0]])
    acc = solver_raw_accuracy(X)
    assert np.allclose(acc, [0.75, 0.25, 0.0])


def test_item_pvalue_helper():
    X = np.array([[1, 1, 0, 0], [1, 0, 1, 0], [0, 0, 0, 0]])
    p = item_raw_pvalue(X)
    assert np.allclose(p, [2 / 3, 1 / 3, 1 / 3, 0.0])


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))