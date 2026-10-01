"""Count distinct colors generator.

Task semantics
---------------
The input is a small grid scattered with N cells, each painted in a unique
non-background colour. The output is identical in shape but has every cell
reset to the background colour *except* the bottom row, which contains
exactly N marker cells (colour 8) starting from column 0.

The task forces a model to:
  1. discover that every input colour is unique;
  2. count them;
  3. paint that many markers of colour 8 in the bottom row.

Parametric controls
-------------------
``n_colors``     number of distinct colours (default 3; allowed 2..7)
``grid_size``    (rows, cols) of the canvas (default sampled per-pair)
``marker_color`` colour used for the count markers (default 8)

``public_seed`` controls every aspect of the demonstration pairs;
``private_seed`` controls only the held-out test pair.
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

DEFAULT_MARKER = 8


def _place_positions(rng, n: int, rows: int, cols: int, forbidden_rows: Tuple[int, ...] = ()) -> List[Tuple[int, int]]:
    """Choose `n` non-overlapping positions, avoiding `forbidden_rows`."""
    placed: List[Tuple[int, int]] = []
    occupied: set = set()
    for _ in range(400):
        r = rng.randint(0, rows - 1)
        c = rng.randint(0, cols - 1)
        if r in forbidden_rows:
            continue
        if (r, c) in occupied:
            continue
        occupied.add((r, c))
        placed.append((r, c))
        if len(placed) == n:
            break
    if len(placed) < n:
        raise RuntimeError(f"count_colors: only placed {len(placed)}/{n} cells")
    return placed


def _build_pair(seed: Any, params: Dict[str, Any]) -> Dict[str, Grid]:
    rng = make_rng(combined_seed("count_colors", seed, params))

    if "grid_size" in params:
        gs = params["grid_size"]
        rows, cols = int(gs[0]), int(gs[1])
    else:
        rows = int(params.get("rows", rng.randint(5, 8)))
        cols = int(params.get("cols", rng.randint(5, 8)))

    n_colors = int(params.get("n_colors", 3))
    if not 2 <= n_colors <= 7:
        n_colors = 3
    n_colors = min(n_colors, cols)  # cannot exceed cols or markers won't fit
    marker_color = int(params.get("marker_color", DEFAULT_MARKER))

    palette = sample_palette(rng, n_colors, exclude={marker_color})
    if len(palette) != n_colors:
        raise RuntimeError("count_colors: palette generation failed")

    # Place N cells in rows 0..(rows-2) so the bottom row stays free for markers.
    forbidden = (rows - 1,)
    positions = _place_positions(rng, n_colors, rows, cols, forbidden)

    input_grid = blank_grid(rows, cols)
    for (r, c), color in zip(positions, palette):
        input_grid[r][c] = color

    # Output: clear everything, then paint N markers in the bottom row.
    output_grid = blank_grid(rows, cols)
    n_markers = min(n_colors, cols)
    for i in range(n_markers):
        output_grid[rows - 1][i] = marker_color

    return {"input": input_grid, "output": output_grid}


def generate(public_seed: Any, private_seed: Any, **params: Any) -> Dict[str, Any]:
    """Generate a count-colors task.

    Each pair is built entirely from its own seed (no global parameters that
    depend on ``public_seed``), so the test pair is purely a function of
    ``private_seed``.
    """
    n_train = int(params.get("n_train", 3))
    train = [_build_pair(f"{public_seed}-{i}", params) for i in range(n_train)]
    test = [_build_pair(private_seed, params)]

    task = {"train": train, "test": test}
    validate_arc_task(task, require_test_output=True)
    return task