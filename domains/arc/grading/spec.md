# Hierarchical Grading Specification for ARC Tasks

Version 1.0 — applies to synthetic ARC tasks and any grid-pair (predicted, ground truth).

## 1. Purpose

The official ARC-AGI leaderboard awards credit only when the predicted output grid equals
the ground-truth output grid cell-by-cell. This under-counts near-miss solutions that:

* get the shape and object structure right but mis-color one or two cells,
* get everything right except the color palette (recolored but bijectively),
* get everything right except the orientation (rotated or flipped),
* get the high-level structure right but introduce local noise.

The hierarchical grader below assigns **partial credit** along three tiers that mirror how
ARC puzzles are typically authored and how human solvers recognize near-misses.

## 2. Tier definitions

### Tier 1 — Exact match (weight `1.0`)

`predicted == ground_truth` element-wise. No transformation is applied. This is the
official ARC credit.

### Tier 2 — Equivalence-class match (weight `0.7`)

The predicted grid equals the ground truth **up to one of a documented set of
invariances**. The grader tries each allowed invariance in turn and accepts tier 2 if
any of them makes the grids identical.

Documented invariance classes:

| Symbol  | Name                       | Meaning                                                                                |
|---------|----------------------------|----------------------------------------------------------------------------------------|
| `id`    | Identity                   | No transformation (already covered by tier 1, listed for completeness).                |
| `pal`   | Palette permutation          | Bijective recoloring between predicted and ground truth color sets.                    |
| `rot90` | 90° rotation               | Rotate the grid 90° clockwise.                                                         |
| `rot180`| 180° rotation              | Rotate the grid 180°.                                                                  |
| `rot270`| 270° rotation              | Rotate the grid 270° clockwise (equivalently 90° counter-clockwise).                    |
| `fh`    | Horizontal flip            | Mirror left-right.                                                                     |
| `fv`    | Vertical flip              | Mirror top-down.                                                                       |
| `tr`    | Translation within bounds  | Shift by an integer offset `(dy, dx)` such that the shifted grid still fits.           |

Per-task invariance selection is configured through `task_metadata["invariances"]`. The
default task type applies **all** of the above. Recommended overrides:

* `color-by-example` tasks: invariances = `{"id", "pal"}` — rotation/flip changes the
  color-keyed regions and should not be rewarded.
* `symmetry-completion` tasks: invariances = `{"id", "rot90", "rot180", "rot270", "fh", "fv"}`
  — palette is fixed by the example pairs.
* `shape-completion` tasks: invariances = `{"id"}` — only tier 1 credit; partial credit
  is still possible via tier 3.
* `translation-puzzle` tasks: invariances = `{"id", "tr"}`.

### Tier 3 — Structural match (weight `0.3`)

The predicted grid has the same structural skeleton as the ground truth but differs at
the cell level. Tier 3 requires all of the following:

1. **Shape parity**: same `(height, width)`.
2. **Object-count parity**: connected-component count of non-background cells (4-connectivity,
   background = `0`) is within a small tolerance (default `±1`).
3. **Cell-match rate** after **best palette alignment** is at least `0.6`.

Palette sets may differ between predicted and ground truth — for example, the prediction
might use new color IDs that the ground truth doesn't have. The grader always runs a
best-effort palette alignment (brute force for small palettes, greedy intersection-based
otherwise) and uses the resulting cell-match rate to decide tier 3.

Brute force is run when:
* the non-background palette has at most 7 unique colors, AND
* the predicted and ground-truth non-background palettes have the same size (so a full
  bijection is enumerable).

If either condition fails, the grader falls back to greedy alignment (each predicted
color is mapped to the unused ground-truth color with the highest cell-intersection
count). Greedy alignment is `O(C_p * C_g)` and works for any palette size.

## 3. Scoring rule

For each `(predicted, ground_truth)` pair:

```
score = 1.0   if exact_match(predicted, ground_truth)
      = 0.7   elif equivalence_match(predicted, ground_truth, invariances)
      = 0.3   elif structural_match(predicted, ground_truth)
      = 0.0   otherwise
```

**Strict mode.** If `task_metadata["strict"]` is `True`, only tier 1 counts. Tiers 2 and
3 are skipped entirely. This is recommended for `shape-completion` tasks where partial
credit would be misleading.

Aggregation across test examples of a task follows the standard ARC convention:

* `task_score = mean(score_i over test examples i)`
* `strict_score = mean(score_i over examples that hit tier 1)`, or `None` if none did.

The grader returns a dict:

```
{
  "tier":           1 | 2 | 3 | 0,
  "score":          float,
  "per_example":    [ {"tier", "score", "matched_invariance", "cell_match", "object_iou"}, ... ],
  "task_score":     float,
  "strict":         float | None,
  "invariances":    [...],
}
```

## 4. Algorithmic notes

* **Palette permutation** is implemented with a brute-force search for `len(palette) ≤ 7`
  non-background colors and a greedy IoU-based fallback otherwise. Both are deterministic.
* **Connected components** use `scipy.ndimage.label` with a 4-connectivity structure.
* **Translation within bounds** is implemented as an exhaustive scan of integer offsets
  that keep the shifted grid inside the original bounds — this is `O(H*W)` and is
  bounded by `H*W` candidate offsets.
* **No mutation**: all transformations return new grids; inputs are not modified.

## 5. Limitations (intentional, in scope notes)

* Translation is only useful when the task explicitly fixes the output grid size; ARC
  test outputs have variable size, so `tr` invariance is rarely active in practice.
* Palette permutation does not handle partial overlaps gracefully when the predicted and
  ground-truth palettes differ in size by more than 1 — it falls back to direct cell-match
  scoring.
* Reflection along diagonals (`fd`, anti-diagonal) is omitted — the four documented
  orientation invariances (`rot90`, `rot180`, `rot270`, `fh`, `fv`) cover the dominant
  cases in the ARC corpus.

## 6. Acceptance test plan

The unit tests (`test_grader.py`) cover:

* Tier 1: identical grids → tier 1, score 1.0.
* Tier 2: palette-recolored → tier 2 (not tier 1).
* Tier 2: rotated 90° → tier 2 when rotation is in invariances.
* Tier 2: palette-permutation on a default task still hits tier 2.
* Tier 3: 2 cells swapped → tier 3.
* Tier 3 boundary: ≥ 60% cell match, object count within tolerance.
* Tier 0: completely wrong → tier 0.
* Partial-credit ordering: tier 3 < tier 2 < tier 1.
* Aggregation: `task_score` is the mean over examples.

The demo (`demo.py`) prints a tier-by-tier breakdown for six synthetic ARC tasks that
exercise each path above.