"""Symmetry completion generator.

Task semantics
---------------
The input shows one side of a bilaterally-symmetric pattern; the other side
(plus the axis itself) is filled with the background colour. The output
completes the symmetry by mirroring the populated half across the axis.

Two axis choices are supported:
  * ``vertical``   mirror left -> right across the middle column.
  * ``horizontal`` mirror top -> bottom across the middle row.

Parametric controls
-------------------
``axis``         ``"vertical"`` or ``"horizontal"`` (default: sampled per pair)
``grid_size``    (rows, cols); the perpendicular dimension is forced odd so
                 there is a clean central axis (default: sampled 5..9)

``public_seed`` drives every demo pair independently; ``private_seed`` drives
the held-out test pair.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from arc_gen.core import (
    BACKGROUND,
    Grid,
    blank_grid,
    combined_seed,
    grid_shape,
    make_rng,
    sample_palette,
    validate_arc_task,
)


def _odd(n: int) -> int:
    n = max(3, int(n))
    return n if n % 2 == 1 else n + 1


def _pick_axis(rng) -> str:
    return rng.choice(("vertical", "horizontal"))


def _build_pair(seed: Any, params: Dict[str, Any]) -> Dict[str, Grid]:
    rng = make_rng(combined_seed("symmetry_complete", seed, params))

    if "axis" in params:
        axis = params["axis"]
        if axis not in ("vertical", "horizontal"):
            axis = "vertical"
    else:
        axis = _pick_axis(rng)

    if "grid_size" in params:
        gs = params["grid_size"]
        rows, cols = int(gs[0]), int(gs[1])
    else:
        if axis == "vertical":
            rows = int(params.get("rows", rng.randint(5, 7)))
            cols = _odd(int(params.get("cols", rng.choice([7, 9]))))
        else:
            rows = _odd(int(params.get("rows", rng.choice([7, 9]))))
            cols = int(params.get("cols", rng.randint(5, 7)))

    # Choose a palette of up to 3 colours for the decoration.
    palette = sample_palette(rng, rng.randint(1, 3))

    density = float(params.get("density", 0.45))
    if not 0.0 < density < 1.0:
        density = 0.45

    input_grid = blank_grid(rows, cols)
    output_grid = blank_grid(rows, cols)

    if axis == "vertical":
        mid = cols // 2
        for r in range(rows):
            for c in range(mid):
                if rng.random() < density:
                    color = rng.choice(palette)
                    input_grid[r][c] = color
                    output_grid[r][c] = color
                    output_grid[r][cols - 1 - c] = color
    else:  # horizontal
        mid = rows // 2
        for r in range(mid):
            for c in range(cols):
                if rng.random() < density:
                    color = rng.choice(palette)
                    input_grid[r][c] = color
                    output_grid[r][c] = color
                    output_grid[rows - 1 - r][c] = color

    # Edge case: an entirely-empty input would not actually demonstrate the
    # transformation. Re-roll in that case (cheap, deterministic).
    if not any(cell != BACKGROUND for row in input_grid for cell in row):
        return _build_pair(seed, params)

    return {"input": input_grid, "output": output_grid}


def generate(public_seed: Any, private_seed: Any, **params: Any) -> Dict[str, Any]:
    """Generate a symmetry-completion task."""
    n_train = int(params.get("n_train", 3))
    train = [_build_pair(f"{public_seed}-{i}", params) for i in range(n_train)]
    test = [_build_pair(private_seed, params)]

    task = {"train": train, "test": test}
    validate_arc_task(task, require_test_output=True)
    return task