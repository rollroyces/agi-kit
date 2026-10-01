"""Name → callable registry. Used by the reasoner to look up primitives."""
from __future__ import annotations

from typing import Callable, Dict, List

from dsl import primitives as _p

# Order matters for stable iteration; keep it deterministic.
_ORDER: List[str] = [
    # Construction
    "make_grid", "from_list",
    # Inspection
    "shape", "color_at", "distinct_colors", "count_color", "background_color",
    # Geometry
    "rotate", "flip_h", "flip_v", "translate",
    # Object ops
    "connected_components", "largest_object", "bounding_box",
    "flood_fill", "enclosed_regions",
    # Palette
    "recolor", "invert_palette",
    # Higher-order
    "compose", "iterate", "zip_with", "identity", "apply_program",
]

_REGISTRY: Dict[str, Callable] = {
    "make_grid":            _p.make_grid,
    "from_list":            _p.from_list,
    "shape":                _p.shape,
    "color_at":             _p.color_at,
    "distinct_colors":      _p.distinct_colors,
    "count_color":          _p.count_color,
    "background_color":     _p.background_color,
    "rotate":               _p.rotate,
    "flip_h":               _p.flip_h,
    "flip_v":               _p.flip_v,
    "translate":            _p.translate,
    "connected_components": _p.connected_components,
    "largest_object":       _p.largest_object,
    "bounding_box":         _p.bounding_box,
    "flood_fill":           _p.flood_fill,
    "enclosed_regions":     _p.enclosed_regions,
    "recolor":              _p.recolor,
    "invert_palette":       _p.invert_palette,
    "compose":              _p.compose,
    "iterate":              _p.iterate,
    "zip_with":             _p.zip_with,
    "identity":             _p.identity,
    "apply_program":        _p.apply_program,
}


def registry() -> Dict[str, Callable]:
    """Return a fresh shallow copy of the registry."""
    return dict(_REGISTRY)


def get(name: str) -> Callable:
    """Look up a primitive by name; raise ``KeyError`` if unknown."""
    return _REGISTRY[name]


def all_names() -> List[str]:
    """Deterministic list of all registered primitive names."""
    return list(_ORDER)