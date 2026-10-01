# Hierarchical ARC Grader

Three-tier partial-credit grader for ARC tasks. Assigns `1.0` for exact match,
`0.7` for equivalence-class match (palette perm / rotation / flip / translation),
and `0.3` for structural near-miss. Falls to `0.0` when nothing else applies.

The motivation and tier definitions live in [`spec.md`](spec.md). This README
covers installation, usage, and how to pick the right invariance per task type.

## Files

| File             | Purpose                                                    |
|------------------|------------------------------------------------------------|
| `spec.md`        | Design document — tier definitions, invariance classes    |
| `grader.py`      | Implementation: `exact_match`, `equivalence_match`,        |
|                  | `structural_match`, `grade_example`, `grade`, `transform`  |
| `test_grader.py` | Unit tests covering all 3 tiers and partial-credit paths   |
| `demo.py`        | Runs the grader on 8 synthetic ARC tasks + task aggregation |
| `README.md`      | This file                                                   |

## Quick start

```bash
# Run the unit tests (28 tests, ~0.02s)
python -m unittest test_grader.py -v

# Run the demo
python demo.py
```

The implementation depends only on `numpy` and `scipy`. No other third-party
packages are required (no `pytest`, no `scikit-learn`).

## API surface

```python
import numpy as np
from grader import grade_example, grade

# Single (predicted, ground_truth) pair
result = grade_example(pred, gt)
# -> {"tier": 1|2|3|0, "score": float, "matched_invariance": str|None,
#     "palette_mapping": dict|None, "cell_match": float,
#     "object_iou": float, "object_count_pred": int, "object_count_gt": int}

# Multiple test examples of a task
result = grade(
    [pred1, pred2, pred3],
    [gt1, gt2, gt3],
    task_metadata={"invariances": ("id", "pal", "rot90", "rot180",
                                   "rot270", "fh", "fv", "tr"),
                   "strict": False},
)
# -> {"per_example": [...], "task_score": float, "strict": float|None,
#     "invariances": [...]}
```

`task_score` is the mean of per-example scores (the ARC convention).
`strict` is the mean restricted to examples that hit tier 1, or `None` if none
did.

## The three tiers

### Tier 1 (weight 1.0) — exact match
Predicted grid equals ground truth cell-by-cell. No transformation.

### Tier 2 (weight 0.7) — equivalence-class match
Predicted grid matches ground truth under one of a documented set of invariances.
The first matching invariance wins.

Invariance classes:

| Code     | Meaning                                       |
|----------|-----------------------------------------------|
| `pal`    | bijective recoloring                          |
| `rot90`  | 90 deg rotation                               |
| `rot180` | 180 deg rotation                              |
| `rot270` | 270 deg rotation                              |
| `fh`     | horizontal flip (mirror left-right)           |
| `fv`     | vertical flip (mirror top-down)               |
| `tr`     | translation of non-background cells within bounds |

### Tier 3 (weight 0.3) — structural match
Same shape, same object count (within tolerance), and cell-match rate
**>= 0.6** after best palette alignment. Palette alignment uses brute-force
bijection search for small palettes (<= 7 colors) and falls back to a greedy
intersection-based alignment otherwise.

## Choosing invariances per task type

Tasks differ on which transformations count as equivalent answers. Set
`task_metadata["invariances"]` accordingly:

* **`color-by-example`** — `("id", "pal")`. The example pairs fix the color
  palette; rotation / flip changes the color-keyed regions.
* **`symmetry-completion`** — `("id", "rot90", "rot180", "rot270", "fh", "fv")`.
  The palette is fixed; orientations may permute.
* **`shape-completion`** — `("id",)` plus `task_metadata["strict"]=True`. Only
  exact match counts; tier 3 is disabled.
* **`translation-puzzle`** — `("id", "tr")`. Translation within bounds is the
  expected equivalence.
* **Default / unknown** — `DEFAULT_INVARIANCES`, all of the above.

`task_metadata["strict"]=True` further disables tier 3 (structural partial credit).
This is recommended for `shape-completion` tasks where partial credit would be
misleading.

## When does a "swap" hit tier 2 vs tier 3?

A common confusion: a prediction that swaps two colors can be tier 2 (palette
permutation) or tier 3 (structural), depending on the task.

* If the task allows palette permutation (most `color-by-example` and the
  default invariance set), a two-color swap hits tier 2 because the bijection
  `{3:4, 4:3}` makes the recolored prediction equal the ground truth.
* If the task explicitly disables palette permutation (invariances without
  `"pal"`) AND enables strict mode, the same swap falls to tier 0.
* If the task disables palette permutation but keeps structural partial
  credit on, the same swap still hits tier 3 because cell-match rate is
  high after alignment.

## Examples (run from `demo.py`)

| Case | Description                                  | Tier | Score |
|------|----------------------------------------------|------|-------|
| 1    | Exact match                                  | 1    | 1.00  |
| 2    | Bijective palette recolor (1->5, ...)        | 2    | 0.70  |
| 3    | 90 deg rotation of an asymmetric grid        | 2    | 0.70  |
| 4    | Horizontal flip                              | 2    | 0.70  |
| 5    | Two-color swap (palette perm)                | 2    | 0.70  |
| 6    | Two cells changed to new colors + extra cell | 3    | 0.30  |
| 7    | Object translated within bounds              | 2    | 0.70  |
| 8    | Completely different cells                   | 0    | 0.00  |

## Limitations (also see `spec.md` section 5)

* Palette permutation brute-force is capped at 7 non-background colors; above
  that, greedy alignment is used (still correct, possibly sub-optimal).
* Diagonal reflections are not in the invariance set.
* Translation only moves non-background cells; background is preserved.
* Tier 3 cell-match threshold (`0.6`) and object-count tolerance (`1`) are
  hard-coded but exposed as function arguments.
* Tier 3 structural alignment always uses palette permutation to align colors
  before comparing, even when `invariances` excludes `"pal"`. If you need to
  fully disable palette-based alignment, set `strict=True`.

## Validation

`python -m unittest test_grader.py -v` runs 28 tests across:

* Tier 1 (4 tests): identity true/false, shape mismatch, score and matched label.
* Tier 2 (10 tests): palette perm, palette perm-not-tier-1, color swap, 4 rotations,
  2 flips, invariance filtering, strict mode.
* Tier 3 (5 tests): structural near-miss, shape mismatch blocks tier 3,
  threshold above and below, object-count tolerance.
* Tier 0 (1 test): completely wrong.
* Aggregation (4 tests): task score mean, strict score, strict=None, metadata overrides.
* Partial-credit ordering (1 test): tier weights strictly decreasing.
* Invariance enum (2 tests): all documented invariances labelled, translation matching.

All 28 tests pass.