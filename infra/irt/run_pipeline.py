"""End-to-end IRT calibration pipeline driver.

Run with::

    python run_pipeline.py            # default 2PL on the standard 30x50 sim
    python run_pipeline.py --model 3pl

Outputs (under ./outputs/):
    solver_abilities.csv       -- per-solver raw accuracy and theta
    item_parameters.csv        -- per-item a, b, [c], plus true values
    item_fit_residuals.csv     -- signed and chi-square residuals per item
    model_fit_summary.json     -- machine-readable fit summary
    model_fit_summary.txt      -- human-readable fit summary
    icc_curves.png             -- ICC for 6 representative items
    ability_distribution.png   -- histogram of theta with N(0,1) overlay
    accuracy_vs_theta.png      -- raw accuracy vs theta scatter + same-acc pairs
    true_vs_estimated.png      -- true vs estimated parameter recovery
    same_accuracy_pairs.csv    -- concrete example pairs used in the demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_generator import (
    SimulationConfig,
    generate_responses,
    solver_raw_accuracy,
)
from src.fitter import fit_synthetic, save_artifacts, solver_dataframe, item_dataframe
from src.irt_model import fit_irt, model_summary
from src.visualization import (
    plot_accuracy_vs_theta,
    plot_ability_histogram,
    plot_icc_curves,
    plot_true_vs_estimated,
)


HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"


def find_same_accuracy_pairs(solvers: pd.DataFrame, n_pairs: int = 3,
                             tol: float = 0.06) -> list[tuple[int, int]]:
    """Find solver pairs with very similar raw accuracy but different theta.

    For each solver, look for another solver whose raw_accuracy is within
    ``tol`` (default 0.06 = 3 correct answers on 50 items) but whose theta
    differs by at least 0.25 * sigma_theta.  Returns up to ``n_pairs`` such
    pairs (deterministic order: largest theta gap first).
    """
    acc = solvers["raw_accuracy"].values
    th = solvers["theta"].values
    sd = th.std(ddof=1)
    candidates = []
    for i in range(len(acc)):
        for j in range(i + 1, len(acc)):
            if abs(acc[i] - acc[j]) <= tol and abs(th[i] - th[j]) >= 0.25 * sd:
                candidates.append((abs(th[i] - th[j]), i, j))
    candidates.sort(reverse=True)
    return [(i, j) for _, i, j in candidates[:n_pairs]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="2pl", choices=["2pl", "3pl"])
    parser.add_argument("--n-solvers", type=int, default=30)
    parser.add_argument("--n-items", type=int, default=50)
    parser.add_argument("--noise", type=float, default=0.07)
    parser.add_argument("--seed", type=int, default=20240930)
    parser.add_argument("--fit-seed", type=int, default=0)
    parser.add_argument("--max-iter", type=int, default=500)
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate synthetic data
    cfg = SimulationConfig(
        n_solvers=args.n_solvers,
        n_items=args.n_items,
        noise_rate=args.noise,
        seed=args.seed,
    )
    sim = generate_responses(cfg, model=args.model, seed=args.seed)
    X = sim["X"]

    # 2. Fit the IRT model
    fit, residuals, summary = fit_synthetic(
        X,
        model=args.model,
        seed=args.fit_seed,
        max_iter=args.max_iter,
    )

    # 3. Save tabular / summary artifacts
    true_params = {
        "theta": sim["theta"],
        "a": sim["a"],
        "b": sim["b"],
    }
    if sim["c"] is not None:
        true_params["c"] = sim["c"]
    save_artifacts(
        out_dir,
        fit=fit,
        residuals=residuals,
        summary=summary,
        X=X,
        true_params=true_params,
    )

    # 4. Visualisations
    plot_icc_curves(fit, out_path=out_dir / "icc_curves.png")
    plot_ability_histogram(fit, out_path=out_dir / "ability_distribution.png")

    solvers_df = solver_dataframe(fit, X)
    pairs = find_same_accuracy_pairs(solvers_df, n_pairs=3, tol=0.06)
    plot_accuracy_vs_theta(solvers_df, pairs=pairs,
                           out_path=out_dir / "accuracy_vs_theta.png")

    plot_true_vs_estimated(
        {"theta": sim["theta"], "a": sim["a"], "b": sim["b"]},
        fit,
        out_path=out_dir / "true_vs_estimated.png",
    )

    # 5. The concrete same-accuracy demonstration table
    rows = []
    for i, j in pairs:
        rows.append(
            {
                "solver_a": i,
                "solver_b": j,
                "raw_accuracy_a": float(solvers_df.loc[i, "raw_accuracy"]),
                "raw_accuracy_b": float(solvers_df.loc[j, "raw_accuracy"]),
                "abs_acc_diff": abs(
                    solvers_df.loc[i, "raw_accuracy"]
                    - solvers_df.loc[j, "raw_accuracy"]
                ),
                "theta_a": float(solvers_df.loc[i, "theta"]),
                "theta_b": float(solvers_df.loc[j, "theta"]),
                "abs_theta_diff": float(abs(
                    solvers_df.loc[i, "theta"]
                    - solvers_df.loc[j, "theta"]
                )),
            }
        )
    pairs_df = pd.DataFrame(rows)
    pairs_df.to_csv(out_dir / "same_accuracy_pairs.csv", index=False)

    # 6. Console report
    print("=" * 64)
    print(f"IRT pipeline complete ({summary['model']})")
    print("=" * 64)
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k:<16}: {v:.4f}")
        else:
            print(f"  {k:<16}: {v}")
    print()
    print("Per-solver ability sample:")
    print(solver_dataframe(fit, X).head().to_string(index=False))
    print()
    print("Per-item parameter sample:")
    print(item_dataframe(fit).head().to_string(index=False))
    print()
    if pairs:
        print("Same-raw-accuracy, different-theta pairs (the headline demo):")
        print(pairs_df.to_string(index=False))
    else:
        print("No same-raw-accuracy, different-theta pairs found "
              "(try a different seed).")
    print()
    print(f"Artifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()