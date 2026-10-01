"""Conformance test for A3S SPEC §4 — Task format."""
from __future__ import annotations

import json
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_THIS, ".."))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "..", "01-task-generator"))

from reference.task_format import (  # noqa: E402
    A3SValidationError, dump_task, parse_task, validate_task,
)


def _valid_task() -> dict:
    """Build a minimal-valid A3S task for fixtures."""
    return {
        "generator":           "fill_enclosed",
        "generator_signature": "0" * 64,
        "public_seed":         "pub",
        "private_seed":        "priv",
        "parameters":          {"n_shapes": 1},
        "task": {
            "train": [
                {"input": [[0, 0], [0, 0]], "output": [[0, 0], [0, 0]]},
            ],
            "test": [
                {"input": [[0, 0], [0, 0]], "output": [[0, 0], [0, 0]]},
            ],
        },
    }


class TestTaskFormat(unittest.TestCase):
    """SPEC §4 — required fields, grid range, train/test shape parity."""

    def test_valid_task_passes(self):
        """A minimal-valid task MUST validate without error."""
        validate_task(_valid_task())  # should not raise

    def test_missing_top_level_field_raises(self):
        """A task missing any of the §4 REQUIRED fields MUST be rejected."""
        t = _valid_task()
        del t["generator_signature"]
        with self.assertRaises(A3SValidationError) as ctx:
            validate_task(t)
        self.assertIn("generator_signature", str(ctx.exception))

    def test_generator_signature_must_be_hex_sha256(self):
        """generator_signature MUST be lowercase hex 64 chars (SPEC §4.1)."""
        t = _valid_task()
        t["generator_signature"] = "not-a-hash"
        with self.assertRaises(A3SValidationError):
            validate_task(t)

    def test_seeds_must_be_strings(self):
        """public_seed/private_seed MUST be strings, not ints."""
        t = _valid_task()
        t["public_seed"] = 42
        with self.assertRaises(A3SValidationError):
            validate_task(t)

    def test_train_must_be_non_empty_list(self):
        """task.train MUST be a non-empty list (SPEC §4.1)."""
        t = _valid_task()
        t["task"]["train"] = []
        with self.assertRaises(A3SValidationError):
            validate_task(t)

    def test_test_must_have_exactly_one_pair(self):
        """A3S v1 freezes single-test tasks (SPEC §4.1)."""
        t = _valid_task()
        t["task"]["test"].append(t["task"]["test"][0])
        with self.assertRaises(A3SValidationError):
            validate_task(t)

    def test_grid_values_must_be_in_range(self):
        """Cells MUST be integers in [0, 9] (SPEC §4.1, ARC convention)."""
        t = _valid_task()
        t["task"]["train"][0]["input"][0][0] = 99  # out of range
        with self.assertRaises(A3SValidationError):
            validate_task(t)

    def test_input_output_shape_must_match(self):
        """Within a pair, input and output MUST share shape."""
        t = _valid_task()
        t["task"]["train"][0]["output"] = [[0, 0, 0], [0, 0, 0]]  # 2x3 vs 2x2
        with self.assertRaises(A3SValidationError):
            validate_task(t)

    def test_serialization_roundtrip(self):
        """dump_task + parse_task MUST be lossless and canonical."""
        t = _valid_task()
        text = dump_task(t)
        # Sorted keys: 'generator' must come before 'parameters'
        self.assertLess(text.index('"generator"'), text.index('"parameters"'))
        t2 = parse_task(text)
        validate_task(t2)
        self.assertEqual(t2, t)

    def test_real_example_task_validates(self):
        """A real example task from examples/task_family MUST validate."""
        path = os.path.join(_ROOT, "examples", "task_family",
                            "examples", "task_01.json")
        if os.path.exists(path):
            with open(path) as fh:
                task = parse_task(fh.read())
            validate_task(task)


if __name__ == "__main__":
    unittest.main()
