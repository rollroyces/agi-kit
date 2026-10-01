"""Math-specific DSL primitives.

These extend :mod:`agent.dsl.primitives` with three small utilities used by the
math reasoner and grader:

* :func:`parse_number`  — extract the first integer or float from a free-form
  text answer.
* :func:`safe_eval`     — safely evaluate a simple arithmetic expression
  containing ``+ - * /`` and parentheses.
* :func:`extract_template` — find ``{slot}``-style placeholders in a templated
  word problem (e.g. ``"If you have {x} apples ..."``).

The module is pure-functional: every function is deterministic and does not
mutate its inputs.
"""
from __future__ import annotations

import ast
import operator
import re
from typing import Dict, Optional


_BIN_OPS: Dict[type, object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: Dict[type, object] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_number(text: str) -> float:
    """Return the first integer or float found in ``text``.

    The first match is parsed as a ``float`` (so integer answers like ``"42"``
    come back as ``42.0``). Raises :class:`ValueError` if no number is found.

    >>> parse_number("The answer is 42.")
    42.0
    >>> parse_number("Approximately -3.14")
    -3.14
    """
    if not isinstance(text, str):
        raise ValueError(f"parse_number: expected str, got {type(text).__name__}")
    m = _NUMBER_RE.search(text)
    if m is None:
        raise ValueError(f"parse_number: no number in {text!r}")
    return float(m.group(0))


def safe_eval(expr: str) -> float:
    """Safely evaluate a simple arithmetic expression.

    Accepts ``+ - * / // % **`` and parentheses with numeric literals.
    Returns a ``float``. Rejects names, calls, comprehensions, attributes —
    anything other than a literal/arithmetic expression tree.

    >>> safe_eval("3 + 4 * 2")
    11.0
    >>> safe_eval("(1 + 2) ** 3")
    27.0
    """
    if not isinstance(expr, str) or not expr.strip():
        raise ValueError("safe_eval: empty expression")

    tree = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return float(node.value)
            raise ValueError(f"safe_eval: unsupported literal {node.value!r}")
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _BIN_OPS:
                raise ValueError(f"safe_eval: unsupported operator {op_type.__name__}")
            return float(_BIN_OPS[op_type](_eval(node.left), _eval(node.right)))
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _UNARY_OPS:
                raise ValueError(f"safe_eval: unsupported unary op {op_type.__name__}")
            return float(_UNARY_OPS[op_type](_eval(node.operand)))
        raise ValueError(f"safe_eval: disallowed node {type(node).__name__}")

    return _eval(tree)


_SLOT_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def extract_template(text: str) -> str:
    """Return ``text`` with each ``{slot}`` placeholder replaced by the slot
    name itself, so callers can see which slots are present.

    >>> extract_template("If you have {x} apples and {y} are added, how many?")
    'If you have x apples and y are added, how many?'
    """
    if not isinstance(text, str):
        raise ValueError(f"extract_template: expected str, got {type(text).__name__}")
    return _SLOT_RE.sub(lambda m: m.group(1), text)


def template_slots(text: str) -> Optional[list]:
    """Return the ordered list of ``{slot}`` names found in ``text``.

    Returns ``None`` if no slots are present (so callers can distinguish
    "no template" from "empty template").
    """
    slots = _SLOT_RE.findall(text)
    return slots or None


__all__ = ["parse_number", "safe_eval", "extract_template", "template_slots"]
