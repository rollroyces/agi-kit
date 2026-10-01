"""Lightweight task-feature extraction.

The reasoner inspects a small set of train pairs to compute signals used by
template selection. Features are deliberately cheap (single-pass over each
train pair) — no symbolic search, no LLM.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

Grid = List[List[int]]


def _shape(g: Grid) -> Tuple[int, int]:
    return (len(g), len(g[0]) if g else 0)


def _colors(g: Grid) -> Counter:
    c = Counter()
    for row in g:
        c.update(row)
    return c


def _distinct(g: Grid) -> List[int]:
    return sorted(set(v for row in g for v in row))


def _bg(g: Grid) -> int:
    return _colors(g).most_common(1)[0][0]


def _is_symmetric_h(grid: Grid) -> bool:
    return all(row == list(reversed(row)) for row in grid)


def _is_symmetric_v(grid: Grid) -> bool:
    return list(grid) == list(reversed(grid))


@dataclass
class TaskFeatures:
    """Computed task-level features used by template selection."""

    palette_size: int = 0
    background: int = 0
    palette: List[int] = field(default_factory=list)
    object_count: int = 0
    has_symmetry_h: bool = False
    has_symmetry_v: bool = False
    n_train_pairs: int = 0
    n_test_pairs: int = 0
    shape_in: Tuple[int, int] = (0, 0)
    shape_out: Tuple[int, int] = (0, 0)
    shape_invariant: bool = True
    output_has_marker_row: bool = False
    input_has_enclosed_pockets: bool = False
    input_has_multiple_objects: bool = False
    output_introduces_new_color: bool = False
    # v2 — multi-modal + language-conditioned extensions.
    is_multichannel: bool = False
    n_channels: int = 1
    hints: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


def _count_objects(grid: Grid, bg: int) -> int:
    h, w = _shape(grid)
    seen = [[False] * w for _ in range(h)]
    count = 0
    for i in range(h):
        for j in range(w):
            if grid[i][j] == bg or seen[i][j]:
                continue
            color = grid[i][j]
            stack = [(i, j)]
            while stack:
                y, x = stack.pop()
                if y < 0 or y >= h or x < 0 or x >= w:
                    continue
                if seen[y][x] or grid[y][x] != color:
                    continue
                seen[y][x] = True
                stack.extend([(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)])
            count += 1
    return count


def _has_enclosed_pockets(grid: Grid, bg: int) -> bool:
    """True iff there is at least one bg pocket not touching the edge."""
    h, w = _shape(grid)
    outside = [[False] * w for _ in range(h)]
    stack = []
    for r in range(h):
        for c in (0, w - 1):
            if grid[r][c] == bg:
                outside[r][c] = True
                stack.append((r, c))
    for c in range(w):
        for r in (0, h - 1):
            if grid[r][c] == bg:
                outside[r][c] = True
                stack.append((r, c))
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not outside[ny][nx] and grid[ny][nx] == bg:
                outside[ny][nx] = True
                stack.append((ny, nx))
    # Look for any bg cell that is not outside.
    for r in range(h):
        for c in range(w):
            if grid[r][c] == bg and not outside[r][c]:
                return True
    return False


def _bottom_row_uniform_marker(grid: Grid) -> bool:
    """True if the bottom row has a single non-zero colour repeated contiguously from column 0."""
    if not grid:
        return False
    last = grid[-1]
    counts = Counter(v for v in last if v != 0)
    if not counts:
        return False
    if len(counts) > 1:
        return False
    colour = next(iter(counts))
    if last[0] != colour:
        return False
    # Contiguous run of `colour` starting from column 0, then maybe zeros.
    i = 0
    while i < len(last) and last[i] == colour:
        i += 1
    while i < len(last) and last[i] == 0:
        i += 1
    return i == len(last)


def extract_features(task: dict) -> TaskFeatures:
    """Compute :class:`TaskFeatures` from a full A3S task dict."""
    from dsl.multichannel import is_multichannel as _ismc, project_luminance
    train = task["task"]["train"]
    test = task["task"]["test"]
    in0 = train[0]["input"]
    out0 = train[0]["output"]
    # v2 — if the input is multichannel, project to luminance for the
    # downstream scalar features (palette, bg, symmetry, …). The raw
    # multichannel shape is preserved in ``is_multichannel`` / ``n_channels``
    # so the proposers still emit multichannel-aware templates.
    multi = _ismc(in0)
    if multi:
        in0_view = project_luminance(in0)
        out0_view = project_luminance(out0) if _ismc(out0) else out0
        n_channels = len(in0) if in0 else 0
    else:
        in0_view = in0
        out0_view = out0
        n_channels = 1
    feat = TaskFeatures(
        n_train_pairs=len(train),
        n_test_pairs=len(test),
        palette=sorted(set(_distinct(in0_view)) | set(_distinct(out0_view))),
        shape_in=_shape(in0_view),
        shape_out=_shape(out0_view),
    )
    feat.palette_size = len(feat.palette)
    feat.background = _bg(in0_view)
    # Average object count across train inputs (use the projected view).
    counts = [
        _count_objects(
            (project_luminance(p["input"]) if _ismc(p["input"]) else p["input"]),
            _bg(project_luminance(p["input"]) if _ismc(p["input"]) else p["input"]),
        )
        for p in train
    ]
    feat.object_count = max(counts) if counts else 0
    feat.input_has_multiple_objects = feat.object_count >= 2
    feat.has_symmetry_h = all(
        _is_symmetric_h(project_luminance(p["output"]) if _ismc(p["output"]) else p["output"])
        for p in train
    )
    feat.has_symmetry_v = all(
        _is_symmetric_v(project_luminance(p["output"]) if _ismc(p["output"]) else p["output"])
        for p in train
    )
    feat.output_has_marker_row = all(
        _bottom_row_uniform_marker(
            project_luminance(p["output"]) if _ismc(p["output"]) else p["output"]
        ) for p in train
    )
    feat.input_has_enclosed_pockets = any(
        _has_enclosed_pockets(
            project_luminance(p["input"]) if _ismc(p["input"]) else p["input"],
            _bg(project_luminance(p["input"]) if _ismc(p["input"]) else p["input"]),
        ) for p in train
    )
    feat.shape_invariant = all(
        _shape(p["input"]) == _shape(p["output"]) for p in train
    )
    feat.output_introduces_new_color = any(
        set(_distinct(
            project_luminance(p["output"]) if _ismc(p["output"]) else p["output"]
        )) - set(_distinct(
            project_luminance(p["input"]) if _ismc(p["input"]) else p["input"]
        )) for p in train
    )
    feat.is_multichannel = multi
    feat.n_channels = n_channels
    raw_hints = task.get("hints") if isinstance(task, dict) else None
    if isinstance(raw_hints, (list, tuple)):
        feat.hints = [str(h) for h in raw_hints if h]
    elif isinstance(raw_hints, str) and raw_hints:
        feat.hints = [raw_hints]
    return feat