# IRT Calibration Pipeline — ARC AGI Enhancement (Sub-project 02)

A self-contained pipeline that demonstrates **Item Response Theory (IRT)**
calibration on ARC-AGI-style response data.  The pipeline simulates a
binary (correct / incorrect) response matrix, fits a 2PL (or 3PL) latent-trait
model to it, and emits per-solver ability estimates, per-item difficulty /
discrimination parameters, fit diagnostics, and visualisations that make the
case for calibrated measurement over raw leaderboard accuracy.

> **Scope.** This is the *measurement* enhancement for the ARC AGI project
> (sub-project 02 of 05).  It does not touch the actual ARC-AGI leaderboard,
> the cognitive taxonomy (03), the grading rubric (04), or the audit
> framework (05).  All data shown here is synthetic but chosen to mimic
> ARC-style difficulty spread and solver heterogeneity.

---

## 1. Why IRT instead of "% correct"?

ARC tasks vary enormously in difficulty.  A solver who scores 60% by
crushing easy puzzles and missing the hard ones is *not* the same as a
solver who gets 60% by carefully picking up a few medium items.  Raw
accuracy hides that distinction.  IRT models each solver's latent ability
**θ** and each task's latent difficulty **b** and discrimination **a**
jointly, so that two solvers with identical raw accuracy can be
differentiated by **which** items they got right.

This pipeline makes the contrast visible: see
`outputs/same_accuracy_pairs.csv` for concrete solver pairs with near-
identical raw accuracy but meaningfully different IRT ability.

---

## 2. The model — 2PL (and 3PL)

For solver *i* and task *j*:

> **2PL**:  P(correct | θᵢ, aⱼ, bⱼ) = σ(aⱼ (θᵢ − bⱼ))
> where σ is the logistic sigmoid σ(z) = 1 / (1 + e⁻ᶻ).

> **3PL**:  P(correct | θᵢ, aⱼ, bⱼ, cⱼ) = cⱼ + (1 − cⱼ) · σ(aⱼ (θᵢ − bⱼ))

| Symbol | Meaning |
|--------|---------|
| θᵢ     | Solver *i*'s latent ability on the standard-normal scale. |
| aⱼ > 0 | Item *j*'s **discrimination**: how sharply the curve separates solvers around bⱼ. |
| bⱼ     | Item *j*'s **difficulty**: the ability level at which P(correct) = 0.5 (for 2PL). |
| cⱼ ∈ [0, 1) | Item *j*'s **guessing** floor (3PL only).  Default prior Beta(2, 10) keeps it low. |

### Identification

The likelihood is invariant under the transformations

    θᵢ → θᵢ + k,   bⱼ → bⱼ + k       (location)
    aⱼ → k aⱼ,     θᵢ − bⱼ → (θᵢ − bⱼ)/k   (scale)

To pin the model down we use weak Gaussian priors:

    θᵢ       ~ N(0, 1)
    bⱼ       ~ N(0, 2)
    log aⱼ   ~ N(0, 1)   ⇒   aⱼ median = 1
    cⱼ       ~ Beta(2, 10)   (3PL only; encourages low guessing,
                              matching ARC's open-ended answer format)

These are *not* informative for the data we generate (which has
σ_θ ≈ 1.5 and a, b roughly in the same range), so the MAP estimates
are essentially maximum-likelihood with a mild regularising nudge.

### Estimation

Joint MAP via **L-BFGS-B** over the unconstrained parameter vector
[θ, log a, b, (logit c)].  The 2PL path uses an analytic gradient
(tested against finite differences in `tests/test_irt.py`); the 3PL
path uses scipy's finite-difference gradient — the analytic 3PL
gradient is messy, and FD is more than fast enough for matrices our
size.

Initialisation uses the probit transform of each item's p-value to seed
**b**, plus zero **θ** and unit **a** (log a = 0) and c = 0.1 for 3PL.
A tiny jitter (1e-3 × N(0, 1)) breaks ties that confuse L-BFGS-B.

---

## 3. Synthetic data generator

`src/data_generator.py` simulates a `SimulationConfig`-driven response
matrix.  Default configuration:

| Setting              | Default | Meaning |
|----------------------|--------:|---------|
| `n_solvers`          |      30 | Solver count. |
| `n_items`            |      50 | Task count. |
| `theta_sd`           |     1.5 | Ability spread — wider than the prior to stress identification. |
| `mu_a, sigma_a`      | 0.0, 0.5 | Log-normal discrimination; median a = 1. |
| `mu_b, b_sd`         | 0.0, 1.5 | Difficulty range ≈ −3 to +3. |
| `c_a, c_b`           | 2.0, 10.0 | Beta(2, 10) — small guessing. |
| `noise_rate`         |     0.07 | After drawing X from Bernoulli(P), flip ~7% of responses. |
| `seed`               | 20240930 | Reproducibility. |

The noise step mimics mis-clicks, transcription slips, and inference
instability in real ARC submission pipelines.

---

## 4. Running the pipeline

From this directory:

```bash
# default: 30 solvers x 50 items, 2PL, 7% noise, seed 20240930
python run_pipeline.py

# try 3PL
python run_pipeline.py --model 3pl

# different noise level / seed
python run_pipeline.py --noise 0.10 --seed 7
```

The full pipeline (synthesise → fit → tabulate → plot) takes a few
seconds.  All artefacts land in `./outputs/`.

### Tests

```bash
python -m pytest tests/ -v
```

The unit tests cover ICC shapes and edge cases, log-likelihood
identities, parameter pack/unpack round-trip, analytic-vs-FD gradient,
and end-to-end fit quality on the default configuration.

---

## 5. Outputs

| File | Purpose |
|------|---------|
| `solver_abilities.csv` | Per-solver raw accuracy and IRT θ.  Includes true θ for reference. |
| `item_parameters.csv`  | Per-item (a, b[, c]) plus true values for recovery checks. |
| `item_fit_residuals.csv` | Signed and chi-square residuals per item.  Big values ⇒ item misfit. |
| `model_fit_summary.json` / `.txt` | log-likelihood, AIC, BIC, convergence, parameter means. |
| `icc_curves.png` | 6 ICCs spanning the difficulty range, showing how a and b vary. |
| `ability_distribution.png` | Histogram of θ̂ with N(0, 1) prior overlay. |
| `accuracy_vs_theta.png` | The headline scatter: raw accuracy vs IRT ability, with same-accuracy pairs highlighted. |
| `true_vs_estimated.png` | Sanity scatter of true vs recovered (θ, a, b). |
| `same_accuracy_pairs.csv` | Concrete pairs used in the demonstration. |

### How to read them

* **`model_fit_summary.txt`** is the first stop.  Confirm `converged: True`,
  then skim log-likelihood, AIC/BIC, and the parameter means.  AIC/BIC are
  not directly comparable to anything here, but they're useful when you
  compare 2PL vs 3PL on the same data.
* **`solver_abilities.csv`** is the *new* leaderboard — sort by `theta`
  descending.  The same-accuracy / different-θ pairs in
  `same_accuracy_pairs.csv` are the most informative rows for
  explaining IRT to a sceptic.
* **`item_parameters.csv`** is the *new* item bank.  Items with low `a`
  (~0.4 or less) are barely informative; consider dropping or replacing
  them.  Items with extreme |b| (>2.5) are too easy or too hard for the
  current solver pool.
* **`icc_curves.png`** shows what each item actually measures.  Steep
  curves (high a) separate solvers finely; flat curves (low a) are
  near-noise items.
* **`accuracy_vs_theta.png`** is the killer plot.  Look for pairs of
  points at the same vertical level with different x positions — those
  are the same-accuracy / different-ability solvers.

---

## 6. The headline insight

For the default 30 × 50 configuration the pipeline finds pairs like:

```
 solver_a  solver_b  raw_acc_a  raw_acc_b   |Δacc|   θ_a      θ_b      |Δθ|
       7        18       0.48      0.52      0.04   -0.19    +0.19    0.39
       16       28       0.44      0.40      0.04   -0.07    -0.46    0.39
```

Two solvers within 2 correct answers of each other on 50 tasks
(Δaccuracy ≈ 0.04) have IRT abilities that differ by ≈ 0.4 standard
deviations — about half a sigma.  This is precisely the kind of
information that gets washed out by the leaderboard's "% correct" column
and that IRT recovers by crediting solvers for *which* items they got
right, not just *how many*.

In a real ARC deployment, the practical payoff is twofold:

1. **Robust cross-population comparison.**  If a new solver joins the
   pool having attempted a different sub-set of tasks, MAP θ is still
   comparable to veteran solvers'.  Raw "% correct on your 30 tasks"
   is not.
2. **Item-bank curation.**  Items with low fitted `a` and high chi-
   square residuals are candidates for retirement, so future
   calibrations are sharper.

---

## 7. File tree

```
infra/irt/
├── README.md                  this file
├── requirements.txt           numpy, scipy, pandas, matplotlib, pytest
├── run_pipeline.py            end-to-end driver (CLI)
├── src/
│   ├── __init__.py
│   ├── irt_model.py           2PL/3PL ICC, likelihood, MAP fitter
│   ├── data_generator.py      SimulationConfig + generate_responses
│   ├── fitter.py              high-level fit / save_artifacts helpers
│   └── visualization.py       ICC, ability hist, accuracy vs theta
├── tests/
│   ├── __init__.py
│   └── test_irt.py            22 unit tests
└── outputs/                   generated by run_pipeline.py
    ├── solver_abilities.csv
    ├── item_parameters.csv
    ├── item_fit_residuals.csv
    ├── model_fit_summary.json
    ├── model_fit_summary.txt
    ├── same_accuracy_pairs.csv
    ├── icc_curves.png
    ├── ability_distribution.png
    ├── accuracy_vs_theta.png
    └── true_vs_estimated.png
```

---

## 8. Extending the pipeline

* **More realistic data.**  `SimulationConfig` already supports
  tweaking θ, a, b, c, and noise independently.  For an even more
  ARC-like shape, try `theta_sd=2.0` with `b_sd=2.0` and see how
  the latent-ability range widens.
* **3PL with informative priors.**  Pass `model='3pl'` to
  `run_pipeline.py`.  The default Beta(2, 10) prior on c is
  appropriate for ARC (open-ended answers, low guessing); change
  `c_prior_a, c_prior_b` in `neg_log_posterior` for a different
  application.
* **Other estimation methods.**  Marginal MLE via Gauss-Hermite
  quadrature (Bock–Aitkin EM) would give a purer likelihood
  treatment; the current joint MAP is simpler and adequate for
  the matrix sizes we use here.  Swap `fit_irt` for a different
  backend — the rest of the pipeline only depends on the
  `IRTFitResult` dataclass.
* **Real ARC data.**  Once an ARC submission log is available, feed
  its `(solver, task) → 0/1` matrix in place of the synthetic one.
  Everything downstream of `fit_synthetic` works unchanged.