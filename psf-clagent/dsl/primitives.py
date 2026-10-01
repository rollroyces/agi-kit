"""Pure functional primitives for the grid DSL.

Conventions:
    * A Grid is a list of lists of ints in ``[0, 9]``.
    * All primitive functions are pure: they never mutate their input grid.
    * Inspector primitives return Python values, not grids.

v2 multi-channel primitives (``make_multichannel``, ``extract_channel``,
``combine_channels``, ``project_luminance``) live in :mod:`dsl.multichannel`
and are re-exported here so the registry + interpreter can treat them like
any other primitive.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Sequence, Tuple

Grid = List[List[int]]

# v2 — multi-channel helpers (purely re-exported so they participate in
# the registry + interpreter like every other primitive).
from dsl.multichannel import (  # noqa: E402
    is_multichannel,
    make_multichannel,
    extract_channel,
    combine_channels,
    project_luminance,
)


def _shape(grid: Grid) -> Tuple[int, int]:
    if not grid:
        return (0, 0)
    return len(grid), len(grid[0]) if grid[0] else 0


def _deep_copy(grid: Grid) -> Grid:
    return [row[:] for row in grid]


def _majority_color(grid: Grid) -> int:
    counter: Counter = {}
    for row in grid:
        for c in row:
            counter[c] = counter.get(c, 0) + 1
    return max(counter.items(), key=lambda kv: kv[1])[0] if counter else 0


from collections import Counter  # noqa: E402


# Construction

def make_grid(h: int, w: int, fill: int = 0) -> Grid:
    """Build a fresh ``h x w`` grid filled with ``fill``."""
    h = int(h)
    w = int(w)
    return [[int(fill) for _ in range(w)] for _ in range(h)]


def from_list(rows: Sequence[Sequence[int]]) -> Grid:
    """Build a grid from a list-of-lists. Each row is deep-copied."""
    return [[int(c) for c in row] for row in rows]


# Inspection

def shape(grid: Grid) -> Tuple[int, int]:
    """Return ``(rows, cols)`` of a grid."""
    return _shape(grid)


def color_at(grid: Grid, r: int, c: int) -> int:
    """Return the colour at ``(r, c)`` (out-of-bounds → 0)."""
    h, w = _shape(grid)
    if 0 <= r < h and 0 <= c < w:
        return grid[r][c]
    return 0


def distinct_colors(grid: Grid) -> List[int]:
    """Return sorted distinct colours in ``grid``."""
    seen = set()
    for row in grid:
        for c in row:
            seen.add(c)
    return sorted(seen)


def count_color(grid: Grid, c: int) -> int:
    """Count occurrences of colour ``c`` in ``grid``."""
    return sum(1 for row in grid for v in row if v == c)


def background_color(grid: Grid) -> int:
    """The most-frequent colour — the heuristic background."""
    return _majority_color(grid)


# Geometry

def rotate(grid: Grid, k: int = 1) -> Grid:
    """Rotate clockwise by ``k * 90`` degrees (k mod 4, 0 → identity)."""
    k = int(k) % 4
    if k == 0:
        return _deep_copy(grid)
    out = _deep_copy(grid)
    for _ in range(k):
        out = _rotate90cw(out)
    return out


def _rotate90cw(grid: Grid) -> Grid:
    """Rotate a grid 90° clockwise: ``(r, c) → (c, h - 1 - r)``."""
    if not grid or not grid[0]:
        return _deep_copy(grid)
    h = len(grid)
    w = len(grid[0])
    out: List[List[int]] = [[0] * h for _ in range(w)]
    for r in range(h):
        for c in range(w):
            out[c][h - 1 - r] = grid[r][c]
    return out


def flip_h(grid: Grid) -> Grid:
    """Mirror left-right."""
    return [list(reversed(row)) for row in _deep_copy(grid)]


def flip_v(grid: Grid) -> Grid:
    """Mirror top-bottom."""
    return list(reversed(_deep_copy(grid)))


def translate(grid: Grid, dr: int, dc: int, fill: int = 0) -> Grid:
    """Shift every cell by ``(dr, dc)``; vacated cells become ``fill``."""
    h, w = _shape(grid)
    out = [[int(fill) for _ in range(w)] for _ in range(h)]
    for r in range(h):
        for c in range(w):
            nr, nc = r + int(dr), c + int(dc)
            if 0 <= nr < h and 0 <= nc < w:
                out[nr][nc] = grid[r][c]
    return out


# Object ops

def connected_components(grid: Grid, background: int) -> List[List[Tuple[int, int]]]:
    """Return connected components of *same-colour* non-background cells (4-conn).

    Two cells are in the same component iff both are non-background, share
    the same colour, and are 4-adjacent. This is the canonical ARC
    convention; the shallow ``05-audit/heuristics.py`` version pools all
    non-background colours which is wrong for reasoning about distinct objects.
    """
    h, w = _shape(grid)
    seen = [[False] * w for _ in range(h)]
    comps: List[List[Tuple[int, int]]] = []
    for i in range(h):
        for j in range(w):
            if grid[i][j] == background or seen[i][j]:
                continue
            target = grid[i][j]
            stack = [(i, j)]
            comp: List[Tuple[int, int]] = []
            while stack:
                y, x = stack.pop()
                if y < 0 or y >= h or x < 0 or x >= w:
                    continue
                if seen[y][x] or grid[y][x] != target:
                    continue
                seen[y][x] = True
                comp.append((y, x))
                stack.extend([(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)])
            comps.append(comp)
    return comps


def bounding_box(obj: Sequence[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    """Return ``(r0, c0, r1, c1)`` bounding box of a cell list."""
    if not obj:
        return (0, 0, 0, 0)
    rs = [r for r, _ in obj]
    cs = [c for _, c in obj]
    return (min(rs), min(cs), max(rs), max(cs))


def largest_object(grid: Grid, background: int) -> List[Tuple[int, int]]:
    """Return the cells of the largest non-background component."""
    comps = connected_components(grid, background)
    if not comps:
        return []
    comps.sort(key=len, reverse=True)
    return comps[0]


def flood_fill(grid: Grid, r: int, c: int, new_color: int) -> Grid:
    """4-connected flood fill from ``(r, c)`` of its current colour."""
    h, w = _shape(grid)
    target = grid[r][c]
    out = _deep_copy(grid)
    stack = [(r, c)]
    seen = [[False] * w for _ in range(h)]
    while stack:
        y, x = stack.pop()
        if y < 0 or y >= h or x < 0 or x >= w:
            continue
        if seen[y][x] or out[y][x] != target:
            continue
        seen[y][x] = True
        out[y][x] = int(new_color)
        stack.extend([(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)])
    return out


def enclosed_regions(grid: Grid, background: int) -> List[List[Tuple[int, int]]]:
    """Return connected regions of ``background`` that do not touch the grid edge."""
    h, w = _shape(grid)
    outside = [[False] * w for _ in range(h)]
    stack: List[Tuple[int, int]] = []
    for r in range(h):
        for c in (0, w - 1):
            if grid[r][c] == background and not outside[r][c]:
                outside[r][c] = True
                stack.append((r, c))
    for c in range(w):
        for r in (0, h - 1):
            if grid[r][c] == background and not outside[r][c]:
                outside[r][c] = True
                stack.append((r, c))
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not outside[ny][nx] and grid[ny][nx] == background:
                outside[ny][nx] = True
                stack.append((ny, nx))
    seen = [[False] * w for _ in range(h)]
    regions: List[List[Tuple[int, int]]] = []
    for i in range(h):
        for j in range(w):
            if grid[i][j] != background or outside[i][j] or seen[i][j]:
                continue
            comp: List[Tuple[int, int]] = []
            stack2 = [(i, j)]
            while stack2:
                y, x = stack2.pop()
                if y < 0 or y >= h or x < 0 or x >= w:
                    continue
                if seen[y][x] or outside[y][x] or grid[y][x] != background:
                    continue
                seen[y][x] = True
                comp.append((y, x))
                stack2.extend([(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)])
            if comp:
                regions.append(comp)
    return regions


# Palette

def recolor(grid: Grid, mapping: Dict[int, int]) -> Grid:
    """Replace each colour ``src`` with ``mapping[src]``; unmapped cells unchanged."""
    out = _deep_copy(grid)
    for r, row in enumerate(out):
        for c, v in enumerate(row):
            if v in mapping:
                out[r][c] = int(mapping[v])
    return out


def invert_palette(grid: Grid) -> Grid:
    """Map 0->9, 9->1, 1->9, 2->8, ..., 5->5."""
    def inv(v: int) -> int:
        if v == 0:
            return 9
        if v == 9:
            return 1
        return 10 - v
    return [[inv(c) for c in row] for row in _deep_copy(grid)]


# Higher-order

def compose(*parts: Callable[[Grid], Grid]) -> Callable[[Grid], Grid]:
    """Left-to-right function composition. ``compose(f, g)(x) == g(f(x))``."""
    parts = tuple(parts)

    def _c(grid: Grid) -> Grid:
        out = grid
        for fn in parts:
            out = fn(out)
        return out

    return _c


def iterate(f: Callable[[Grid], Grid], n: int, x: Grid) -> Grid:
    """Apply ``f`` to ``x`` exactly ``n`` times."""
    out = _deep_copy(x)
    for _ in range(int(n)):
        out = f(out)
    return out


def zip_with(f: Callable[[Grid, Grid], Grid], g1: Grid, g2: Grid) -> Grid:
    """Apply a binary grid function cell-by-cell. Shapes must match."""
    h1, w1 = _shape(g1)
    h2, w2 = _shape(g2)
    if (h1, w1) != (h2, w2):
        raise ValueError(f"zip_with: shape mismatch {g1} vs {g2}")
    return [[f([[g1[r][c]]], [[g2[r][c]]])[0][0] for c in range(w1)] for r in range(h1)]


def identity(grid: Grid) -> Grid:
    """Return a deep copy of the grid."""
    return _deep_copy(grid)


def apply_program(prog: Callable[[Grid], Grid], grid: Grid) -> Grid:
    """Run a callable program on ``grid``. Used as a uniform type-erased wrapper."""
    return prog(grid)