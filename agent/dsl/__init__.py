"""Minimal functional DSL for ARC grid tasks.

A primitive is a pure function ``f(grid, *args) -> grid`` (or for inspectors,
returns a small Python value). Programs are compositions of primitives assembled
by :mod:`reasoner.template_proposer`.

Public surface:
    :func:`get` returns a primitive by name.
    :func:`registry` returns the full ordered name → callable mapping.
    :func:`typecheck_program` runs the lightweight type checker on a program AST.
"""
from __future__ import annotations

from .multichannel import is_multichannel
from .primitives import (
    # Construction
    make_grid,
    from_list,
    # Inspection
    shape,
    color_at,
    distinct_colors,
    count_color,
    background_color,
    # Geometry
    rotate,
    flip_h,
    flip_v,
    translate,
    # Object ops
    connected_components,
    largest_object,
    bounding_box,
    flood_fill,
    enclosed_regions,
    # Palette
    recolor,
    invert_palette,
    # Higher-order
    compose,
    iterate,
    zip_with,
    identity,
    # Helpers (programs / closures)
    apply_program,
    # v2 multi-channel
    make_multichannel,
    extract_channel,
    combine_channels,
    project_luminance,
)
from .registry import registry, get, all_names
from .typechecker import typecheck_program, TypeError_

__all__ = [
    # Primitives
    "make_grid", "from_list",
    "shape", "color_at", "distinct_colors", "count_color", "background_color",
    "rotate", "flip_h", "flip_v", "translate",
    "connected_components", "largest_object", "bounding_box",
    "flood_fill", "enclosed_regions",
    "recolor", "invert_palette",
    "compose", "iterate", "zip_with", "identity", "apply_program",
    # v2 multi-channel
    "is_multichannel", "make_multichannel", "extract_channel",
    "combine_channels", "project_luminance",
    # Registry + typechecker
    "registry", "get", "all_names", "typecheck_program", "TypeError_",
]
