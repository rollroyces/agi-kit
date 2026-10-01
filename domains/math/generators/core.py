"""Shared utilities for math task generators.

Math tasks are ``input -> output`` mappings over plain strings (word problems).
This module provides:

* ``make_rng(seed)`` — deterministic ``random.Random`` like the ARC equivalent.
* ``combined_seed(*parts)`` — stable 64-bit hash combining multiple parts.
* ``validate_math_task(task)`` — schema validation for math tasks. Unlike
  ARC, math tasks carry string ``input`` and string ``output`` (the answer,
  parsed as a number by the grader).

Conventions
-----------
* ``generator`` and ``public_seed`` / ``private_seed`` are strings.
* ``parameters`` is a JSON object (``dict``).
* ``task`` has ``train`` and ``test`` lists of ``{"input": str, "output": str}``.
* Numbers in math problems are non-negative integers (answers fit in a
  Python ``int``); units are SI-style (meters, centimeters, kilograms, grams,
  hours, minutes) with simple base-10 or base-60 scaling.
"""
from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Tuple


# Numeric / textual sanity bounds. Generators may exceed these when the
# parameter set explicitly says so (e.g. multi-step chains).
DEFAULT_MIN_OPERAND = 1
DEFAULT_MAX_OPERAND = 99


class MathTaskError(ValueError):
    """Raised when a math task does not conform to the expected schema."""


# ---------------------------------------------------------------------------
# RNG / seeding (mirrors arc_gen.core.make_rng / combined_seed)
# ---------------------------------------------------------------------------

def make_rng(seed: Any) -> random.Random:
    """Return a deterministic ``random.Random`` from an arbitrary hashable seed."""
    rng = random.Random()
    try:
        rng.seed(seed, version=2)
    except TypeError:
        rng.seed(str(seed), version=2)
    return rng


def combined_seed(*parts: Any) -> int:
    """Combine multiple seed parts into a stable 64-bit integer."""
    h = 0x9E3779B97F4A7C15
    for p in parts:
        s = str(p).encode("utf-8")
        for b in s:
            h ^= b
            h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

REQUIRED_ENVELOPE_KEYS = (
    "generator",
    "public_seed",
    "private_seed",
    "parameters",
    "task",
)


def validate_math_task_body(task: Any, *, require_test_output: bool = True) -> None:
    """Validate the *inner* task body — the ``task.task`` dict.

    This is the ``{"train": [...], "test": [...]}`` shape that mirrors the ARC
    inner shape but uses string ``input`` and string ``output`` instead of
    grids. The top-level A3S envelope is validated separately by
    :func:`validate_math_envelope`.
    """
    if not isinstance(task, dict):
        raise MathTaskError("task body must be a dict")
    if "train" not in task or "test" not in task:
        raise MathTaskError("task body must contain both 'train' and 'test'")
    if not isinstance(task["train"], list) or not task["train"]:
        raise MathTaskError("'train' must be a non-empty list")
    if not isinstance(task["test"], list) or len(task["test"]) != 1:
        raise MathTaskError("'test' must contain exactly one pair")

    for i, pair in enumerate(task["train"]):
        _validate_pair(pair, i, "train", require_output=True)
    for i, pair in enumerate(task["test"]):
        _validate_pair(pair, i, "test", require_output=require_test_output)


def validate_math_envelope(task: Any, *, require_test_output: bool = True) -> None:
    """Validate the full A3S-shaped math task (envelope + body).

    Raises :class:`MathTaskError` on any structural problem.
    """
    if not isinstance(task, dict):
        raise MathTaskError("task must be a dict")
    for key in REQUIRED_ENVELOPE_KEYS:
        if key not in task:
            raise MathTaskError(f"task missing required top-level field '{key}'")

    if not isinstance(task["generator"], str) or not task["generator"]:
        raise MathTaskError("'generator' must be a non-empty string")
    if not isinstance(task["public_seed"], str):
        raise MathTaskError("'public_seed' must be a string")
    if not isinstance(task["private_seed"], str):
        raise MathTaskError("'private_seed' must be a string")
    if not isinstance(task["parameters"], dict):
        raise MathTaskError("'parameters' must be a dict")

    validate_math_task_body(task["task"], require_test_output=require_test_output)


# Backwards-compatibility alias — older callers used ``validate_math_task`` to
# mean "the inner body". Keep it but route to the body validator.
def validate_math_task(task: Any, *, require_test_output: bool = True) -> None:
    """Validate the inner task body (train/test content)."""
    validate_math_task_body(task, require_test_output=require_test_output)


def _validate_pair(pair: Any, idx: int, section: str, *, require_output: bool) -> None:
    if not isinstance(pair, dict):
        raise MathTaskError(f"{section}[{idx}] must be a dict")
    if not isinstance(pair.get("input"), str):
        raise MathTaskError(f"{section}[{idx}].input must be a string")
    if require_output and not isinstance(pair.get("output"), str):
        raise MathTaskError(f"{section}[{idx}].output must be a string")


# ---------------------------------------------------------------------------
# Helpers used by generators
# ---------------------------------------------------------------------------

def task_to_jsonable(task: Dict[str, Any]) -> Dict[str, Any]:
    """Return a JSON-safe deep copy of ``task``."""
    return json.loads(json.dumps(task))


def int_to_text(n: int) -> str:
    """Canonical text form for a numeric answer (the grader parses this back)."""
    return str(int(n))


# A handful of unit names used by the unit-conversion generator.
# Maps (from_unit, to_unit) -> scale factor such that ``value * factor`` is the
# answer in ``to_unit``. (meters, centimeters): 100. (kilograms, grams): 1000.
# (hours, minutes): 60. Reverse directions (e.g. cm -> m) yield a fractional
# factor; we pre-compute both directions so the generator can pick.
UNIT_FAMILIES: Dict[Tuple[str, str], float] = {
    ("meters", "centimeters"): 100.0,
    ("centimeters", "meters"): 0.01,
    ("kilograms", "grams"): 1000.0,
    ("grams", "kilograms"): 0.001,
    ("hours", "minutes"): 60.0,
    ("minutes", "hours"): 1.0 / 60.0,
}


def apply_conversion(value: int, from_unit: str, to_unit: str) -> float:
    """Return ``value`` converted from ``from_unit`` to ``to_unit``.

    Raises ``MathTaskError`` if the pair is not in ``UNIT_FAMILIES``.
    """
    key = (from_unit, to_unit)
    if key not in UNIT_FAMILIES:
        raise MathTaskError(f"unsupported conversion {from_unit} -> {to_unit}")
    return float(value) * UNIT_FAMILIES[key]


__all__ = [
    "MathTaskError",
    "make_rng",
    "combined_seed",
    "validate_math_task",
    "validate_math_task_body",
    "validate_math_envelope",
    "task_to_jsonable",
    "int_to_text",
    "UNIT_FAMILIES",
    "apply_conversion",
    "DEFAULT_MIN_OPERAND",
    "DEFAULT_MAX_OPERAND",
]
