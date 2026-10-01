"""Shallow heuristic solvers for ARC tasks.

Each heuristic implements the signature:
    predict(train_pairs, test_input) -> predicted_output (list[list[int]])

Heuristics are deliberately *trivial*: they do not inspect the training pairs to
infer a rule. The point is to flag ARC tasks that any one of them solves exactly —
which usually implies the task is not testing abstract reasoning at all.

Conventions:
    - Colors are integers in [0, 9] (ARC convention).
    - Grid is a list of lists of ints.
    - Background color is the most frequent color in the grid.
"""
from __future__ import annotations

from collections import Counter
from typing import List, Sequence, Tuple

Grid = List[List[int]]
TrainPair = Tuple[Grid, Grid]


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------

def _shape(grid: Grid) -> Tuple[int, int]:
    if not grid or not grid[0]:
        return (0, 0)
    return len(grid), len(grid[0])


def _empty_like(grid: Grid, fill: int = 0) -> Grid:
    h, w = _shape(grid)
    return [[fill for _ in range(w)] for _ in range(h)]


def _counter(grid: Grid) -> Counter:
    c = Counter()
    for row in grid:
        c.update(row)
    return c


def _majority_color(grid: Grid) -> int:
    return _counter(grid).most_common(1)[0][0]


def _rare_color(grid: Grid, exclude: Sequence[int] = ()) -> int:
    counter = _counter(grid)
    for color, _ in counter.most_common():
        if color not in exclude:
            return color
    return 0


def _flip_h(grid: Grid) -> Grid:
    return [list(reversed(row)) for row in grid]


def _flip_v(grid: Grid) -> Grid:
    return list(reversed(grid))


def _connected_components(grid: Grid, background: int) -> List[List[Tuple[int, int]]]:
    """Return connected components of non-background cells (4-connectivity)."""
    h, w = _shape(grid)
    seen = [[False] * w for _ in range(h)]
    comps: List[List[Tuple[int, int]]] = []
    for i in range(h):
        for j in range(w):
            if grid[i][j] == background or seen[i][j]:
                continue
            stack = [(i, j)]
            comp: List[Tuple[int, int]] = []
            while stack:
                y, x = stack.pop()
                if y < 0 or y >= h or x < 0 or x >= w:
                    continue
                if seen[y][x] or grid[y][x] == background:
                    continue
                seen[y][x] = True
                comp.append((y, x))
                stack.extend([(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)])
            comps.append(comp)
    return comps


# ---------------------------------------------------------------------------
# heuristics
# ---------------------------------------------------------------------------

def identity_heuristic(train_pairs: Sequence[TrainPair], test_input: Grid) -> Grid:
    """Return the input unchanged."""
    return [row[:] for row in test_input]


def palette_majority_heuristic(train_pairs: Sequence[TrainPair], test_input: Grid) -> Grid:
    """Fill the entire output with the most frequent color in the input."""
    fill = _majority_color(test_input)
    return _empty_like(test_input, fill)


def mirror_heuristic(train_pairs: Sequence[TrainPair], test_input: Grid) -> Grid:
    """Flip the input horizontally (left-right)."""
    return _flip_h(test_input)


def largest_object_heuristic(train_pairs: Sequence[TrainPair], test_input: Grid) -> Grid:
    """Keep only the largest non-background connected component; rest becomes background."""
    background = _majority_color(test_input)
    comps = _connected_components(test_input, background)
    out = _empty_like(test_input, background)
    if not comps:
        return out
    comps.sort(key=len, reverse=True)
    for y, x in comps[0]:
        out[y][x] = test_input[y][x]
    return out


def background_swap_heuristic(train_pairs: Sequence[TrainPair], test_input: Grid) -> Grid:
    """Swap the background color (most common) with the rarest non-background color."""
    background = _majority_color(test_input)
    rare = _rare_color(test_input, exclude=(background,))
    out = [[background if c == rare else (rare if c == background else c) for c in row] for row in test_input]
    return out


def diagonal_replicate_heuristic(train_pairs: Sequence[TrainPair], test_input: Grid) -> Grid:
    """Tile the input to form a 2x2 block grid (each block equals the input)."""
    out: Grid = []
    for _ in range(2):
        for row in test_input:
            out.append(row[:] + row[:])
    return out


def single_color_fill_heuristic(train_pairs: Sequence[TrainPair], test_input: Grid) -> Grid:
    """Fill the entire output with the count of distinct colors (clamped to 0-9)."""
    n_colors = len({c for row in test_input for c in row})
    fill = max(0, min(9, n_colors))
    return _empty_like(test_input, fill)


def palette_invert_heuristic(train_pairs: Sequence[TrainPair], test_input: Grid) -> Grid:
    """Invert palette: 1->9, 2->8, 3->7, 4->6, 5->5; 0 and 9 map to 9 and 1 respectively."""
    def invert(c: int) -> int:
        if c == 0:
            return 9
        if c == 9:
            return 1
        return 10 - c

    return [[invert(c) for c in row] for row in test_input]


# ---------------------------------------------------------------------------
# public registry
# ---------------------------------------------------------------------------

HEURISTICS = {
    "identity": identity_heuristic,
    "palette_majority": palette_majority_heuristic,
    "mirror": mirror_heuristic,
    "largest_object": largest_object_heuristic,
    "background_swap": background_swap_heuristic,
    "diagonal_replicate": diagonal_replicate_heuristic,
    "single_color_fill": single_color_fill_heuristic,
    "palette_invert": palette_invert_heuristic,
}


def run_all(train_pairs, test_input):
    """Convenience: run every heuristic and return {name: prediction}."""
    return {name: fn(train_pairs, test_input) for name, fn in HEURISTICS.items()}