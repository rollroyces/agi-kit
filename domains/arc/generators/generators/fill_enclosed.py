"""Fill enclosed regions generator.

Task semantics
---------------
The input contains one or more rectangular *frames*: closed loops drawn with a
single non-background colour, surrounding a region of background cells that
does not touch the grid edge. The output is identical to the input except
that every enclosed hole is filled with a new colour.

Parametric controls
-------------------
``n_shapes``      number of frames to draw (default sampled 1..3 per pair)
``grid_size``     (rows, cols) of the output grid (default sampled per pair)

The ``public_seed`` controls shape geometry (the demonstration pairs); the
``private_seed`` controls geometry, grid size, and palette picks for the
held-out test pair. This separation lets a model see many public geometries
without ever encountering the private test instance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from arc_gen.core import (
    BACKGROUND,
    Grid,
    blank_grid,
    combined_seed,
    draw_rect,
    grid_shape,
    make_rng,
    sample_palette,
    validate_arc_task,
)


def _overlap(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _solve_holes(input_grid: Grid, fill_color: int) -> Grid:
    """Return a copy of ``input_grid`` with every enclosed background region
    repainted with ``fill_color``."""
    rows, cols = grid_shape(input_grid)
    solved = [row[:] for row in input_grid]

    # Flood-fill from the grid border; any cell of colour BACKGROUND that is
    # reachable from the border is *outside* and stays BACKGROUND.
    outside = [[False] * cols for _ in range(rows)]
    stack: List[Tuple[int, int]] = []
    for r in range(rows):
        for c in (0, cols - 1):
            if solved[r][c] == BACKGROUND and not outside[r][c]:
                outside[r][c] = True
                stack.append((r, c))
    for c in range(cols):
        for r in (0, rows - 1):
            if solved[r][c] == BACKGROUND and not outside[r][c]:
                outside[r][c] = True
                stack.append((r, c))
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not outside[nr][nc] and solved[nr][nc] == BACKGROUND:
                outside[nr][nc] = True
                stack.append((nr, nc))

    for r in range(rows):
        for c in range(cols):
            if solved[r][c] == BACKGROUND and not outside[r][c]:
                solved[r][c] = fill_color
    return solved


def _build_pair(seed: Any, params: Dict[str, Any]) -> Dict[str, Grid]:
    """Build one (input, output) pair entirely from `seed`.

    Grid size, geometry, and palette are all derived from this seed so the
    test pair is fully controlled by `private_seed`.
    """
    rng = make_rng(combined_seed("fill_enclosed", seed, params))

    if "grid_size" in params:
        gs = params["grid_size"]
        rows, cols = int(gs[0]), int(gs[1])
    else:
        rows = int(params.get("rows", rng.randint(8, 14)))
        cols = int(params.get("cols", rng.randint(8, 14)))

    n_shapes = int(params.get("n_shapes", rng.randint(1, 3)))
    palette = sample_palette(rng, n_shapes + 1)  # borders + fill
    border_colors = palette[:n_shapes]
    fill_color = palette[-1]

    grid = blank_grid(rows, cols)
    placed: List[Tuple[int, int, int, int]] = []
    for i in range(n_shapes):
        for _try in range(60):
            w = rng.randint(3, max(3, cols - 2))
            h = rng.randint(3, max(3, rows - 2))
            if h < 3 or w < 3:
                continue
            r0 = rng.randint(1, rows - h - 1)
            c0 = rng.randint(1, cols - w - 1)
            r1 = r0 + h - 1
            c1 = c0 + w - 1
            cand = (r0, c0, r1, c1)
            if any(_overlap(cand, p) for p in placed):
                continue
            placed.append(cand)
            draw_rect(grid, r0, c0, r1, c1, border_colors[i])
            break
        else:
            # Could not place; skip this shape.
            pass

    solved = _solve_holes(grid, fill_color)
    return {"input": grid, "output": solved}


def generate(public_seed: Any, private_seed: Any, **params: Any) -> Dict[str, Any]:
    """Generate a fill-enclosed task.

    Each pair is built independently from its own seed so the public/private
    split is real: the test pair is determined solely by ``private_seed``.
    """
    n_train = int(params.get("n_train", 3))
    train = [_build_pair(f"{public_seed}-{i}", params) for i in range(n_train)]
    test = [_build_pair(private_seed, params)]

    task = {"train": train, "test": test}
    validate_arc_task(task, require_test_output=True)
    return task