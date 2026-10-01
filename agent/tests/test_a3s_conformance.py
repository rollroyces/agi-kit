"""A3S conformance tests for the agent's ``solve()`` output.

The agent MUST satisfy SPEC §6:

* ``Answer.test_predictions`` is a non-empty list of grids, one per test pair.
* Each prediction has the same shape as its corresponding test input.
* The trace has ``agent_version``, ``started_at``, ``finished_at``, ``steps``,
  and ``memory_writes``.
* Every step has a ``kind`` field per §6.2.
* ``Memory`` (the parameter to ``solve()``) supports the three stores from
  §6.3: episodic, semantic, procedural.
"""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ARC = os.path.abspath(os.path.join(_ROOT, ".."))
sys.path.insert(0, _ARC)
sys.path.insert(0, os.path.join(_ARC, "standard"))

from agent import CLAgent, MemoryFacade  # noqa: E402
from reference.airt import InMemoryStore, ToolBridge  # noqa: E402


def _identity_task() -> dict:
    return {
        "generator": "identity",
        "generator_signature": "0" * 64,
        "public_seed": "p",
        "private_seed": "q",
        "parameters": {},
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


class TestA3SConformance(unittest.TestCase):
    """SPEC §6 — solve() signature, trace schema, Answer shape."""

    def test_solve_returns_answer(self):
        ans = CLAgent().solve(_identity_task(), MemoryFacade(), ToolBridge())
        # Answer is a simple object — should at least have the two required fields.
        self.assertTrue(hasattr(ans, "test_predictions"))
        self.assertTrue(hasattr(ans, "trace"))
        self.assertEqual(len(ans.test_predictions), 1)

    def test_solve_returns_correct_grid_for_identity_task(self):
        ans = CLAgent().solve(_identity_task(), MemoryFacade(), ToolBridge())
        # The identity task: input = output, so any solver should produce [[3,3],[3,3]].
        self.assertEqual(ans.test_predictions[0], [[3, 3], [3, 3]])

    def test_trace_has_required_fields(self):
        ans = CLAgent().solve(_identity_task(), MemoryFacade(), ToolBridge())
        for key in ("agent_version", "started_at", "finished_at", "steps",
                    "memory_writes"):
            self.assertIn(key, ans.trace, f"trace missing '{key}'")
        self.assertGreater(len(ans.trace["steps"]), 0)

    def test_trace_steps_are_kind_typed(self):
        ans = CLAgent().solve(_identity_task(), MemoryFacade(), ToolBridge())
        for step in ans.trace["steps"]:
            self.assertIn("kind", step, f"step {step} missing 'kind'")
            self.assertIn("step", step)

    def test_memory_stores_are_callable(self):
        """The Memory parameter to solve() MUST expose three readable/writable stores."""
        mem = MemoryFacade()
        for store in ("episodic", "semantic", "procedural"):
            getattr(mem, f"write_{store}")("k", "v")
            self.assertEqual(getattr(mem, f"read_{store}")("k"), "v")

    def test_prediction_matches_input_shape(self):
        ans = CLAgent().solve(_identity_task(), MemoryFacade(), ToolBridge())
        pred = ans.test_predictions[0]
        self.assertEqual(len(pred), 2)
        self.assertEqual(len(pred[0]), 2)

    def test_in_memory_store_also_conforms(self):
        """The reference ``InMemoryStore`` from ``a3s/reference/airt.py`` must also work."""
        ans = CLAgent().solve(_identity_task(), InMemoryStore(), ToolBridge())
        self.assertEqual(ans.test_predictions[0], [[3, 3], [3, 3]])


if __name__ == "__main__":
    unittest.main()