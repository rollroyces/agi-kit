"""Hierarchical ARC grader — three tiers, partial credit for near-misses.

See spec.md for the tier definitions, invariance classes, scoring rule, and limitations.
"""
from __future__ import annotations

from itertools import permutations
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage


# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_INVARIANCES: Tuple[str, ...] = (
    "id", "pal", "rot90", "rot180", "rot270", "fh", "fv", "tr",
)

INVARIANCE_LABELS: Dict[str, str] = {
    "id": "identity",
    "pal": "palette permutation",
    "rot90": "90 deg rotation",
    "rot180": "180 deg rotation",
    "rot270": "270 deg rotation",
    "fh": "horizontal flip",
    "fv": "vertical flip",
    "tr": "translation within bounds",
}

TIER_WEIGHTS: Dict[int, float] = {1: 1.0, 2: 0.7, 3: 0.3, 0: 0.0}

TIER3_CELL_MATCH_THRESHOLD: float = 0.6
TIER3_OBJECT_COUNT_TOLERANCE: int = 1
PALETTE_PERM_SEARCH_LIMIT: int = 7  # max non-background colors for brute-force perm search


# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

Grid = np.ndarray  # 2D int array


def _to_grid(g: Any) -> Grid:
    """Coerce input into a 2D int numpy array."""
    if isinstance(g, np.ndarray):
        arr = g
    else:
        arr = np.asarray(g)
    if arr.ndim != 2:
        raise ValueError(f"Grid must be 2D; got shape {arr.shape}")
    if not np.issubdtype(arr.dtype, np.integer):
        arr = arr.astype(np.int64)
    return arr


def _as_list(g: Any) -> List[List[int]]:
    """Coerce input into a list-of-lists of ints (useful for printing)."""
    return _to_grid(g).tolist()


# ---------------------------------------------------------------------------
# Transformation primitives
# ---------------------------------------------------------------------------

def transform(grid: Any, kind: str) -> Grid:
    """Apply a single invariance transform. Returns a new grid."""
    g = _to_grid(grid)
    if kind == "id":
        return g.copy()
    if kind == "rot90":
        return np.rot90(g, k=-1)  # -1 -> 90 deg clockwise (matches the spec table)
    if kind == "rot180":
        return np.rot90(g, k=2)
    if kind == "rot270":
        return np.rot90(g, k=1)
    if kind == "fh":
        return np.fliplr(g)
    if kind == "fv":
        return np.flipud(g)
    raise ValueError(f"Unknown transform kind: {kind!r}")


def _all_translations(grid: Grid) -> List[Grid]:
    """Yield every integer translation of `grid` that stays within its original bounds.

    Only non-background cells are moved; background cells stay background. This is
    the ARC-style "object translation" interpretation.
    """
    h, w = grid.shape
    out: List[Grid] = []
    nz = np.argwhere(grid != 0)  # positions of non-background cells
    if len(nz) == 0:
        return [grid.copy()]
    for dy in range(-(h - 1), h):
        for dx in range(-(w - 1), w):
            shifted = np.zeros_like(grid)
            new_pos = nz + np.array([dy, dx])
            # Bounds check
            if np.any(new_pos[:, 0] < 0) or np.any(new_pos[:, 0] >= h):
                continue
            if np.any(new_pos[:, 1] < 0) or np.any(new_pos[:, 1] >= w):
                continue
            for (y, x), (ny, nx) in zip(nz, new_pos):
                shifted[ny, nx] = grid[y, x]
            out.append(shifted)
    return out


# ---------------------------------------------------------------------------
# Tier 1 — exact match
# ---------------------------------------------------------------------------

def exact_match(predicted: Any, ground_truth: Any) -> bool:
    """Tier 1: predicted grid is identical to ground truth cell-by-cell."""
    p = _to_grid(predicted)
    g = _to_grid(ground_truth)
    if p.shape != g.shape:
        return False
    return bool(np.array_equal(p, g))


# ---------------------------------------------------------------------------
# Palette alignment (shared by tier 2 and tier 3)
# ---------------------------------------------------------------------------

def _apply_mapping(grid: Grid, mapping: Dict[int, int]) -> Grid:
    out = grid.copy()
    for src, dst in mapping.items():
        out[grid == src] = dst
    return out


def _greedy_palette_align(p: Grid, g: Grid) -> Tuple[Dict[int, int], float]:
    """Greedy intersection-based palette alignment for palettes of any size.

    For each predicted color, pick the unused ground-truth color with the highest
    cell-intersection count (cells where pred has p_color and gt has g_color).
    Returns the resulting mapping and cell-match rate.
    """
    p_colors = [int(x) for x in np.unique(p)]
    g_colors = [int(x) for x in np.unique(g)]
    remaining_g = set(g_colors)
    mapping: Dict[int, int] = {}

    # Background anchor if present in both
    if 0 in p_colors and 0 in g_colors:
        mapping[0] = 0
        remaining_g.discard(0)

    # Order predicted colors by descending frequency (largest first is most informative)
    order = sorted(p_colors, key=lambda c: -int(np.sum(p == c)))
    for c in order:
        if c in mapping:
            continue
        best_g, best_count = None, -1
        for gc in remaining_g:
            count = int(np.sum((p == c) & (g == gc)))
            if count > best_count:
                best_count, best_g = count, gc
        if best_g is None:
            continue
        mapping[c] = best_g
        remaining_g.discard(best_g)

    recolored = _apply_mapping(p, mapping)
    rate = float(np.mean(recolored == g))
    return mapping, rate


def _palette_perm_align(p: Grid, g: Grid) -> Optional[Tuple[Dict[int, int], float]]:
    """Brute-force palette alignment by enumerating bijections.

    Returns `(mapping, rate)` for the best bijection, or `None` if the non-background
    palette is too large or otherwise can't be enumerated (caller should fall back to
    greedy).
    """
    p_colors = sorted(int(x) for x in np.unique(p) if x != 0)
    g_colors = sorted(int(x) for x in np.unique(g) if x != 0)
    p_has_bg = 0 in p
    g_has_bg = 0 in g
    if p_has_bg != g_has_bg:
        # background presence mismatch — palette perm can't fix it
        return None

    if not p_colors:
        # only background colors — trivially identity if grid == ground truth
        return ({0: 0} if p_has_bg else {}, 1.0 if np.array_equal(p, g) else 0.0)

    if len(p_colors) > PALETTE_PERM_SEARCH_LIMIT:
        return None  # caller falls back to greedy

    # Different non-zero color counts -> can't fully enumerate bijections.
    if len(p_colors) != len(g_colors):
        return None  # caller falls back to greedy

    # Quick reject: if there are no permutations (shouldn't happen now since sizes
    # match, but guard anyway).
    perms = list(permutations(g_colors, len(p_colors)))
    if not perms:
        return None

    best: Tuple[Dict[int, int], float] = ({}, -1.0)
    for perm in perms:
        mapping: Dict[int, int] = {}
        if p_has_bg:
            mapping[0] = 0
        for src, dst in zip(p_colors, perm):
            mapping[src] = dst
        recolored = _apply_mapping(p, mapping)
        rate = float(np.mean(recolored == g))
        if rate > best[1]:
            best = (mapping, rate)
    return best


def _palette_align_metric(p: Grid, g: Grid) -> Tuple[Dict[int, int], float]:
    """Best-effort palette alignment. Returns (mapping, cell-match-rate).

    Tries brute force first; falls back to greedy. Always returns a value.
    """
    aligned = _palette_perm_align(p, g)
    if aligned is None:
        return _greedy_palette_align(p, g)
    return aligned


# ---------------------------------------------------------------------------
# Tier 2 — equivalence-class match
# ---------------------------------------------------------------------------

def _palette_perm_exact_match(predicted: Any, ground_truth: Any) -> Optional[Dict[int, int]]:
    """Return the palette-permutation mapping that makes predicted equal ground truth exactly,
    or None if no such bijection exists."""
    p = _to_grid(predicted)
    g = _to_grid(ground_truth)
    if p.shape != g.shape:
        return None
    aligned = _palette_align_metric(p, g)
    mapping, rate = aligned
    if rate >= 1.0 - 1e-9:
        return mapping
    return None


def equivalence_match(
    predicted: Any,
    ground_truth: Any,
    invariances: Optional[Sequence[str]] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[int, int]]]:
    """Tier 2: return (matched, invariance_used, palette_mapping_or_None).

    Tries each invariance in `invariances` (default: all). The first that produces an
    exact match wins. Palette permutation is checked separately because it carries
    a mapping payload; geometric invariances do not.
    """
    if invariances is None:
        invariances = DEFAULT_INVARIANCES
    invariances = tuple(invariances)

    p = _to_grid(predicted)
    g = _to_grid(ground_truth)

    # Geometric transforms (and translation) reshape `predicted`; we compare against `g`.
    for kind in invariances:
        if kind == "pal":
            continue  # handled below
        if kind == "tr":
            for shifted in _all_translations(p):
                if shifted.shape == g.shape and np.array_equal(shifted, g):
                    return True, "tr", None
            continue
        if kind in ("id", "rot90", "rot180", "rot270", "fh", "fv"):
            if kind == "id":
                continue  # tier 1 already covered; tier 2 never needs "id"
            t = transform(p, kind)
            if t.shape == g.shape and np.array_equal(t, g):
                return True, kind, None
            continue

    # Palette permutation (separate because of the mapping payload)
    if "pal" in invariances:
        mapping = _palette_perm_exact_match(p, g)
        if mapping is not None:
            return True, "pal", mapping

    return False, None, None


# ---------------------------------------------------------------------------
# Tier 3 — structural match
# ---------------------------------------------------------------------------

def _count_objects(grid: Grid, background: int = 0) -> int:
    mask = (grid != background).astype(np.int8)
    _, n = ndimage.label(mask, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    return int(n)


def structural_match(
    predicted: Any,
    ground_truth: Any,
    cell_match_threshold: float = TIER3_CELL_MATCH_THRESHOLD,
    object_count_tolerance: int = TIER3_OBJECT_COUNT_TOLERANCE,
) -> Tuple[bool, Dict[str, Any]]:
    """Tier 3: structural partial credit.

    Tier 3 requires:
      1. Shape parity (same H, W).
      2. Object-count parity within `object_count_tolerance`.
      3. Cell-match rate after best palette alignment >= `cell_match_threshold`.

    Palettes may differ (e.g., cells changed to new colors); alignment absorbs the
    difference. Returns `(matched, info)` where `info` contains diagnostic fields.
    """
    p = _to_grid(predicted)
    g = _to_grid(ground_truth)

    info: Dict[str, Any] = {
        "shape_ok": bool(p.shape == g.shape),
        "object_count_pred": 0,
        "object_count_gt": 0,
        "cell_match_rate": 0.0,
        "object_iou": 0.0,
        "mapping": {},
    }

    if not info["shape_ok"]:
        return False, info

    info["object_count_pred"] = _count_objects(p)
    info["object_count_gt"] = _count_objects(g)
    count_ok = abs(info["object_count_pred"] - info["object_count_gt"]) <= object_count_tolerance

    mapping, rate = _palette_align_metric(p, g)
    info["mapping"] = mapping
    info["cell_match_rate"] = rate

    recolored = _apply_mapping(p, mapping)
    p_mask = (recolored != 0)
    g_mask = (g != 0)
    inter = int(np.sum(p_mask & g_mask))
    union = int(np.sum(p_mask | g_mask))
    info["object_iou"] = inter / union if union else 0.0

    ok = count_ok and rate >= cell_match_threshold
    return bool(ok), info


# ---------------------------------------------------------------------------
# Top-level grading
# ---------------------------------------------------------------------------

def grade_example(
    predicted: Any,
    ground_truth: Any,
    invariances: Optional[Sequence[str]] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """Grade a single (predicted, ground_truth) pair.

    Parameters
    ----------
    predicted, ground_truth : the two grids to compare.
    invariances : sequence of invariance kinds used for tier 2.
    strict : if True, only tier 1 (exact match) counts; tiers 2 and 3 are disabled.
             This matches the "shape-completion" task style where colors must match
             exactly and partial credit is not awarded.

    Returns a dict with:
        tier (1|2|3|0), score (float), matched_invariance (str|None),
        palette_mapping (dict|None), cell_match (float), object_iou (float),
        object_count_pred (int), object_count_gt (int).
    """
    invariances = tuple(invariances) if invariances is not None else DEFAULT_INVARIANCES

    # Tier 1
    if exact_match(predicted, ground_truth):
        return {
            "tier": 1,
            "score": TIER_WEIGHTS[1],
            "matched_invariance": "id",
            "palette_mapping": None,
            "cell_match": 1.0,
            "object_iou": 1.0,
            "object_count_pred": _count_objects(_to_grid(predicted)),
            "object_count_gt": _count_objects(_to_grid(ground_truth)),
        }

    # Strict mode: only tier 1 counts
    if strict:
        info = structural_match(predicted, ground_truth)[1]  # for diagnostics
        return {
            "tier": 0,
            "score": TIER_WEIGHTS[0],
            "matched_invariance": None,
            "palette_mapping": None,
            "cell_match": info["cell_match_rate"],
            "object_iou": info["object_iou"],
            "object_count_pred": info["object_count_pred"],
            "object_count_gt": info["object_count_gt"],
        }

    # Tier 2
    matched, kind, mapping = equivalence_match(predicted, ground_truth, invariances)
    if matched:
        return {
            "tier": 2,
            "score": TIER_WEIGHTS[2],
            "matched_invariance": kind,
            "palette_mapping": mapping,
            "cell_match": 1.0,
            "object_iou": 1.0,
            "object_count_pred": _count_objects(_to_grid(predicted)),
            "object_count_gt": _count_objects(_to_grid(ground_truth)),
        }

    # Tier 3
    ok, info = structural_match(predicted, ground_truth)
    if ok:
        return {
            "tier": 3,
            "score": TIER_WEIGHTS[3],
            "matched_invariance": None,
            "palette_mapping": info["mapping"],
            "cell_match": info["cell_match_rate"],
            "object_iou": info["object_iou"],
            "object_count_pred": info["object_count_pred"],
            "object_count_gt": info["object_count_gt"],
        }

    # Tier 0 — fall-through
    return {
        "tier": 0,
        "score": TIER_WEIGHTS[0],
        "matched_invariance": None,
        "palette_mapping": None,
        "cell_match": info["cell_match_rate"],
        "object_iou": info["object_iou"],
        "object_count_pred": info["object_count_pred"],
        "object_count_gt": info["object_count_gt"],
    }


def grade(
    predicted: Sequence[Any],
    ground_truth: Sequence[Any],
    task_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Top-level grading across multiple test examples.

    Parameters
    ----------
    predicted : sequence of grids (any array-like of array-likes).
    ground_truth : sequence of grids of the same length.
    task_metadata : optional dict; supports:
        invariances (sequence of str): default `DEFAULT_INVARIANCES`.

    Returns
    -------
    dict with:
        per_example : list of `grade_example` results.
        task_score  : mean of per-example scores.
        strict      : mean restricted to examples that hit tier 1 (or None if none).
        invariances : the invariance list actually used.
    """
    if len(predicted) != len(ground_truth):
        raise ValueError(
            f"predicted/ground_truth length mismatch: {len(predicted)} vs {len(ground_truth)}"
        )

    meta = dict(task_metadata or {})
    invariances = tuple(meta.get("invariances") or DEFAULT_INVARIANCES)
    strict = bool(meta.get("strict", False))

    per_example: List[Dict[str, Any]] = []
    for p, g in zip(predicted, ground_truth):
        per_example.append(grade_example(p, g, invariances=invariances, strict=strict))

    scores = [r["score"] for r in per_example]
    task_score = float(np.mean(scores)) if scores else 0.0
    tier1_scores = [r["score"] for r in per_example if r["tier"] == 1]
    strict = float(np.mean(tier1_scores)) if tier1_scores else None

    return {
        "per_example": per_example,
        "task_score": task_score,
        "strict": strict,
        "invariances": list(invariances),
    }


__all__ = [
    "DEFAULT_INVARIANCES",
    "INVARIANCE_LABELS",
    "TIER_WEIGHTS",
    "TIER3_CELL_MATCH_THRESHOLD",
    "TIER3_OBJECT_COUNT_TOLERANCE",
    "PALETTE_PERM_SEARCH_LIMIT",
    "exact_match",
    "equivalence_match",
    "structural_match",
    "grade_example",
    "grade",
    "transform",
]