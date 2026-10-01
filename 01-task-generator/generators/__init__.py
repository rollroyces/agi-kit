"""ARC task generators.

Each module exposes `generate(public_seed, private_seed, **kwargs) -> dict`
returning an ARC task. Importing the package registers them all in
`arc_gen.registry.GENERATORS`.
"""

from . import count_colors, fill_enclosed, rotate_largest, symmetry_complete  # noqa: F401

__all__ = ["fill_enclosed", "rotate_largest", "count_colors", "symmetry_complete"]