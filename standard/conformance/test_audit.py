"""Conformance test for A3S SPEC §7 — Audit protocol."""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_THIS, ".."))
sys.path.insert(0, _ROOT)

from reference.audit import (  # noqa: E402
    REQUIRED_CATEGORIES, _categories_covered, audit_task, audit_tasks,
)


def _identity_task() -> dict:
    """A task that the 'identity' heuristic MUST solve (sanity fixture)."""
    return {
        "generator":           "sanity",
        "generator_signature": "0" * 64,
        "public_seed":         "p",
        "private_seed":        "q",
        "parameters":          {},
        "task": {
            "train": [{"input": [[1, 1], [1, 1]], "output": [[1, 1], [1, 1]]}],
            "test":  [{"input": [[2, 2], [2, 2]], "output": [[2, 2], [2, 2]]}],
        },
    }


def _non_trivial_task() -> dict:
    """A task that NO shallow heuristic in the registry should solve.

    Rule: output is the input with the diagonal set to colour 7 — a rule
    none of the bundled heuristics implement.
    """
    return {
        "generator":           "fill_enclosed",
        "generator_signature": "0" * 64,
        "public_seed":         "p",
        "private_seed":        "q",
        "parameters":          {},
        "task": {
            "train": [
                {
                    "input":  [[1, 0], [0, 1]],
                    "output": [[7, 0], [0, 7]],
                },
                {
                    "input":  [[2, 0, 0], [0, 0, 0], [0, 0, 2]],
                    "output": [[7, 0, 0], [0, 7, 0], [0, 0, 7]],
                },
            ],
            "test": [
                {"input": [[3, 0, 0], [0, 0, 0], [0, 0, 3]],
                 "output": [[7, 0, 0], [0, 7, 0], [0, 0, 7]]},
            ],
        },
    }


class TestAudit(unittest.TestCase):
    """SPEC §7 — verdict schema, categories, quarantine."""

    def test_at_least_5_heuristics_registered(self):
        """SPEC §7.2 requires ≥5 heuristics; the imported registry has 8."""
        from reference.audit import HEURISTICS  # type: ignore
        self.assertGreaterEqual(len(HEURISTICS), 5)

    def test_categories_covered(self):
        """Each of identity/palette/geometry/object/counting MUST be covered."""
        cov = _categories_covered()
        for cat, ok in cov.items():
            self.assertTrue(ok, f"required category '{cat}' is not covered")

    def test_identity_task_is_quarantined(self):
        """A task where output == input MUST be flagged 'quarantine'."""
        v = audit_task(_identity_task())
        self.assertEqual(v["verdict"], "quarantine")
        # The heuristic registry is named under "per_heuristic" with hit booleans.
        self.assertTrue(v["per_heuristic"]["identity"]["hit"])

    def test_non_trivial_task_passes(self):
        """A rule-based task MUST pass the audit (not trivially solvable)."""
        v = audit_task(_non_trivial_task())
        self.assertEqual(v["verdict"], "pass")
        self.assertFalse(v["trivially_solvable"])

    def test_verdict_schema_matches_spec(self):
        """Audit verdict MUST have the §7.3 fields."""
        v = audit_task(_identity_task())
        for key in ("task_id", "audited_at", "audit_version",
                    "heuristics_run", "per_heuristic",
                    "trivially_solvable", "verdict"):
            self.assertIn(key, v, f"verdict missing '{key}'")

    def test_audit_tasks_aggregates(self):
        """audit_tasks() MUST aggregate per-heuristic accuracy + categories."""
        report = audit_tasks([_identity_task(), _non_trivial_task()])
        self.assertEqual(report["n_tasks"], 2)
        self.assertEqual(report["n_trivially_solvable"], 1)
        self.assertIn("identity", report["per_heuristic_accuracy"])

    def test_audit_version_is_a_sha256(self):
        """audit_version MUST be a 64-char hex sha256 (§7.3)."""
        v = audit_task(_identity_task())
        self.assertEqual(len(v["audit_version"]), 64)
        int(v["audit_version"], 16)


if __name__ == "__main__":
    unittest.main()
