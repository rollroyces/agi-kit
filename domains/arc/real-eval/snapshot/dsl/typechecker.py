"""Lightweight static type checker for DSL programs.

A program AST is a tree of ``("name", *children)`` tuples. The checker only
catches blatant shape mistakes (arity mismatch, unknown primitive) — it does
not perform full unification. Real DSLs in production use a MyPy-style checker;
the MVP keeps the signature simple to avoid the complexity cost.

Usage::

    ast = ("compose",
            ("rotate", ("identity",)),
            ("flip_h", ("identity",)))
    typecheck_program(ast)   # returns None; raises TypeError_ on failure.
"""
from __future__ import annotations

from typing import Any, Tuple

from dsl.registry import all_names, get as _get

# Arity table — primitives that take the grid as their first argument are
# treated as "grid operators" with arity = 1 + len(non-grid args). Pure
# inspectors/constructors have their own fixed arity.
_ARITY: dict[str, int] = {
    # Construction
    "make_grid": 3,            # (h, w, fill)
    "from_list": 1,            # (rows)
    # Inspection — return values, not grids
    "shape": 1,
    "color_at": 3,
    "distinct_colors": 1,
    "count_color": 2,
    "background_color": 1,
    # Geometry (operate on grid)
    "rotate": 2,               # grid + k
    "flip_h": 1,
    "flip_v": 1,
    "translate": 4,            # grid + dr + dc + fill
    # Object ops
    "connected_components": 2,
    "largest_object": 2,
    "bounding_box": 1,
    "flood_fill": 4,
    "enclosed_regions": 2,
    # Palette
    "recolor": 2,
    "invert_palette": 1,
    # Higher-order
    "compose": -1,             # variadic — accept any arity >= 1
    "iterate": 3,
    "zip_with": 3,
    "identity": 1,
    "apply_program": 2,
}


class TypeError_(Exception):
    """Raised by :func:`typecheck_program` on malformed input."""


def _walk(node: Any, depth: int = 0) -> None:
    if depth > 32:
        raise TypeError_("typecheck_program: program nesting exceeds 32 levels")
    if not isinstance(node, tuple) or not node:
        raise TypeError_(f"typecheck_program: node must be a non-empty tuple, got {node!r}")
    name = node[0]
    if not isinstance(name, str):
        raise TypeError_(f"typecheck_program: head must be str, got {name!r}")
    if name not in all_names():
        raise TypeError_(f"typecheck_program: unknown primitive {name!r}")
    # ``("identity",)`` is the 0-arg "this grid" form; allow it explicitly.
    if name == "identity" and len(node) == 1:
        return
    expected = _ARITY.get(name, 1)
    children = node[1:]
    if expected == -1:                # variadic
        if len(children) < 1:
            raise TypeError_(f"typecheck_program: {name}() needs at least 1 argument")
    else:
        if len(children) != expected:
            raise TypeError_(
                f"typecheck_program: {name}() expected {expected} args, got {len(children)}"
            )
    for child in children:
        # Allow plain Python literals (ints, strs, dicts, lists).
        if isinstance(child, (int, float, bool, str, dict, list)):
            continue
        _walk(child, depth + 1)


def typecheck_program(node: Any) -> None:
    """Raise ``TypeError_`` if ``node`` is not a well-formed program AST."""
    _walk(node, 0)