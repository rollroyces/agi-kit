"""Interpreter that turns a program AST into a callable.

Semantics
---------
An AST ``("name", arg1, arg2, ...)`` represents a *program* (a function from
a grid to some value). To run it on a grid, compile to a function first
(``compile_program``) and call that function.

The ``("identity",)`` zero-argument form is sugar for "the current execution
grid", i.e. ``lambda g: g``. It lets you write, e.g.,
``("rotate", ("identity",), 1)`` without explicitly threading the grid.

Composition
-----------
``("compose", f, g, ...)`` is itself a primitive whose arguments are *programs*
(not values). The interpreter compiles each child before calling ``compose``,
which returns a new program that runs the parts sequentially.

Mixing literal values and sub-programs
--------------------------------------
Any non-AST, non-list/tuple child is treated as a literal. AST children are
recursively compiled to functions and threaded through the grid.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

from dsl.registry import get as _get
from dsl.primitives import compose as _compose_primitive


def _literal_const(value: Any) -> Callable[[Any], Any]:
    return lambda _g, _v=value: _v


def _identity_prog() -> Callable[[Any], Any]:
    return lambda g: copy.deepcopy(g)


def compile_program(node: Any) -> Callable[[Any], Any]:
    """Compile an AST to a function ``grid -> result``."""
    if callable(node):
        return node
    if not isinstance(node, tuple) or not node:
        raise TypeError(f"interpreter: invalid AST node {node!r}")
    name = node[0]
    if name == "identity" and len(node) == 1:
        return _identity_prog()
    if name == "compose":
        # Compose is special. Its children are *programs*, not values; we
        # compile each child before passing to the primitive.
        children = node[1:]
        if not children:
            raise TypeError("interpreter: compose() needs at least 1 argument")
        compiled = [compile_program(c) if isinstance(c, tuple) else c for c in children]
        composed = _compose_primitive(*compiled)
        return lambda grid: composed(grid)
    fn = _get(name)
    arg_progs = []
    for child in node[1:]:
        if isinstance(child, tuple):
            arg_progs.append(compile_program(child))
        elif callable(child):
            arg_progs.append(child)
        else:
            arg_progs.append(_literal_const(child))
    return lambda grid: fn(*(p(grid) for p in arg_progs))


def execute(node: Any, grid: Any) -> Any:
    """Compile-then-run: execute an AST on a grid."""
    return compile_program(node)(grid)