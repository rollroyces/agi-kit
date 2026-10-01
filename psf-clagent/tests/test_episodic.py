"""v2 tests for the episodic-memory store."""
from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass
from typing import List

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from memory.episodic import (  # noqa: E402
    EpisodicMemory, Trace, episodic_vector,
)
from agent import CLAgent, MemoryFacade, SolveConfig  # noqa: E402
from reference.airt import ToolBridge  # noqa: E402


@dataclass
class _Feat:
    palette_size: int = 0
    object_count: int = 0
    has_symmetry_h: bool = False
    has_symmetry_v: bool = False
    n_train_pairs: int = 0
    shape_invariant: bool = True
    output_introduces_new_color: bool = False
    is_multichannel: bool = False


class TestEpisodicMemoryCRUD(unittest.TestCase):

    def test_store_and_get(self):
        emem = EpisodicMemory()
        t = Trace(task_id="t1", winning_program_label="identity")
        emem.store_trace(t)
        self.assertIs(emem.get("t1"), t)

    def test_overwrite_existing_trace(self):
        emem = EpisodicMemory()
        emem.store_trace(Trace(task_id="t1", winning_program_label="a"))
        emem.store_trace(Trace(task_id="t1", winning_program_label="b"))
        self.assertEqual(len(emem), 1)
        self.assertEqual(emem.get("t1").winning_program_label, "b")

    def test_preset_has_seed(self):
        emem = EpisodicMemory.preset()
        self.assertEqual(len(emem), 1)
        self.assertIn("seed::rotate_largest::01", emem)


class TestEpisodicRetrieval(unittest.TestCase):

    def test_retrieve_similar_excludes_self(self):
        emem = EpisodicMemory()
        # Three traces with distinct features.
        emem.store_trace(Trace(task_id="a", features=_Feat(
            palette_size=5, object_count=2, has_symmetry_h=True,
        )))
        emem.store_trace(Trace(task_id="b", features=_Feat(
            palette_size=8, object_count=4, has_symmetry_v=True,
        )))
        emem.store_trace(Trace(task_id="c", features=_Feat(
            palette_size=3, object_count=1,
        )))
        out = emem.retrieve_similar(
            _Feat(palette_size=5, object_count=2, has_symmetry_h=True),
            k=2, exclude=["a"],
        )
        ids = [t.task_id for t in out]
        self.assertNotIn("a", ids)
        self.assertEqual(len(out), 2)

    def test_retrieve_returns_at_most_k(self):
        emem = EpisodicMemory()
        for i in range(5):
            emem.store_trace(Trace(task_id=f"t{i}", features=_Feat(
                palette_size=i, object_count=i)))
        out = emem.retrieve_similar(_Feat(palette_size=2, object_count=2), k=3)
        self.assertEqual(len(out), 3)

    def test_retrieve_similarity_ordering(self):
        emem = EpisodicMemory()
        # 'close' has palette=4, count=2; 'far' has palette=9, count=5.
        emem.store_trace(Trace(task_id="close", features=_Feat(
            palette_size=4, object_count=2)))
        emem.store_trace(Trace(task_id="far", features=_Feat(
            palette_size=9, object_count=5)))
        out = emem.retrieve_similar(_Feat(palette_size=4, object_count=2), k=2)
        self.assertEqual(out[0].task_id, "close")

    def test_retrieve_empty_store_returns_empty(self):
        emem = EpisodicMemory()
        self.assertEqual(emem.retrieve_similar(_Feat(), k=3), [])

    def test_episodic_vector_normalises_palette(self):
        a = episodic_vector(_Feat(palette_size=10, object_count=5))
        b = episodic_vector(_Feat(palette_size=5, object_count=2))
        # Same length, normalised → identical-length vectors.
        self.assertEqual(len(a), len(b))
        self.assertEqual(len(a), 8)


class TestEpisodicMemoryWiring(unittest.TestCase):

    def test_agent_stores_trace_after_solve(self):
        # Identity task → template proposer succeeds → trace stored.
        task = {
            "generator": "test_family",
            "generator_signature": "0" * 64,
            "public_seed": "p",
            "private_seed": "q",
            "parameters": {},
            "task": {
                "train": [
                    {"input": [[1, 0], [0, 1]], "output": [[1, 0], [0, 1]]},
                ],
                "test": [
                    {"input": [[2, 2], [2, 2]], "output": [[2, 2], [2, 2]]},
                ],
            },
        }
        mem = MemoryFacade()
        before = len(mem._episodic_mem)
        CLAgent().solve(task, mem, ToolBridge())
        after = len(mem._episodic_mem)
        self.assertGreater(after, before)

    def test_agent_retrieves_seed_as_hint(self):
        # The seed is a "rotate_largest" task with palette_size=3 etc.
        # Our second task matches the seed exactly → trace should be
        # present and retrievable before this solve is committed.
        task = {
            "generator": "rotate_largest",
            "generator_signature": "0" * 64,
            "public_seed": "p",
            "private_seed": "q",
            "parameters": {},
            "task": {
                "train": [
                    {"input": [[0, 0], [0, 1]], "output": [[0, 0], [1, 0]]},
                    {"input": [[0, 0], [0, 2]], "output": [[0, 0], [2, 0]]},
                    {"input": [[0, 0], [0, 3]], "output": [[0, 0], [3, 0]]},
                ],
                "test": [{"input": [[0, 0], [0, 4]], "output": [[0, 0], [4, 0]]}],
            },
        }
        mem = MemoryFacade()
        agent = CLAgent()
        ans = agent.solve(task, mem, ToolBridge())
        # The trace has a "retrieve_episodic" step that mentions hints.
        kinds = [s.get("kind") for s in ans.trace["steps"]]
        self.assertIn("retrieve_episodic", kinds)


if __name__ == "__main__":
    unittest.main()