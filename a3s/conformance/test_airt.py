"""Conformance test for A3S SPEC §6 — Agent interface."""
from __future__ import annotations

import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_THIS, ".."))
sys.path.insert(0, _ROOT)

from reference.airt import (  # noqa: E402
    Agent, Answer, InMemoryStore, ToolBridge,
)


class _IdentityAgent(Agent):
    """Minimal conforming agent: identity program wins because the task is identity."""
    name = "identity_agent"
    version = "1.0.0"

    def propose_programs(self, task):
        return [self._identity, self._all_zero]

    @staticmethod
    def _identity(g):
        return [row[:] for row in g]

    @staticmethod
    def _all_zero(g):
        return [[0 for _ in row] for row in g]


def _identity_task() -> dict:
    return {
        "generator":           "identity",
        "generator_signature": "0" * 64,
        "public_seed":         "p",
        "private_seed":        "q",
        "parameters":          {},
        "task": {
            "train": [
                {"input": [[0, 1], [1, 0]], "output": [[0, 1], [1, 0]]},
                {"input": [[2, 2], [2, 2]], "output": [[2, 2], [2, 2]]},
            ],
            "test": [
                {"input": [[3, 3], [3, 3]], "output": [[3, 3], [3, 3]]},
            ],
        },
    }


class TestAirt(unittest.TestCase):
    """SPEC §6 — solve() signature, trace schema, Answer shape."""

    def test_solve_returns_answer(self):
        """solve() MUST return an Answer with one prediction per test pair."""
        ans = _IdentityAgent().solve(_identity_task(), InMemoryStore(), ToolBridge())
        self.assertIsInstance(ans, Answer)
        self.assertEqual(len(ans.test_predictions), 1)

    def test_solve_returns_correct_grid_for_identity_task(self):
        """The default verify-three-candidates loop MUST find the identity program."""
        ans = _IdentityAgent().solve(_identity_task(), InMemoryStore(), ToolBridge())
        self.assertEqual(ans.test_predictions[0], [[3, 3], [3, 3]])

    def test_trace_has_required_fields(self):
        """The trace MUST include agent_version, started_at, finished_at, steps."""
        ans = _IdentityAgent().solve(_identity_task(), InMemoryStore(), ToolBridge())
        for key in ("agent_version", "started_at", "finished_at", "steps"):
            self.assertIn(key, ans.trace, f"trace missing '{key}'")
        self.assertGreater(len(ans.trace["steps"]), 0)

    def test_trace_steps_are_kind_typed(self):
        """Every step MUST have a 'kind' field per §6.2."""
        ans = _IdentityAgent().solve(_identity_task(), InMemoryStore(), ToolBridge())
        for step in ans.trace["steps"]:
            self.assertIn("kind", step)
            self.assertIn("step", step)

    def test_memory_stores_are_callable(self):
        """Memory **MUST** expose three readable/writable stores (§6.3)."""
        mem = InMemoryStore()
        for store in ("episodic", "semantic", "procedural"):
            getattr(mem, f"write_{store}")("k", "v")
            self.assertEqual(getattr(mem, f"read_{store}")("k"), "v")

    def test_prediction_matches_input_shape(self):
        """Returned grids MUST match the test input shape (§6.1)."""
        ans = _IdentityAgent().solve(_identity_task(), InMemoryStore(), ToolBridge())
        pred = ans.test_predictions[0]
        self.assertEqual(len(pred), 2)
        self.assertEqual(len(pred[0]), 2)


if __name__ == "__main__":
    unittest.main()
