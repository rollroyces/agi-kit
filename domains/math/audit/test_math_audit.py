"""Unit tests for the math audit heuristics and harness.

Run with: ``python -m unittest test_math_audit.py`` from this directory.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from audit import audit_task, audit_tasks  # noqa: E402
from heuristics import (  # noqa: E402
    HEURISTICS,
    echo_first_number,
    identity_echo,
    random_guess,
    return_count,
    return_max,
    return_zero,
)


class TestHeuristics(unittest.TestCase):

    def test_echo_first_number_basic(self):
        self.assertEqual(echo_first_number([], "If you have 7 apples."), "7")

    def test_echo_first_number_picks_first_only(self):
        # Multiple integers: must return the *first*, not the largest.
        self.assertEqual(echo_first_number([], "3 then 10"), "3")

    def test_echo_first_number_no_int_returns_zero(self):
        self.assertEqual(echo_first_number([], "no numbers here"), "0")

    def test_return_zero_always_zero(self):
        self.assertEqual(return_zero([], "anything"), "0")
        self.assertEqual(return_zero([], ""), "0")

    def test_return_max_picks_largest(self):
        self.assertEqual(return_max([], "3 then 10 then 5"), "10")

    def test_return_max_handles_negatives(self):
        self.assertEqual(return_max([], "a -5 and -10"), "-5")

    def test_return_count_counts_integers(self):
        self.assertEqual(return_count([], "1 2 3 4"), "4")
        self.assertEqual(return_count([], "no numbers"), "0")

    def test_random_guess_is_deterministic(self):
        a = random_guess([], "hello world")
        b = random_guess([], "hello world")
        self.assertEqual(a, b)

    def test_random_guess_is_in_range(self):
        for _ in range(50):
            v = int(random_guess([], f"seed-{_}"))
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 100)

    def test_identity_echo_returns_input(self):
        self.assertEqual(identity_echo([], "anything"), "anything")

    def test_heuristics_registered(self):
        expected = {
            "echo_first_number",
            "return_zero",
            "return_max",
            "return_count",
            "random_guess",
            "identity_echo",
        }
        self.assertEqual(set(HEURISTICS), expected)
        self.assertGreaterEqual(len(HEURISTICS), 5)

    def test_train_pairs_ignored(self):
        # Heuristics must accept train_pairs and ignore them.
        text = "If you have 8 marbles and give away 3, how many remain?"
        for fn in HEURISTICS.values():
            out = fn([("ignored", "ignored")], text)
            self.assertIsInstance(out, str)


class TestAuditTask(unittest.TestCase):

    def _task(self, task_id: str, train, test_in: str, test_out: str) -> dict:
        return {
            "task_id": task_id,
            "train": [{"input": tin, "output": tout} for tin, tout in train],
            "test":  [{"input": test_in, "output": test_out}],
        }

    def test_first_number_trivial_task_is_flagged(self):
        # A task whose answer is the first integer in the input.
        task = self._task(
            "first_number",
            train=[("If you have 2 apples, how many do you have?", "2")],
            test_in="If you have 9 apples, how many do you have?",
            test_out="9",
        )
        result = audit_task(task)
        self.assertTrue(result["trivially_solvable"])
        self.assertIn("echo_first_number", result["solvers_hit"])

    def test_zero_heuristic_only_solves_zero_answers(self):
        # A task whose answer is 0 — only return_zero should hit.
        task = self._task(
            "zero",
            train=[("Give me 0 cookies.", "0")],
            test_in="Give me 0 books.",
            test_out="0",
        )
        result = audit_task(task)
        self.assertTrue(result["trivially_solvable"])
        self.assertIn("return_zero", result["solvers_hit"])

    def test_non_trivial_task_not_flagged(self):
        # 7 apples minus 3 = 4; the first integer is 7, but the answer is 4.
        task = self._task(
            "subtraction",
            train=[("If you have 5 apples and give away 2, how many remain?", "3")],
            test_in="If you have 7 apples and give away 3, how many remain?",
            test_out="4",
        )
        result = audit_task(task)
        # echo_first_number returns 7 (wrong), so task should not be trivially solvable.
        self.assertFalse(result["trivially_solvable"])
        self.assertEqual(result["solvers_hit"], [])


class TestAuditAggregate(unittest.TestCase):

    def _task(self, task_id: str, train, test_in: str, test_out: str) -> dict:
        return {
            "task_id": task_id,
            "train": [{"input": tin, "output": tout} for tin, tout in train],
            "test":  [{"input": test_in, "output": test_out}],
        }

    def test_aggregate_counts(self):
        tasks = [
            self._task("easy_zero",
                       train=[("zero", "0")],
                       test_in="zero", test_out="0"),
            self._task("hard_sub",
                       train=[("have 5 give 2", "3")],
                       test_in="have 7 give 3", test_out="4"),
        ]
        report = audit_tasks(tasks)
        self.assertEqual(report["n_tasks"], 2)
        self.assertEqual(report["n_trivially_solvable"], 1)
        # return_zero should hit exactly once.
        self.assertEqual(report["per_heuristic_hits"]["return_zero"], 1)
        self.assertEqual(report["per_heuristic_total"]["return_zero"], 2)


if __name__ == "__main__":
    unittest.main()
