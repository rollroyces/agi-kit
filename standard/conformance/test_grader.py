"""Conformance test for A3S SPEC §8 — Scoring protocol."""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_THIS, ".."))
sys.path.insert(0, _ROOT)

from reference.grader import (  # noqa: E402
    INVARIANCES_FROZEN as A3S_INVARIANCES,
    TIER_WEIGHTS_FROZEN as A3S_TIER_WEIGHTS,
    grade_predictions,
)


def gt():  return [[1, 1], [1, 1]]


class TestGrader(unittest.TestCase):
    """SPEC §8 — tier weights, invariance classes, per-example schema."""

    def test_tier1_exact_match(self):
        """Cell-by-cell match MUST yield tier=1, score=1.0."""
        r = grade_predictions([gt()], [gt()])
        self.assertEqual(r["task_score"], 1.0)
        self.assertEqual(r["per_example"][0]["tier"], 1)
        self.assertEqual(r["per_example"][0]["matched_invariance"], "id")

    def test_tier2_palette_permutation(self):
        """Swapping palette MUST count as tier=2 (score=0.7)."""
        # gt uses colour 1; predicted uses colour 2 everywhere -> pal match.
        pred = [[2, 2], [2, 2]]
        r = grade_predictions([pred], [gt()])
        row = r["per_example"][0]
        self.assertEqual(row["tier"], 2)
        self.assertEqual(row["score"], 0.7)
        self.assertEqual(row["matched_invariance"], "pal")
        self.assertIsNotNone(row["palette_mapping"])

    def test_tier3_structural_partial(self):
        """A mostly-correct prediction with one wrong cell MUST be tier=3."""
        pred = [[1, 1], [1, 0]]   # 3/4 cells match
        r = grade_predictions([pred], [gt()])
        row = r["per_example"][0]
        self.assertEqual(row["tier"], 3)
        self.assertEqual(row["score"], 0.3)
        self.assertGreaterEqual(row["cell_match"], 0.6)

    def test_tier0_full_miss(self):
        """A complete miss MUST yield tier=0, score=0.0."""
        pred = [[9, 8], [7, 6]]
        r = grade_predictions([pred], [gt()])
        row = r["per_example"][0]
        self.assertEqual(row["tier"], 0)
        self.assertEqual(row["score"], 0.0)

    def test_invariances_are_freeze_set(self):
        """A3S v1 freezes the 8 invariance codes (§8.2)."""
        self.assertEqual(
            set(A3S_INVARIANCES),
            {"id", "pal", "rot90", "rot180", "rot270", "fh", "fv", "tr"},
        )

    def test_tier_weights_match_spec(self):
        """A3S v1 freezes tier weights to 1.0 / 0.7 / 0.3 / 0.0 (§8.1)."""
        self.assertEqual(A3S_TIER_WEIGHTS, {0: 0.0, 1: 1.0, 2: 0.7, 3: 0.3})

    def test_per_example_schema_matches_spec_8_3(self):
        """Per-example rows MUST have the §8.3 keys."""
        r = grade_predictions([gt()], [gt()])
        row = r["per_example"][0]
        for key in ("tier", "score", "matched_invariance",
                    "palette_mapping", "cell_match", "object_iou",
                    "audit_failed"):
            self.assertIn(key, row, f"per_example missing '{key}'")

    def test_audit_failed_propagates(self):
        """An audit verdict of 'quarantine' MUST mark audit_failed=True."""
        r = grade_predictions(
            [gt()], [gt()],
            audit_verdict={"verdict": "quarantine"},
        )
        self.assertTrue(r["audit_failed"])

    def test_no_audit_verdict_means_audit_failed_false(self):
        """Default (no audit verdict) MUST leave audit_failed=False."""
        r = grade_predictions([gt()], [gt()])
        self.assertFalse(r["audit_failed"])


if __name__ == "__main__":
    unittest.main()
