"""Math task generators.

Public API:

    from generators import GENERATORS, generate_task

Every generator exposes ``generate(public_seed, private_seed, **kwargs)``
returning a math task dict (see ``core.validate_math_task``).
"""
from __future__ import annotations

from typing import Any, Callable, Dict

from .core import (  # noqa: F401
    MathTaskError,
    UNIT_FAMILIES,
    apply_conversion,
    combined_seed,
    int_to_text,
    make_rng,
    validate_math_task,
)
from . import arithmetic_word_problems, multi_step_arithmetic, unit_conversion  # noqa: F401

TaskFn = Callable[..., Dict[str, Any]]

GENERATORS: Dict[str, TaskFn] = {
    "arithmetic_word_problems": arithmetic_word_problems.generate,
    "multi_step_arithmetic": multi_step_arithmetic.generate,
    "unit_conversion": unit_conversion.generate,
}


def generate_task(name: str, public_seed: Any, private_seed: Any, **kwargs: Any) -> Dict[str, Any]:
    """Dispatch to the named generator with seeds and parameters."""
    if name not in GENERATORS:
        raise KeyError(
            f"Unknown math generator '{name}'. Known: {sorted(GENERATORS)}"
        )
    return GENERATORS[name](public_seed, private_seed, **kwargs)


__all__ = [
    "GENERATORS",
    "generate_task",
    "validate_math_task",
    "MathTaskError",
    "UNIT_FAMILIES",
    "apply_conversion",
    "combined_seed",
    "int_to_text",
    "make_rng",
]
