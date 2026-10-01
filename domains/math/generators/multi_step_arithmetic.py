"""Multi-step arithmetic generator.

Generates three-step integer arithmetic chains presented as a natural-language
question, e.g.::

    "Start with 5. Multiply by 4, then subtract 7, then add 9. What is the
    final number?"

Each chain is exactly three operations from ``{+, -, *}`` chosen so the final
answer is a non-negative integer that fits inside a 32-bit signed range. The
intermediate values are not constrained to be non-negative — only the *final*
answer is — so chains may temporarily dip below zero (that is fine for the
``subtract`` operation).

Parametric controls
-------------------
``n_train``        number of training pairs (default 3).
``min_operand``    smallest operand (default 1).
``max_operand``    largest operand  (default 20).
``answer_max``     upper bound for the final answer (default 1_000_000).

The seed/parameters determine the operand values and operation choices.
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

OP_WORDS = {
    "+": "add",
    "-": "subtract",
    "*": "multiply by",
}
OPS = ("+", "-", "*")


def _phrase_chain(start: int, op1: str, x: int, op2: str, y: int, op3: str, z: int) -> str:
    return (
        f"Start with {start}. {OP_WORDS[op1]} {x}, then {OP_WORDS[op2]} {y}, "
        f"then {OP_WORDS[op3]} {z}. What is the final number?"
    )


def _apply(prev: int, op: str, n: int) -> int:
    if op == "+":
        return prev + n
    if op == "-":
        return prev - n
    return prev * n  # "*"


def _build_pair(rng, params: Dict[str, Any]) -> Dict[str, str]:
    """Build one ``{input, output}`` pair from a ``random.Random``."""
    min_op = int(params.get("min_operand", DEFAULT_MIN_OPERAND))
    max_op = int(params.get("max_operand", 20))
    answer_max = int(params.get("answer_max", 1_000_000))

    # Sample a chain whose final answer stays within bounds. A small retry loop
    # is enough because the operands are small.
    for _ in range(200):
        start = rng.randint(min_op, max_op)
        ops: List[str] = [OPS[rng.randrange(len(OPS))] for _ in range(3)]
        vals: List[int] = [
            rng.randint(min_op, max_op),
            rng.randint(min_op, max_op),
            rng.randint(min_op, max_op),
        ]
        v = start
        for op, n in zip(ops, vals):
            v = _apply(v, op, n)
        if 0 <= v <= answer_max:
            return {
                "input": _phrase_chain(start, ops[0], vals[0], ops[1], vals[1], ops[2], vals[2]),
                "output": int_to_text(v),
            }

    # Fallback to a guaranteed-valid trivial chain.
    return {
        "input": _phrase_chain(1, "+", 1, "+", 1, "+", 1),
        "output": int_to_text(4),
    }


def generate(public_seed: Any, private_seed: Any, **params: Any) -> Dict[str, Any]:
    """Generate a three-step arithmetic chain task."""
    n_train = int(params.get("n_train", 3))

    public_rng = make_rng(combined_seed("multi_step_arithmetic", public_seed, params))
    train = [_build_pair(public_rng, params) for _ in range(n_train)]

    private_rng = make_rng(combined_seed("multi_step_arithmetic", private_seed, params))
    test = [_build_pair(private_rng, params)]

    task = {"train": train, "test": test}
    envelope = {
        "generator": "multi_step_arithmetic",
        "public_seed": public_seed,
        "private_seed": private_seed,
        "parameters": dict(params),
        "task": task,
    }
    validate_math_envelope(envelope, require_test_output=True)
    return envelope


__all__ = ["generate"]
