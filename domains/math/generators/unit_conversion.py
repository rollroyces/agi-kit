"""Unit-conversion generator.

Generates one-step unit-conversion problems of the form::

    "5 meters is how many centimeters?"
    "250 grams is how many kilograms?"
    "3 hours is how many minutes?"

The answer is the numeric result in the target unit. For m↔cm, kg↔g, and
hours↔minutes, every answer is a clean integer (we pick operand values so
that this holds: e.g. only meter values that are whole-centimeter numbers,
only gram values that are whole-kilogram-friendly powers of 1000, only
hour values that are integer minutes).

Parametric controls
-------------------
``n_train``        number of training pairs (default 3).
``family``         one of ``{"length", "mass", "time"}``; default samples each
                   pair from any family.
``min_value``      smallest whole-unit value (default 1).
``max_value``      largest whole-unit value (default 100).

The seed/parameters determine which family is used for each pair.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .core import (
    DEFAULT_MAX_OPERAND,
    DEFAULT_MIN_OPERAND,
    UNIT_FAMILIES,
    apply_conversion,
    int_to_text,
    make_rng,
    combined_seed,
    validate_math_envelope,
)

# (from_unit, to_unit, family)
DIRECTIONS: List[Tuple[str, str, str]] = [
    ("meters", "centimeters", "length"),
    ("centimeters", "meters", "length"),
    ("kilograms", "grams", "mass"),
    ("grams", "kilograms", "mass"),
    ("hours", "minutes", "time"),
    ("minutes", "hours", "time"),
]


def _phrase(value: int, from_unit: str, to_unit: str) -> str:
    return f"{value} {from_unit} is how many {to_unit}?"


def _eligible_values(from_unit: str, to_unit: str,
                     min_value: int, max_value: int) -> List[int]:
    """Pick operand values that yield an integer answer in ``to_unit``."""
    factor = UNIT_FAMILIES[(from_unit, to_unit)]
    candidates: List[int] = []
    # Integer answers mean ``value * factor`` is an integer; that holds when
    # the factor is 1 / N for some integer N (centimeters->meters and minutes->hours),
    # so we additionally require ``value`` to be a multiple of N. We pick the
    # smallest N >= 1 such that ``1/N == factor`` (or its reciprocal).
    if factor >= 1:
        # value * factor is automatically an integer for any integer value.
        return list(range(min_value, max_value + 1))
    # factor < 1: factor = 1/N where N = round(1 / factor)
    n = round(1.0 / factor)
    if abs(1.0 / n - factor) > 1e-9:
        return []  # not a clean reciprocal; skip
    for k in range(1, max_value // n + 1):
        candidates.append(n * k)
    return [v for v in candidates if v >= min_value]


def _build_pair(rng, params: Dict[str, Any]) -> Dict[str, str]:
    """Build one ``{input, output}`` pair from a ``random.Random``."""
    min_value = int(params.get("min_value", DEFAULT_MIN_OPERAND))
    max_value = int(params.get("max_value", 100))
    family = params.get("family")  # str or None

    directions = [d for d in DIRECTIONS if family is None or d[2] == family]
    if not directions:
        raise ValueError(f"unknown family: {family!r}")

    # Try a few directions; pick the first one that has eligible values.
    rng.shuffle(directions)
    for from_unit, to_unit, _ in directions:
        eligible = _eligible_values(from_unit, to_unit, min_value, max_value)
        if not eligible:
            continue
        value = rng.choice(eligible)
        answer = apply_conversion(value, from_unit, to_unit)
        if answer == int(answer):
            return {
                "input": _phrase(value, from_unit, to_unit),
                "output": int_to_text(int(answer)),
            }

    # Fallback: a guaranteed-valid "5 meters = 500 centimeters".
    return {"input": _phrase(5, "meters", "centimeters"), "output": "500"}


def generate(public_seed: Any, private_seed: Any, **params: Any) -> Dict[str, Any]:
    """Generate a unit-conversion task."""
    n_train = int(params.get("n_train", 3))

    public_rng = make_rng(combined_seed("unit_conversion", public_seed, params))
    train = [_build_pair(public_rng, params) for _ in range(n_train)]

    private_rng = make_rng(combined_seed("unit_conversion", private_seed, params))
    test = [_build_pair(private_rng, params)]

    task = {"train": train, "test": test}
    envelope = {
        "generator": "unit_conversion",
        "public_seed": public_seed,
        "private_seed": private_seed,
        "parameters": dict(params),
        "task": task,
    }
    validate_math_envelope(envelope, require_test_output=True)
    return envelope


__all__ = ["generate"]
