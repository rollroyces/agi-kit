"""IRT model: 2PL (default) and 3PL, with joint MAP estimation.

The 2PL Item Response Theory model assumes that for solver i with ability
theta_i and task j with discrimination a_j and difficulty b_j, the
probability of a correct response is

    P(X_ij = 1 | theta_i, a_j, b_j) = sigmoid(a_j * (theta_i - b_j))

The 3PL adds a guessing parameter c_j in [0, 1):

    P = c_j + (1 - c_j) * sigmoid(a_j * (theta_i - b_j))

We estimate (theta_1..theta_N, a_1..a_J, b_1..b_J, [c_1..c_J]) by joint
maximum a posteriori (MAP) estimation with Gaussian priors on theta and b
and a log-normal prior on a (so a > 0).  For 3PL we add a weakly
informative Beta(2, 10) prior on c (encouraging small guessing, which
matches ARC's open-ended answer format where blind guessing is hard).

Identification:
    - Location is fixed by the standard-normal prior on theta.
    - Scale is fixed by the N(0, 1) prior on log(a) (median a = 1).

Numerical notes:
    - log(1 + exp(z)) is computed with np.logaddexp(0, z).
    - a is reparametrised as log a; c (for 3PL) as logit c, so the
      unbounded parameter vector is what the optimiser sees.
    - For 2PL we use an analytic gradient (fast, exact).
    - For 3PL we use scipy's finite-difference gradient -- analytic 3PL
      gradients are correct but error-prone; FD is more than fast enough
      for our matrix sizes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit as _slogit


# ---------------------------------------------------------------------------
# Item characteristic curves (ICCs) -- pure probability / expected score
# ---------------------------------------------------------------------------

def icc_2pl(theta, a, b):
    """2PL ICC.  Broadcasts over leading axes.

    P(X=1 | theta, a, b) = sigmoid(a (theta - b))
    """
    z = np.multiply(a, np.subtract(theta, b))
    return expit(z)


def icc_3pl(theta, a, b, c):
    """3PL ICC: P = c + (1 - c) * sigmoid(a (theta - b))."""
    p2 = icc_2pl(theta, a, b)
    return c + (1.0 - c) * p2


# ---------------------------------------------------------------------------
# Log-likelihood for a fully observed response matrix
# ---------------------------------------------------------------------------

def log_likelihood_2pl(theta, a, b, X):
    """Sum of per-observation log-likelihoods under 2PL.

    X is shape (N, J) binary.  Returns a scalar (sum, not mean).
    """
    z = a[None, :] * (theta[:, None] - b[None, :])  # (N, J)
    log_p = -np.logaddexp(0.0, -z)
    log_1mp = -np.logaddexp(0.0, z)
    return float((X * log_p + (1.0 - X) * log_1mp).sum())


def log_likelihood_3pl(theta, a, b, c, X):
    z = a[None, :] * (theta[:, None] - b[None, :])
    p2 = expit(z)
    p_obs = c[None, :] + (1.0 - c[None, :]) * p2
    p_obs = np.clip(p_obs, 1e-12, 1.0 - 1e-12)
    return float((X * np.log(p_obs) + (1.0 - X) * np.log(1.0 - p_obs)).sum())


# ---------------------------------------------------------------------------
# Parameter packing / unpacking for joint optimisation
# ---------------------------------------------------------------------------

def pack_params(theta, a, b, c=None):
    """Concatenate free-form parameters into a single vector.

    a is stored as log a; c (if given) is stored as logit c.
    """
    parts = [theta, np.log(a), b]
    if c is not None:
        parts.append(_slogit(np.clip(c, 1e-6, 1.0 - 1e-6)))
    return np.concatenate(parts)


def unpack_params(params, n_solvers, n_items, has_c):
    theta = params[:n_solvers]
    log_a = params[n_solvers:n_solvers + n_items]
    a = np.exp(log_a)
    b = params[n_solvers + n_items:n_solvers + 2 * n_items]
    c = None
    if has_c:
        c = expit(params[n_solvers + 2 * n_items:])
    return theta, a, b, c


# ---------------------------------------------------------------------------
# Joint MAP objective (negative log posterior)
# ---------------------------------------------------------------------------

def neg_log_posterior(
    params,
    X,
    has_c=False,
    theta_sd=1.0,
    b_sd=2.0,
    log_a_sd=1.0,
    c_prior_a=2.0,
    c_prior_b=10.0,
):
    """Negative log posterior (dropping additive constants)."""
    n_solvers, n_items = X.shape
    theta, a, b, c = unpack_params(params, n_solvers, n_items, has_c)

    # ---- likelihood ----
    z = a[None, :] * (theta[:, None] - b[None, :])
    if has_c:
        p2 = expit(z)
        p_obs = c[None, :] + (1.0 - c[None, :]) * p2
        p_obs = np.clip(p_obs, 1e-12, 1.0 - 1e-12)
        ll = X * np.log(p_obs) + (1.0 - X) * np.log(1.0 - p_obs)
    else:
        log_p = -np.logaddexp(0.0, -z)
        log_1mp = -np.logaddexp(0.0, z)
        ll = X * log_p + (1.0 - X) * log_1mp
    nll = -float(ll.sum())

    # ---- priors (Gaussian on theta / b, log-normal on a, Beta on c) ----
    prior = 0.5 * np.sum((theta / theta_sd) ** 2)         # N(0, theta_sd^2)
    log_a = np.log(a)
    prior += 0.5 * np.sum((log_a / log_a_sd) ** 2)        # log a ~ N(0, log_a_sd^2)
    prior += 0.5 * np.sum((b / b_sd) ** 2)                # N(0, b_sd^2)
    if has_c:
        c_clip = np.clip(c, 1e-6, 1.0 - 1e-6)
        prior -= (c_prior_a - 1.0) * np.sum(np.log(c_clip)) \
               + (c_prior_b - 1.0) * np.sum(np.log(1.0 - c_clip))

    return nll + prior


def _grad_2pl(params, X, theta_sd, b_sd, log_a_sd):
    """Analytic gradient of neg_log_posterior for the 2PL case."""
    n_solvers, n_items = X.shape
    theta = params[:n_solvers]
    log_a = params[n_solvers:n_solvers + n_items]
    a = np.exp(log_a)
    b = params[n_solvers + n_items:n_solvers + 2 * n_items]

    z = a[None, :] * (theta[:, None] - b[None, :])  # (N, J)
    p2 = expit(z)
    r = X - p2                                          # (N, J) residual

    # d nll / d theta_i = - sum_j a_j * r_ij
    g_theta = -(a[None, :] * r).sum(axis=1)
    # d nll / d log a_j = a_j * (d nll / d a_j)
    # d nll / d a_j    = - sum_i (theta_i - b_j) * r_ij
    g_log_a = -(a[None, :] * (theta[:, None] - b[None, :]) * r).sum(axis=0)
    # d nll / d b_j = sum_i a_j * r_ij
    g_b = (a[None, :] * r).sum(axis=0)

    # ---- priors ----
    g_theta = g_theta + theta / (theta_sd ** 2)
    g_log_a = g_log_a + log_a / (log_a_sd ** 2)
    g_b = g_b + b / (b_sd ** 2)

    return np.concatenate([g_theta, g_log_a, g_b])


def neg_log_posterior_grad(
    params,
    X,
    has_c=False,
    theta_sd=1.0,
    b_sd=2.0,
    log_a_sd=1.0,
    c_prior_a=2.0,
    c_prior_b=10.0,
):
    """Gradient of neg_log_posterior.

    For 2PL we return the analytic gradient; for 3PL we return None so
    that L-BFGS-B falls back to finite differences (still fast at our
    matrix sizes).
    """
    if has_c:
        return None
    return _grad_2pl(params, X, theta_sd, b_sd, log_a_sd)


# ---------------------------------------------------------------------------
# Fitter -- joint MAP via L-BFGS-B
# ---------------------------------------------------------------------------

@dataclass
class IRTFitResult:
    """Container for a fitted IRT model.

    Attributes
    ----------
    theta   : (N,) solver abilities.
    a       : (J,) item discriminations.
    b       : (J,) item difficulties.
    c       : (J,) item guessing (3PL only) or None.
    log_likelihood : joint log-likelihood at the MAP.
    n_params       : effective parameter count.
    converged      : did the optimiser report success?
    n_iters        : iterations reported by the optimiser.
    """

    theta: np.ndarray
    a: np.ndarray
    b: np.ndarray
    c: np.ndarray | None
    log_likelihood: float
    n_params: int
    converged: bool
    n_iters: int

    def item_table(self):
        rows = []
        for j in range(len(self.a)):
            row = {"item": j, "a": float(self.a[j]), "b": float(self.b[j])}
            if self.c is not None:
                row["c"] = float(self.c[j])
            rows.append(row)
        return rows

    def solver_table(self):
        return [
            {"solver": i, "theta": float(th)} for i, th in enumerate(self.theta)
        ]


def fit_irt(
    X,
    *,
    model="2pl",
    max_iter=500,
    seed=0,
    theta_sd=1.0,
    b_sd=2.0,
    log_a_sd=1.0,
):
    """Fit a 2PL or 3PL IRT model to a binary response matrix X (N, J).

    Parameters
    ----------
    X       : (N, J) 0/1 array of observed responses.
    model   : "2pl" (default) or "3pl".
    max_iter: L-BFGS-B iteration cap.
    seed    : RNG seed for the initial parameter draw.
    theta_sd, b_sd, log_a_sd : prior standard deviations.
    """
    has_c = str(model).lower() == "3pl"
    n_solvers, n_items = X.shape

    rng = np.random.default_rng(seed)

    # ---- sensible initialisation ----
    #   theta_i  ~ 0
    #   b_j from item p-value (probit-transformed), so the ICC is in
    #   roughly the right place at start.
    #   a_j     = 1  (i.e. log a = 0)
    #   c_j     = 0.1 for 3PL
    col_means = np.clip(X.mean(axis=0), 0.05, 0.95)
    from scipy.special import erfinv
    b_j0 = -np.sqrt(2.0) * erfinv(2.0 * col_means - 1.0)
    theta0 = np.zeros(n_solvers)
    log_a0 = np.zeros(n_items)
    if has_c:
        c0 = np.full(n_items, 0.1)
        params0 = pack_params(theta0, np.exp(log_a0), b_j0, c0)
    else:
        params0 = pack_params(theta0, np.exp(log_a0), b_j0)

    # tiny jitter breaks ties that confuse L-BFGS-B
    params0 = params0 + 1e-3 * rng.standard_normal(params0.size)

    args = (X, has_c, theta_sd, b_sd, log_a_sd, 2.0, 10.0)

    jac = neg_log_posterior_grad if not has_c else None
    result = minimize(
        neg_log_posterior,
        params0,
        args=args,
        jac=jac,
        method="L-BFGS-B",
        options={"maxiter": max_iter, "gtol": 1e-6, "ftol": 1e-9, "maxfun": 20000},
    )

    theta, a, b, c = unpack_params(result.x, n_solvers, n_items, has_c)
    if has_c:
        ll = log_likelihood_3pl(theta, a, b, c, X)
        n_params = n_solvers + 3 * n_items
    else:
        ll = log_likelihood_2pl(theta, a, b, X)
        n_params = n_solvers + 2 * n_items

    return IRTFitResult(
        theta=theta,
        a=a,
        b=b,
        c=c,
        log_likelihood=ll,
        n_params=n_params,
        converged=bool(result.success),
        n_iters=int(result.nit),
    )


# ---------------------------------------------------------------------------
# Diagnostic helpers
# ---------------------------------------------------------------------------

def item_fit_residuals(X, theta, a, b, c=None):
    """Per-item (signed and chi-square) residuals.

    For each item j we compute expected scores for every solver, then
    sum (X - P)^2 / (P (1 - P)) over solvers.  Smaller is better; values
    much larger than 1 indicate misfit.
    """
    if c is None:
        p = icc_2pl(theta[:, None], a[None, :], b[None, :])
    else:
        p = icc_3pl(theta[:, None], a[None, :], b[None, :], c[None, :])
    p = np.clip(p, 1e-6, 1.0 - 1e-6)
    signed = (X - p).mean(axis=0)
    chi2 = ((X - p) ** 2 / (p * (1.0 - p))).sum(axis=0)
    return {"signed_residual": signed, "chi_square": chi2}


def model_summary(fit, X):
    """Quick text-friendly summary of fit quality."""
    n, j = X.shape
    aic = 2 * fit.n_params - 2 * fit.log_likelihood
    bic = fit.n_params * np.log(n * j) - 2 * fit.log_likelihood
    return {
        "n_solvers": n,
        "n_items": j,
        "model": "3PL" if fit.c is not None else "2PL",
        "log_likelihood": fit.log_likelihood,
        "n_params": fit.n_params,
        "AIC": aic,
        "BIC": bic,
        "converged": fit.converged,
        "n_iters": fit.n_iters,
        "theta_mean": float(fit.theta.mean()),
        "theta_sd": float(fit.theta.std(ddof=1)),
        "a_mean": float(fit.a.mean()),
        "b_mean": float(fit.b.mean()),
        "b_sd": float(fit.b.std(ddof=1)),
    }


__all__ = [
    "icc_2pl",
    "icc_3pl",
    "log_likelihood_2pl",
    "log_likelihood_3pl",
    "pack_params",
    "unpack_params",
    "neg_log_posterior",
    "neg_log_posterior_grad",
    "fit_irt",
    "IRTFitResult",
    "item_fit_residuals",
    "model_summary",
]