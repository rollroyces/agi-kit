"""Shared utilities for ARC task generators.

Conventions
-----------
- Grids are lists of lists of ints in [0, 9].
- `0` is the background colour by default. Generators may override.
- All RNGs come from `make_rng` so seed handling is centralised.
- Shapes and positions are inclusive on both axes.
"""

from __future__ import annotations

import json
import random
from typing import Any, Iterable, List, Sequence, Tuple

Grid = List[List[int]]
Coord = Tuple[int, int]

BACKGROUND = 0
MIN_CELL = 0
MAX_CELL = 9


class ARCError(Exception):
    """Raised when a generator produces an invalid task."""


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------

def grid_shape(grid: Grid) -> Tuple[int, int]:
    """Return (rows, cols) of a 2D grid."""
    if not grid:
        return (0, 0)
    return len(grid), len(grid[0])


def blank_grid(rows: int, cols: int, fill: int = BACKGROUND) -> Grid:
    """Return a new grid filled with `fill`."""
    return [[fill for _ in range(cols)] for _ in range(rows)]


def clone_grid(grid: Grid) -> Grid:
    """Deep-copy a grid."""
    return [row[:] for row in grid]


def in_bounds(grid: Grid, r: int, c: int) -> bool:
    rows, cols = grid_shape(grid)
    return 0 <= r < rows and 0 <= c < cols


def fill_rect(grid: Grid, r0: int, c0: int, r1: int, c1: int, color: int) -> None:
    """Fill an inclusive rectangle [r0..r1] x [c0..c1] in-place."""
    rows, cols = grid_shape(grid)
    for r in range(max(0, r0), min(rows, r1 + 1)):
        for c in range(max(0, c0), min(cols, c1 + 1)):
            grid[r][c] = color


def draw_rect(grid: Grid, r0: int, c0: int, r1: int, c1: int, color: int) -> None:
    """Draw the border of an inclusive rectangle in-place."""
    rows, cols = grid_shape(grid)
    for r in range(max(0, r0), min(rows, r1 + 1)):
        for c in range(max(0, c0), min(cols, c1 + 1)):
            if r == r0 or r == r1 or c == c0 or c == c1:
                grid[r][c] = color


def rotate_grid(grid: Grid, k: int = 1) -> Grid:
    """Rotate a grid by 90 * k degrees clockwise."""
    if not grid:
        return []
    k %= 4
    if k == 0:
        return clone_grid(grid)
    if k == 2:
        return [row[::-1] for row in grid[::-1]]
    if k == 1:
        rows, cols = grid_shape(grid)
        return [[grid[rows - 1 - r][c] for r in range(rows)] for c in range(cols)]
    # k == 3
    rows, cols = grid_shape(grid)
    return [[grid[r][cols - 1 - c] for c in range(cols)] for r in range(rows)]


def reflect_grid(grid: Grid, axis: str = "vertical") -> Grid:
    """Reflect a grid across `axis` ('vertical' = flip cols, 'horizontal' = flip rows)."""
    if axis == "vertical":
        return [row[::-1] for row in grid]
    if axis == "horizontal":
        return grid[::-1]
    raise ARCError(f"Unknown reflection axis: {axis}")


def transpose_grid(grid: Grid) -> Grid:
    rows, cols = grid_shape(grid)
    return [[grid[r][c] for r in range(rows)] for c in range(cols)]


def count_color_cells(grid: Grid, color: int) -> int:
    return sum(1 for row in grid for v in row if v == color)


def sample_palette(rng: random.Random, k: int, exclude: Iterable[int] = (BACKGROUND,)) -> List[int]:
    """Pick `k` distinct non-background colours from 1..9."""
    pool = [c for c in range(MIN_CELL, MAX_CELL + 1) if c not in set(exclude)]
    if k > len(pool):
        raise ARCError(f"Requested {k} colours but only {len(pool)} available")
    return rng.sample(pool, k)


def find_components(grid: Grid, background: int = BACKGROUND) -> List[List[Coord]]:
    """Find 4-connected components of non-background cells, grouped by colour."""
    rows, cols = grid_shape(grid)
    seen = [[False] * cols for _ in range(rows)]
    components: List[List[Coord]] = []
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == background or seen[r][c]:
                continue
            stack = [(r, c)]
            comp: List[Coord] = []
            while stack:
                cr, cc = stack.pop()
                if not in_bounds(grid, cr, cc) or seen[cr][cc] or grid[cr][cc] == background:
                    continue
                seen[cr][cc] = True
                comp.append((cr, cc))
                stack.extend([(cr + 1, cc), (cr - 1, cc), (cr, cc + 1), (cr, cc - 1)])
            if comp:
                components.append(comp)
    return components


def flood_fill(grid: Grid, r: int, c: int, color: int, background: int = BACKGROUND) -> int:
    """Replace the connected component of `background` touching (r,c) with `color`.
    Returns the number of cells repainted."""
    if not in_bounds(grid, r, c) or grid[r][c] != background:
        return 0
    target = background
    painted = 0
    stack = [(r, c)]
    while stack:
        cr, cc = stack.pop()
        if not in_bounds(grid, cr, cc) or grid[cr][cc] != target:
            continue
        grid[cr][cc] = color
        painted += 1
        stack.extend([(cr + 1, cc), (cr - 1, cc), (cr, cc + 1), (cr, cc - 1)])
    return painted


def grid_equal(a: Grid, b: Grid) -> bool:
    if grid_shape(a) != grid_shape(b):
        return False
    for r1, r2 in zip(a, b):
        if r1 != r2:
            return False
    return True


# ---------------------------------------------------------------------------
# RNG and seeding
# ---------------------------------------------------------------------------

def make_rng(seed: Any) -> random.Random:
    """Return a deterministic `random.Random` from an arbitrary hashable seed."""
    rng = random.Random()
    try:
        rng.seed(seed)
    except TypeError:
        rng.seed(str(seed))
    return rng


def combined_seed(*parts: Any) -> int:
    """Combine multiple seed parts into a stable 64-bit integer."""
    h = 0x9E3779B97F4A7C15
    for p in parts:
        s = str(p).encode("utf-8")
        for b in s:
            h ^= b
            h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


# ---------------------------------------------------------------------------
# Task schema validation
# ---------------------------------------------------------------------------

def validate_arc_task(task: dict, *, require_test_output: bool = True) -> None:
    """Raise ARCError if `task` does not conform to the ARC schema."""
    if not isinstance(task, dict):
        raise ARCError("task must be a dict")
    for key in ("train", "test"):
        if key not in task:
            raise ARCError(f"task missing key '{key}'")
        if not isinstance(task[key], list) or not task[key]:
            raise ARCError(f"task['{key}'] must be a non-empty list")
    for i, pair in enumerate(task["train"]):
        _validate_pair(pair, i, "train", require_output=True)
    for i, pair in enumerate(task["test"]):
        _validate_pair(pair, i, "test", require_output=require_test_output)


def _validate_pair(pair: Any, idx: int, section: str, *, require_output: bool) -> None:
    if not isinstance(pair, dict) or "input" not in pair:
        raise ARCError(f"{section}[{idx}] missing 'input'")
    in_grid = pair["input"]
    out_grid = pair.get("output")
    rows, cols = _check_grid(in_grid, f"{section}[{idx}].input")
    if require_output:
        if out_grid is None:
            raise ARCError(f"{section}[{idx}] missing 'output'")
        orows, ocols = _check_grid(out_grid, f"{section}[{idx}].output")
        if (orows, ocols) != (rows, cols):
            raise ARCError(
                f"{section}[{idx}] shape mismatch: input {(rows, cols)} vs output {(orows, ocols)}"
            )
    elif out_grid is not None:
        # Even for public train pairs, shapes must match
        orows, ocols = _check_grid(out_grid, f"{section}[{idx}].output")
        if (orows, ocols) != (rows, cols):
            raise ARCError(
                f"{section}[{idx}] shape mismatch: input {(rows, cols)} vs output {(orows, ocols)}"
            )


def _check_grid(grid: Any, label: str) -> Tuple[int, int]:
    if not isinstance(grid, list) or not grid:
        raise ARCError(f"{label} must be a non-empty list")
    cols = None
    for r, row in enumerate(grid):
        if not isinstance(row, list):
            raise ARCError(f"{label}[{r}] must be a list")
        if cols is None:
            cols = len(row)
        elif len(row) != cols:
            raise ARCError(f"{label} rows have inconsistent lengths")
        for c, v in enumerate(row):
            if not isinstance(v, int) or isinstance(v, bool):
                raise ARCError(f"{label}[{r}][{c}] must be int, got {type(v).__name__}")
            if not (MIN_CELL <= v <= MAX_CELL):
                raise ARCError(f"{label}[{r}][{c}]={v} out of range [{MIN_CELL},{MAX_CELL}]")
    return len(grid), cols  # type: ignore[return-value]


def task_to_jsonable(task: dict) -> dict:
    """Return a JSON-safe deep copy of `task`."""
    return json.loads(json.dumps(task))