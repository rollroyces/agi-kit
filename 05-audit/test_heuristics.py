"""Unit tests for `heuristics.py` and `audit.py`.

Run with:
    python -m unittest test_heuristics.py
"""
from __future__ import annotations

import unittest

from heuristics import (
    HEURISTICS,
    background_swap_heuristic,
    diagonal_replicate_heuristic,
    identity_heuristic,
    largest_object_heuristic,
    mirror_heuristic,
    palette_invert_heuristic,
    palette_majority_heuristic,
    single_color_fill_heuristic,
)
from audit import _exact_match, audit_task, audit_tasks


def _pairs(*pairs):
    """Convenience: ((in, out), (in, out), ...) -> [(in, out), ...]."""
    return list(pairs)


class TestHeuristics(unittest.TestCase):
    def test_identity(self):
        grid = [[1, 2], [3, 4]]
        out = identity_heuristic([], grid)
        self.assertEqual(out, grid)
        # must be a copy, not the same list
        self.assertIsNot(out, grid)
        self.assertIsNot(out[0], grid[0])

    def test_palette_majority(self):
        grid = [[0, 0, 1], [0, 2, 0], [0, 0, 0]]
        out = palette_majority_heuristic([], grid)
        self.assertEqual(out, [[0] * 3] * 3)
        # most common color = 0
        self.assertEqual(out[0][0], 0)

    def test_mirror(self):
        grid = [[1, 2, 3], [4, 5, 6]]
        out = mirror_heuristic([], grid)
        self.assertEqual(out, [[3, 2, 1], [6, 5, 4]])

    def test_largest_object(self):
        grid = [
            [0, 0, 0, 0],
            [0, 7, 0, 7],  # two singletons of color 7
            [0, 7, 7, 0],  # + one 2-cell blob of color 7
            [0, 0, 0, 0],
        ]
        out = largest_object_heuristic([], grid)
        self.assertEqual(
            out,
            [
                [0, 0, 0, 0],
                [0, 7, 0, 0],
                [0, 7, 7, 0],
                [0, 0, 0, 0],
            ],
        )

    def test_background_swap(self):
        grid = [[0, 3, 0], [0, 0, 0], [3, 0, 3]]
        out = background_swap_heuristic([], grid)
        self.assertEqual(out, [[3, 0, 3], [3, 3, 3], [0, 3, 0]])

    def test_diagonal_replicate(self):
        grid = [[1, 2], [3, 4]]
        out = diagonal_replicate_heuristic([], grid)
        self.assertEqual(
            out,
            [
                [1, 2, 1, 2],
                [3, 4, 3, 4],
                [1, 2, 1, 2],
                [3, 4, 3, 4],
            ],
        )

    def test_single_color_fill(self):
        grid = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]  # 9 distinct colors
        out = single_color_fill_heuristic([], grid)
        self.assertEqual(out, [[9] * 3] * 3)
        # 2 distinct colors -> fill 2
        grid3 = [[1, 2, 1], [2, 1, 2]]
        self.assertEqual(single_color_fill_heuristic([], grid3), [[2, 2, 2], [2, 2, 2]])

    def test_palette_invert(self):
        grid = [[1, 2, 3], [4, 5, 6]]
        out = palette_invert_heuristic([], grid)
        self.assertEqual(out, [[9, 8, 7], [6, 5, 4]])
        # 0 <-> 9 boundary
        self.assertEqual(palette_invert_heuristic([], [[0]]), [[9]])
        self.assertEqual(palette_invert_heuristic([], [[9]]), [[1]])

    def test_heuristics_registered(self):
        # every documented heuristic must be present
        expected = {
            "identity",
            "palette_majority",
            "mirror",
            "largest_object",
            "background_swap",
            "diagonal_replicate",
            "single_color_fill",
            "palette_invert",
        }
        self.assertEqual(set(HEURISTICS), expected)
        self.assertGreaterEqual(len(HEURISTICS), 5)

    def test_train_pairs_ignored(self):
        # all heuristics must accept train_pairs and ignore them gracefully
        grid = [[1, 0, 1], [0, 1, 0]]
        dummy_train = _pairs(([[9]], [[8]]))
        for fn in HEURISTICS.values():
            out = fn(dummy_train, grid)
            self.assertIsNotNone(out)


class TestExactMatch(unittest.TestCase):
    def test_equal_grids(self):
        self.assertTrue(_exact_match([[1, 2], [3, 4]], [[1, 2], [3, 4]]))

    def test_shape_mismatch(self):
        self.assertFalse(_exact_match([[1, 2]], [[1, 2], [3, 4]]))

    def test_value_mismatch(self):
        self.assertFalse(_exact_match([[1, 2], [3, 4]], [[1, 2], [3, 5]]))

    def test_both_empty(self):
        self.assertTrue(_exact_match([], []))


class TestAudit(unittest.TestCase):
    def _task(self, task_id, train, test_in, test_out):
        return {
            "task_id": task_id,
            "train": [{"input": tin, "output": tout} for tin, tout in train],
            "test": [{"input": test_in, "output": test_out}],
        }

    def test_audit_flags_mirror_task(self):
        task = self._task(
            "t_mirror",
            train=[([[1, 0, 2], [0, 0, 1], [2, 1, 0]],
                    [[2, 0, 1], [1, 0, 0], [0, 1, 2]])],
            test_in=[[5, 0, 6], [0, 5, 0], [6, 0, 5]],
            test_out=[[6, 0, 5], [0, 5, 0], [5, 0, 6]],
        )
        result = audit_task(task)
        self.assertTrue(result["trivially_solvable"])
        self.assertIn("mirror", result["solvers_hit"])

    def test_audit_does_not_flag_composite_rule(self):
        # rotate + shift: no single shallow heuristic should match.
        def _rot90(g):
                return [[g[len(g) - 1 - r][c] for r in range(len(g))] for c in range(len(g[0]))]
        def _shift(g, k=3):
                return [[(c + k) % 10 for c in row] for row in g]
        test_in = [[1, 2], [3, 4]]
        test_out = _shift(_rot90(test_in), 3)
        task = self._task("t_rot_shift", train=[([[1, 2]], [[1, 2]])], test_in=test_in, test_out=test_out)
        result = audit_task(task)
        self.assertFalse(result["trivially_solvable"])
        self.assertEqual(result["solvers_hit"], [])

    def test_audit_aggregate(self):
        tasks = [
            self._task(
                "easy_mirror",
                train=[([[1, 2, 3]], [[3, 2, 1]])],
                test_in=[[4, 5, 6]],
                test_out=[[6, 5, 4]],
            ),
            # "hard" task: rotate 90 deg + recolor (c+3)%10 — no shallow
            # heuristic reproduces this on a 2x2 grid.
            self._task(
                "hard",
                train=[([[1, 2]], [[1, 2]])],
                test_in=[[1, 2], [4, 5]],
                test_out=[[7, 4], [8, 4]],
            ),
        ]
        report = audit_tasks(tasks)
        self.assertEqual(report["n_tasks"], 2)
        self.assertEqual(report["n_trivially_solvable"], 1)
        self.assertIn("mirror", report["per_heuristic_hits"])
        self.assertEqual(report["per_heuristic_hits"]["mirror"], 1)
        self.assertEqual(report["per_heuristic_total"]["mirror"], 2)


if __name__ == "__main__":
    unittest.main()