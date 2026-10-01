"""Arithmetic word-problem generator.

Generates one-step word problems with three families of phrasing:

* ``add``     "If you have X apples and Y are added, how many do you have?"
* ``sub``     "If you have X apples and give away Y, how many are left?"
* ``div``     "X apples are split into Y equal groups. How many in each?"

The object noun ("apples", "books", "cookies", ...) is sampled from a fixed
list per generation. The seed/parameters determine numbers, the operation,
and the noun.

Parametric controls
-------------------
``n_train``        number of training pairs (default 3, ARC-style).
``min_operand``    smallest operand X (default 1).
``max_operand``    largest operand X  (default 99).
``min_y``          smallest operand Y (default 1).
``max_y``          largest operand Y  (default 99).
``operation``      one of ``{"add", "sub", "div"}``; default samples each pair.

All numbers are non-negative integers; ``sub`` clamps ``Y <= X`` and ``div``
ensures ``X`` is divisible by ``Y`` so the answer is an integer.

The generator is byte-deterministic given ``(public_seed, private_seed, **params)``.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .core import (
    DEFAULT_MAX_OPERAND,
    DEFAULT_MIN_OPERAND,
    int_to_text,
    make_rng,
    combined_seed,
    validate_math_envelope,
)

NOUNS = ["apples", "books", "cookies", "marbles", "pencils", "stickers"]
OPERATIONS = ("add", "sub", "div")


def _phrase_add(x: int, y: int, noun: str) -> str:
    return (
        f"If you have {x} {noun} and {y} more are added, "
        f"how many {noun} do you have in total?"
    )


def _phrase_sub(x: int, y: int, noun: str) -> str:
    return (
        f"If you have {x} {noun} and you give away {y}, "
        f"how many {noun} are left?"
    )


def _phrase_div(x: int, y: int, noun: str) -> str:
    return (
        f"{x} {noun} are split equally into {y} groups. "
        f"How many {noun} are in each group?"
    )


def _build_pair(rng, params: Dict[str, Any]) -> Dict[str, str]:
    """Build one ``{input, output}`` pair from a ``random.Random``."""
    min_x = int(params.get("min_operand", DEFAULT_MIN_OPERAND))
    max_x = int(params.get("max_operand", DEFAULT_MAX_OPERAND))
    min_y = int(params.get("min_y", 1))
    max_y = int(params.get("max_y", DEFAULT_MAX_OPERAND))

    op = params.get("operation")
    if op is None:
        op = OPERATIONS[rng.randrange(len(OPERATIONS))]
    if op not in OPERATIONS:
        raise ValueError(f"unknown operation: {op!r}")

    noun = rng.choice(NOUNS)

    if op == "add":
        x = rng.randint(min_x, max_x)
        y = rng.randint(min_y, max_y)
        answer = x + y
        text = _phrase_add(x, y, noun)
    elif op == "sub":
        x = rng.randint(min_x, max_x)
        y = rng.randint(min_y, min(max_y, x))  # clamp so x - y >= 0
        answer = x - y
        text = _phrase_sub(x, y, noun)
    else:  # div
        # Ensure x is divisible by y so the answer is an integer.
        y = max(1, rng.randint(min_y, max_y))
        # Pick a multiple of y inside [min_x, max_x].
        lo = max(1, (min_x + y - 1) // y)
        hi = max(1, max_x // y)
        k = rng.randint(lo, hi)
        x = y * k
        answer = k
        text = _phrase_div(x, y, noun)

    return {"input": text, "output": int_to_text(answer)}


def generate(public_seed: Any, private_seed: Any, **params: Any) -> Dict[str, Any]:
    """Generate a single-step arithmetic word-problem task.

    The envelope matches the A3S top-level shape (minus the grid-only
    ``generator_signature`` field — math is string-valued so that field is
    optional). The ``task`` body has ``train`` and ``test`` lists of string
    pairs, validated by ``core.validate_math_task``.
    """
    n_train = int(params.get("n_train", 3))

    public_rng = make_rng(combined_seed("arithmetic_word_problems", public_seed, params))
    train = [_build_pair(public_rng, params) for _ in range(n_train)]

    private_rng = make_rng(combined_seed("arithmetic_word_problems", private_seed, params))
    test = [_build_pair(private_rng, params)]

    task = {"train": train, "test": test}
    envelope = {
        "generator": "arithmetic_word_problems",
        "public_seed": public_seed,
        "private_seed": private_seed,
        "parameters": dict(params),
        "task": task,
    }
    validate_math_envelope(envelope, require_test_output=True)
    return envelope


__all__ = ["generate"]
