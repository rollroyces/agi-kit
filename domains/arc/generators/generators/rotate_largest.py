"""Rotate the largest non-background object generator.

Task semantics
---------------
The input contains 2-4 small non-overlapping coloured objects placed on a
background. Each object is drawn from a library of asymmetric patterns with
distinct cell counts (2, 3, 4, or 5 cells, all within a 3x3 bounding box).
The output is identical to the input except that the largest object (by cell
count) is rotated 90 degrees clockwise *in place* within its 3x3 bounding
box.

Because the patterns are not 90-degree-symmetric, the rotation produces a
visibly different shape while leaving every other object untouched. Ties on
cell count are eliminated by construction (each pair draws cell counts from a
strictly increasing sequence).

Parametric controls
-------------------
``n_objects``      number of objects per pair (default 3; allowed 2..4)
``grid_size``      (rows, cols) of the canvas (default 10x10)
``n_train``        number of demonstration pairs (default 3)

``public_seed`` controls object placement, palette and exact pattern choice
for the demo pairs. ``private_seed`` does the same for the held-out test
pair, so the model can never have seen the test geometry.
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


# Patterns keyed by their cell count. Each is a 3x3 pattern with a single
# "anchor" cell at (0, 0); the bbox is 3x3 in the canvas. Patterns under a
# 90-degree rotation produce a visibly different shape.
PATTERNS: Dict[int, List[Tuple[int, int]]] = {
    2: [(0, 0), (1, 0)],                                      # vertical pair
    3: [(0, 0), (0, 1), (1, 0)],                              # L corner
    4: [(0, 0), (0, 1), (1, 1), (2, 1)],                      # S shape
    5: [(0, 0), (0, 1), (1, 0), (2, 0), (2, 1)],              # Z shape
}


def _rotate_90(cells: List[Tuple[int, int]], size: int = 3) -> List[Tuple[int, int]]:
    """Rotate (row, col) offsets 90 degrees clockwise inside a `size`-sized bbox.

    (r, c) -> (c, size - 1 - r)
    """
    return [(c, size - 1 - r) for (r, c) in cells]


def _strictly_increasing_counts(rng, n: int) -> List[int]:
    """Pick `n` strictly increasing counts from {2,3,4,5}."""
    counts = sorted(rng.sample([2, 3, 4, 5], n))
    if len(counts) != n:
        # rng.sample on a 4-element pool cannot produce duplicates, but be safe.
        counts = sorted(set(counts))
        while len(counts) < n:
            extra = rng.choice([c for c in (2, 3, 4, 5) if c not in counts])
            counts.append(extra)
            counts.sort()
    return counts


def _try_place(rng, grid: Grid, pattern_size: int, occupied: set) -> Tuple[int, int] | None:
    rows, cols = grid_shape(grid)
    for _ in range(80):
        r0 = rng.randint(1, rows - pattern_size - 1)
        c0 = rng.randint(1, cols - pattern_size - 1)
        if all((r0 + dr, c0 + dc) not in occupied for dr in range(pattern_size) for dc in range(pattern_size)):
            return r0, c0
    return None


def _build_pair(seed: Any, params: Dict[str, Any]) -> Dict[str, Grid]:
    rng = make_rng(combined_seed("rotate_largest", seed, params))

    if "grid_size" in params:
        gs = params["grid_size"]
        rows, cols = int(gs[0]), int(gs[1])
    else:
        rows = int(params.get("rows", rng.randint(10, 14)))
        cols = int(params.get("cols", rng.randint(10, 14)))

    grid = blank_grid(rows, cols)

    n_objects = int(params.get("n_objects", 3))
    if not 2 <= n_objects <= 4:
        n_objects = 3

    counts = _strictly_increasing_counts(rng, n_objects)  # strictly increasing -> unique largest
    colors = sample_palette(rng, n_objects)

    placed_objects: List[Dict[str, Any]] = []
    occupied: set = set()
    for count, color in zip(counts, colors):
        pattern = PATTERNS[count]
        anchor = _try_place(rng, grid, 3, occupied)
        if anchor is None:
            continue
        r0, c0 = anchor
        for dr, dc in pattern:
            grid[r0 + dr][c0 + dc] = color
            occupied.add((r0 + dr, c0 + dc))
        placed_objects.append({
            "color": color,
            "anchor": (r0, c0),
            "count": count,
            "pattern": pattern,
        })

    if not placed_objects:
        raise RuntimeError("rotate_largest: failed to place any objects")

    # Largest by cell count (guaranteed unique by construction).
    largest = max(placed_objects, key=lambda o: o["count"])
    r0, c0 = largest["anchor"]
    color = largest["color"]
    rotated = _rotate_90(largest["pattern"])

    solved = [row[:] for row in grid]
    # Clear the largest's 3x3 bbox back to background.
    for dr in range(3):
        for dc in range(3):
            solved[r0 + dr][c0 + dc] = BACKGROUND
    # Paint the rotated pattern.
    for dr, dc in rotated:
        solved[r0 + dr][c0 + dc] = color

    return {"input": grid, "output": solved}


def generate(public_seed: Any, private_seed: Any, **params: Any) -> Dict[str, Any]:
    """Generate a rotate-largest task.

    Each pair is built entirely from its own seed so the test pair is fully
    controlled by ``private_seed``.
    """
    n_train = int(params.get("n_train", 3))
    train = [_build_pair(f"{public_seed}-{i}", params) for i in range(n_train)]
    test = [_build_pair(private_seed, params)]

    task = {"train": train, "test": test}
    validate_arc_task(task, require_test_output=True)
    return task