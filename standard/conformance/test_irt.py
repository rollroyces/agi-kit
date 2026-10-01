"""Conformance test for A3S SPEC §9 — Reporting protocol (IRT section)."""
from __future__ import annotations

import math
import os
import sys
import unittest

import numpy as np

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_THIS, ".."))
sys.path.insert(0, _ROOT)

from reference.irt import CI95, fit_irt_report  # noqa: E402


class TestIrt(unittest.TestCase):
    """SPEC §9 — IRT section: theta, theta_ci95, model, n_solvers, n_items."""

    def test_fit_returns_required_keys(self):
        """§9 irt block MUST contain theta, theta_ci95, model, n_solvers, n_items."""
        rng = np.random.default_rng(0)
        X = (rng.uniform(size=(15, 8)) < 0.5).astype(int)
        r = fit_irt_report(X, model="2pl")
        for key in ("theta", "theta_ci95", "model", "n_solvers", "n_items"):
            self.assertIn(key, r, f"irt block missing '{key}'")

    def test_theta_ci95_is_two_floats(self):
        """theta_ci95 MUST be a list [lo, hi] (SPEC §9)."""
        rng = np.random.default_rng(0)
        X = (rng.uniform(size=(10, 5)) < 0.5).astype(int)
        r = fit_irt_report(X, model="2pl")
        self.assertIsInstance(r["theta_ci95"], list)
        self.assertEqual(len(r["theta_ci95"]), 2)
        lo, hi = r["theta_ci95"]
        self.assertLessEqual(lo, hi)

    def test_model_field_matches_input(self):
        """model field MUST reflect the requested model ('2PL' or '3PL')."""
        rng = np.random.default_rng(0)
        X = (rng.uniform(size=(10, 5)) < 0.5).astype(int)
        r2 = fit_irt_report(X, model="2pl")
        r3 = fit_irt_report(X, model="3pl")
        self.assertEqual(r2["model"], "2PL")
        self.assertEqual(r3["model"], "3PL")

    def test_dimensions_match_input(self):
        """n_solvers / n_items MUST match the response matrix shape."""
        rng = np.random.default_rng(0)
        N, J = 12, 7
        X = (rng.uniform(size=(N, J)) < 0.5).astype(int)
        r = fit_irt_report(X, model="2pl")
        self.assertEqual(r["n_solvers"], N)
        self.assertEqual(r["n_items"], J)

    def test_ci95_helper_is_symmetric(self):
        """The CI95 helper MUST be mean ± half-width."""
        lo, hi = CI95(mean=0.5, sd=1.0, n=100)
        self.assertAlmostEqual((lo + hi) / 2, 0.5, places=4)
        self.assertAlmostEqual(hi - lo, 2 * 1.959963984540054 / 10, places=4)

    def test_ci95_single_solver_returns_degenerate(self):
        """n=1 MUST produce lo == hi == mean (no CI defined)."""
        lo, hi = CI95(mean=0.3, sd=0.5, n=1)
        self.assertEqual(lo, hi)
        self.assertEqual(lo, 0.3)

    def test_ci95_zero_sd_returns_degenerate(self):
        """sd=0 MUST produce lo == hi == mean (no variance -> no spread)."""
        lo, hi = CI95(mean=0.7, sd=0.0, n=50)
        self.assertEqual(lo, hi)
        self.assertEqual(lo, 0.7)


if __name__ == "__main__":
    unittest.main()
