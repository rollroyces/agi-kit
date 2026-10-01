"""Unit tests for the four-tier math grader.

Run with: ``python -m unittest test_math_grading.py`` from this directory.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from grade import TIER_WEIGHTS, grade, grade_task  # noqa: E402


class TestGradeTier1(unittest.TestCase):

    def test_exact_int_match(self):
        r = grade("42", "42")
        self.assertEqual(r["tier"], 1)
        self.assertEqual(r["score"], 1.0)
        self.assertEqual(r["predicted_value"], 42.0)
        self.assertEqual(r["ground_truth_value"], 42.0)

    def test_exact_string_with_no_number_still_matches(self):
        # Both unparseable but identical → tier1.
        r = grade("hello", "hello")
        self.assertEqual(r["tier"], 1)

    def test_exact_float_match(self):
        r = grade("3.14", "3.14")
        self.assertEqual(r["tier"], 1)


class TestGradeTier2(unittest.TestCase):

    def test_within_default_tolerance(self):
        r = grade("1.0000001", "1.0")
        self.assertEqual(r["tier"], 2)
        self.assertAlmostEqual(r["score"], 0.7)

    def test_custom_tolerance(self):
        r = grade("1.5", "1.0", tolerance=1.0)
        self.assertEqual(r["tier"], 2)


class TestGradeTier3(unittest.TestCase):

    def test_off_by_power_of_ten(self):
        r = grade("50", "5")
        self.assertEqual(r["tier"], 3)
        self.assertAlmostEqual(r["score"], 0.3)

    def test_close_magnitude_ratio_within_factor_10(self):
        r = grade("9.5", "1.0")
        # 9.5 vs 1.0 ratio = 9.5 -> within factor 10 -> tier 3
        self.assertEqual(r["tier"], 3)

    def test_far_magnitude_is_tier0(self):
        r = grade("100", "1")
        # 100 / 1 = 100 → outside factor of 10 → tier 0.
        self.assertEqual(r["tier"], 0)


class TestGradeTier0(unittest.TestCase):

    def test_unparseable_predicted(self):
        r = grade("no number", "42")
        self.assertEqual(r["tier"], 0)

    def test_unparseable_ground_truth(self):
        r = grade("42", "no number")
        self.assertEqual(r["tier"], 0)

    def test_neither_parseable(self):
        r = grade("foo", "bar")
        # Neither parses → falls through to tier0 (not exact).
        self.assertEqual(r["tier"], 0)


class TestGradeTaskAggregate(unittest.TestCase):

    def test_single_test_pair(self):
        task = {"test": [{"input": "x", "output": "5"}]}
        result = grade_task(task, ["5"])
        self.assertEqual(result["task_score"], 1.0)
        self.assertEqual(result["strict"], 1.0)
        self.assertEqual(result["per_example"][0]["tier"], 1)

    def test_aggregate_averages_per_example_scores(self):
        task = {"test": [
            {"input": "x", "output": "5"},
            {"input": "y", "output": "10"},
        ]}
        # First exact (1.0), second off by power-of-10 (0.3) → mean = 0.65.
        result = grade_task(task, ["5", "100"])
        self.assertAlmostEqual(result["task_score"], 0.65, places=5)
        # strict is the mean of tier-1 examples only; one hit → 1.0.
        self.assertEqual(result["strict"], 1.0)

    def test_strict_none_when_no_tier1(self):
        task = {"test": [
            {"input": "x", "output": "5"},
            {"input": "y", "output": "10"},
        ]}
        # Both wrong (tier 0 / 3) → strict is None.
        result = grade_task(task, ["100", "1"])
        self.assertIsNone(result["strict"])

    def test_length_mismatch_raises(self):
        task = {"test": [{"input": "x", "output": "5"}]}
        with self.assertRaises(ValueError):
            grade_task(task, ["5", "5"])

    def test_envelope_shape_supported(self):
        task = {
            "generator": "x",
            "public_seed": "p",
            "private_seed": "q",
            "parameters": {},
            "task": {"test": [{"input": "x", "output": "5"}]},
        }
        result = grade_task(task, ["5"])
        self.assertEqual(result["task_score"], 1.0)


class TestWeightsAndDiagnostics(unittest.TestCase):

    def test_tier_weights_match_arc(self):
        # Must match ARC's tier weights (1.0 / 0.7 / 0.3 / 0.0) so the
        # cross-domain aggregate scores are comparable.
        self.assertEqual(TIER_WEIGHTS[1], 1.0)
        self.assertEqual(TIER_WEIGHTS[2], 0.7)
        self.assertEqual(TIER_WEIGHTS[3], 0.3)
        self.assertEqual(TIER_WEIGHTS[0], 0.0)

    def test_diagnostics_returned(self):
        r = grade("42", "42")
        self.assertIn("absolute_error", r)
        self.assertIn("magnitude_ratio", r)
        self.assertIn("predicted_value", r)
        self.assertIn("ground_truth_value", r)

    def test_zero_ground_truth_handled(self):
        r = grade("0", "0")
        self.assertEqual(r["tier"], 1)
        r2 = grade("0", "5")
        self.assertEqual(r2["tier"], 0)  # ratio undefined → no tier-3
        r3 = grade("0", "0")  # both zero
        self.assertEqual(r3["tier"], 1)


if __name__ == "__main__":
    unittest.main()
