"""Procedural-memory tests: CRUD, lifting, pre-seeding."""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REPO = os.path.abspath(os.path.join(_ROOT, ".."))
sys.path.insert(0, _REPO)

from agent.memory import ProceduralMemory, LiftError  # noqa: E402


class TestCRUD(unittest.TestCase):

    def test_add_and_get(self):
        mem = ProceduralMemory()
        mem.add("noop", lambda g: g)
        self.assertIsNotNone(mem.get("noop"))

    def test_duplicate_name_rejected(self):
        mem = ProceduralMemory()
        mem.add("noop", lambda g: g)
        with self.assertRaises(KeyError):
            mem.add("noop", lambda g: g)

    def test_missing_get_raises(self):
        mem = ProceduralMemory()
        with self.assertRaises(KeyError):
            mem.get("nope")

    def test_list_all_preserves_order(self):
        mem = ProceduralMemory()
        mem.add("a", lambda g: g)
        mem.add("b", lambda g: g)
        mem.add("c", lambda g: g)
        names = [n for n, _ in mem.list_all()]
        self.assertEqual(names, ["a", "b", "c"])


class TestLifting(unittest.TestCase):

    def test_lift_when_two_programs_share_subtree(self):
        mem = ProceduralMemory()
        # Both programs contain the sub-expression ("rotate", ("identity",), 1).
        prog_a = ("compose", ("rotate", ("identity",), 1), ("identity",))
        prog_b = ("compose", ("rotate", ("identity",), 1), ("flip_h", ("identity",)))
        mem.add("p_a", prog_a)
        mem.add("p_b", prog_b)
        name = mem.lift()
        self.assertTrue(name.startswith("auto_lift_"))
        self.assertIn(name, mem)

    def test_no_lift_when_subtree_unique(self):
        mem = ProceduralMemory()
        prog_a = ("rotate", ("identity",), 1)
        prog_b = ("flip_h", ("identity",))
        mem.add("a", prog_a)
        mem.add("b", prog_b)
        with self.assertRaises(LiftError):
            mem.lift()

    def test_no_lift_below_min_support(self):
        # min_support=3 — no sub-tree will appear in 3 distinct programs.
        mem = ProceduralMemory(min_support=3)
        mem.add("a", ("rotate", ("identity",), 1))
        mem.add("b", ("rotate", ("identity",), 1))
        with self.assertRaises(LiftError):
            mem.lift()


class TestPresets(unittest.TestCase):

    def test_preset_has_three_named_programs(self):
        mem = ProceduralMemory.preset()
        self.assertEqual(len(mem), 3)
        for n in ("identity_program", "mirror_program", "flip_v_program"):
            self.assertIn(n, mem)


if __name__ == "__main__":
    unittest.main()