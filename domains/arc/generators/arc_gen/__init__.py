"""Procedural ARC task generator package.

Public API:

    from arc_gen import GENERATORS, generate_task
    from arc_gen.core import grid_shape, draw_rect, rotate_grid, ...
    from generators import (
        fill_enclosed,
        rotate_largest,
        count_colors,
        symmetry_complete,
    )

Every generator exposes the same `generate(public_seed, private_seed, **kwargs)`
signature returning an ARC task dict with `train` and `test` lists.
"""

from .core import (  # noqa: F401
    ARCError,
    clone_grid,
    draw_rect,
    fill_rect,
    flood_fill,
    grid_shape,
    make_rng,
    rotate_grid,
    reflect_grid,
    transpose_grid,
    count_color_cells,
    find_components,
    blank_grid,
    sample_palette,
    validate_arc_task,
)

from .registry import GENERATORS, generate_task  # noqa: F401

__all__ = ["GENERATORS", "generate_task", "validate_arc_task"]