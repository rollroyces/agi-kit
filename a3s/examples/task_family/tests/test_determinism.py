"""Conformance: SPEC §5.1 — byte-deterministic generation."""
from __future__ import annotations

import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_BUNDLE = os.path.abspath(os.path.join(_THIS, ".."))
sys.path.insert(0, _BUNDLE)

from generator import FillEnclosedGenerator  # noqa: E402


class TestDeterminism(unittest.TestCase):
    """SPEC §5.1: identical seeds MUST produce identical JSON."""

    def test_two_runs_with_same_seeds_match_bytewise(self):
        gen = FillEnclosedGenerator()
        t1 = gen.generate("pub", "priv", n_shapes=2)
        t2 = gen.generate("pub", "priv", n_shapes=2)
        self.assertEqual(
            json.dumps(t1, sort_keys=True),
            json.dumps(t2, sort_keys=True),
        )

    def test_different_seeds_yield_different_tasks(self):
        gen = FillEnclosedGenerator()
        t1 = gen.generate("pub-a", "priv-a", n_shapes=2)
        t2 = gen.generate("pub-b", "priv-b", n_shapes=2)
        self.assertNotEqual(
            json.dumps(t1, sort_keys=True),
            json.dumps(t2, sort_keys=True),
        )

    def test_envelope_carries_signature(self):
        gen = FillEnclosedGenerator()
        task = gen.generate("p", "q")
        self.assertEqual(task["generator_signature"], gen.signature)
        self.assertEqual(len(task["generator_signature"]), 64)


if __name__ == "__main__":
    unittest.main()
