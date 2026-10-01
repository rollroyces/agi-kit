"""Multimodal grid channels (v2).

A :class:`MultiChannelGrid` is a *list* of 2D grids of identical ``(h, w)`` —
each grid is a "channel". The CLAgent v1 grid pipeline only sees one
channel; v2 generalises to two or more without breaking the single-channel
contract: anything that takes a ``Grid`` still takes one. New primitives
(:func:`make_multichannel`, :func:`extract_channel`, :func:`combine_channels`,
:func:`project_luminance`) operate on the list-of-grids view and let programs
mix a primary view with auxiliary channels (depth, sparse mask, vector field,
etc.).

Detection
---------
:func:`is_multichannel` recognises the multi-channel representation by
checking that the *first* element of the input is itself a list (i.e. the
input is a list of 2D grids, not a single 2D grid). All primitives are
no-ops on a single-channel grid: they accept any grid and return a grid.

This module intentionally contains no I/O and no globals; it's pure data
plus a small set of pure operators.
"""
from __future__ import annotations

from typing import Any, List, Sequence, Tuple

Grid = List[List[int]]
MultiChannelGrid = List[Grid]


def is_multichannel(grid: Any) -> bool:
    """True iff ``grid`` is a list-of-grids (multi-channel) representation.

    Depth check: a 2D grid is ``list[list[int]]``; a multichannel grid is
    ``list[list[list[int]]]``. We require the first element of ``g`` to be a
    list AND the first element of *that* to also be a list, so a single
    2D grid (e.g. ``[[1, 2], [3, 4]]``) is never mistaken for multichannel.
    """
    if not isinstance(grid, list):
        return False
    if not grid:
        return False
    first = grid[0]
    if not isinstance(first, list):
        return False
    if not first:
        return False
    return isinstance(first[0], list)


def channel_shape(channels: MultiChannelGrid) -> Tuple[int, int]:
    """``(h, w)`` shared across all channels; raises on mismatch."""
    if not channels:
        return (0, 0)
    h = len(channels[0])
    w = len(channels[0][0]) if channels[0] else 0
    for ch in channels[1:]:
        if len(ch) != h or (ch and len(ch[0]) != w):
            raise ValueError(
                f"multichannel: shape mismatch — got {h}x{w} vs {len(ch)}x"
                f"{len(ch[0]) if ch else 0}"
            )
    return (h, w)


def _to_channels(grid: Any) -> MultiChannelGrid:
    """Coerce a single grid *or* a multi-channel grid to a list of grids."""
    if is_multichannel(grid):
        return [g for g in grid]
    return [grid]


def make_multichannel(channels: Sequence[Grid]) -> MultiChannelGrid:
    """Build a multi-channel grid from a list of 2D grids.

    All channels must share the same shape; ``ValueError`` otherwise.
    """
    out: MultiChannelGrid = []
    for ch in channels:
        if not isinstance(ch, list) or not ch or not isinstance(ch[0], list):
            raise ValueError("make_multichannel: expected list of 2D grids")
        out.append([row[:] for row in ch])
    channel_shape(out)   # validate via the public shape check
    return out


def extract_channel(grid: Any, i: int) -> Grid:
    """Return the ``i``-th channel; for single grids, ``i`` must be ``0``."""
    chs = _to_channels(grid)
    if not 0 <= i < len(chs):
        raise IndexError(f"extract_channel: index {i} out of range ({len(chs)})")
    return [row[:] for row in chs[i]]


def combine_channels(channels: Sequence[Grid]) -> MultiChannelGrid:
    """Combine ``channels`` (a list of 2D grids) into a multi-channel grid."""
    return make_multichannel(channels)


def project_luminance(grid: Any) -> Grid:
    """Collapse a multi-channel grid to a single grid via cell-wise mean.

    For a single grid, returns a deep copy. The mean is rounded to the
    nearest int so the result stays in the canonical ARC palette ``[0, 9]``.
    """
    chs = _to_channels(grid)
    h, w = channel_shape(chs)
    out: Grid = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            total = sum(ch[r][c] for ch in chs)
            out[r][c] = int(round(total / len(chs)))
    return out