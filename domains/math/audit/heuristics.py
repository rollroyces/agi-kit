"""Shallow heuristic solvers for math word-problem tasks.

Each heuristic implements the signature::

    predict(train_pairs, test_input: str) -> str

Train pairs are passed for parity with the ARC audit harness, but the
heuristics here ignore them — they only inspect the test input. This is the
"trivial baseline" the audit flags: if any of them produces the correct
answer, the task is probably not testing reasoning.

The five heuristics are:

* :func:`echo_first_number`   — return the first integer found in the input.
* :func:`return_zero`         — always return ``"0"``.
* :func:`return_max`          — return the largest integer found in the input.
* :func:`return_count`        — return the count of integers in the input.
* :func:`random_guess`        — return a uniformly random integer in [0, 100].

The :data:`HEURISTICS` registry at the bottom of this module exposes all five.
"""
from __future__ import annotations

import random
import re
from typing import Any, Callable, Dict, List, Sequence, Tuple

Number = Any  # typically str (a textual answer)
TrainPair = Tuple[str, str]


_NUMBER_RE = re.compile(r"-?\d+")


def _ints(text: str) -> List[int]:
    """Extract every integer token from ``text`` (in document order)."""
    return [int(m.group(0)) for m in _NUMBER_RE.finditer(text)]


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

def echo_first_number(train_pairs: Sequence[TrainPair], test_input: str) -> str:
    """Return the first integer found in ``test_input`` as a string."""
    nums = _ints(test_input)
    if not nums:
        return "0"
    return str(nums[0])


def return_zero(train_pairs: Sequence[TrainPair], test_input: str) -> str:
    """Always return ``"0"``. Trivial baseline."""
    return "0"


def return_max(train_pairs: Sequence[TrainPair], test_input: str) -> str:
    """Return the largest integer found in ``test_input``."""
    nums = _ints(test_input)
    if not nums:
        return "0"
    return str(max(nums))


def return_count(train_pairs: Sequence[TrainPair], test_input: str) -> str:
    """Return the *count* of integer tokens found in ``test_input``."""
    nums = _ints(test_input)
    return str(len(nums))


def random_guess(train_pairs: Sequence[TrainPair], test_input: str) -> str:
    """Return a uniformly random integer in [0, 100].

    The random generator is seeded from ``test_input`` so the heuristic is
    deterministic for a given input — important for the audit harness
    reproducibility.
    """
    seed = sum(ord(c) for c in test_input)
    rng = random.Random(seed)
    return str(rng.randint(0, 100))


# Identity: echoes the test input verbatim. Useful as a sanity baseline.
def identity_echo(train_pairs: Sequence[TrainPair], test_input: str) -> str:
    """Return ``test_input`` unchanged. A degenerate baseline."""
    return test_input


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HEURISTICS: Dict[str, Callable[..., str]] = {
    "echo_first_number": echo_first_number,
    "return_zero":       return_zero,
    "return_max":        return_max,
    "return_count":      return_count,
    "random_guess":      random_guess,
    "identity_echo":     identity_echo,
}


def run_all(train_pairs: Sequence[TrainPair], test_input: str) -> Dict[str, str]:
    """Convenience: run every heuristic and return ``{name: prediction}``."""
    return {name: fn(train_pairs, test_input) for name, fn in HEURISTICS.items()}


__all__ = [
    "HEURISTICS",
    "echo_first_number",
    "return_zero",
    "return_max",
    "return_count",
    "random_guess",
    "identity_echo",
    "run_all",
]
