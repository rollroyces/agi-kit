"""Demo: run the hierarchical grader on synthetic ARC tasks and print tier-by-tier scoring.

Run with: `python demo.py` from this directory.
"""
from __future__ import annotations

import numpy as np

import grader


# ---------------------------------------------------------------------------
# Helpers for pretty printing
# ---------------------------------------------------------------------------

SYM = {
    0: " . ", 1: " 1 ", 2: " 2 ", 3: " 3 ", 4: " 4 ",
    5: " 5 ", 6: " 6 ", 7: " 7 ", 8: " 8 ", 9: " 9 ",
}


def _render(grid: np.ndarray) -> str:
    rows = ["".join(SYM.get(int(v), f"{int(v):3d} ") for v in row) for row in grid]
    return "\n".join(rows)


def _hr(width: int = 70) -> str:
    return "-" * width


def _print_case(idx: int, title: str, predicted, ground_truth, metadata=None) -> None:
    p = np.asarray(predicted, dtype=np.int64)
    g = np.asarray(ground_truth, dtype=np.int64)
    result = grader.grade([p], [g], task_metadata=metadata)[0] if False else \
        grader.grade_example(p, g, **(metadata or {}))

    print(_hr())
    print(f"[Case {idx}] {title}")
    print(_hr())
    print("Ground truth:")
    print(_render(g))
    print()
    print("Prediction:")
    print(_render(p))
    print()
    inv_label = grader.INVARIANCE_LABELS.get(result["matched_invariance"] or "", "-")
    print(
        f"  tier={result['tier']}  score={result['score']:.2f}  "
        f"matched={inv_label}  "
        f"cell_match={result['cell_match']:.2f}  "
        f"object_iou={result['object_iou']:.2f}  "
        f"objects(pred/gt)={result['object_count_pred']}/{result['object_count_gt']}"
    )
    if result["palette_mapping"]:
        mapping_str = ", ".join(
            f"{s}->{d}" for s, d in sorted(result["palette_mapping"].items())
        )
        print(f"  palette mapping: {mapping_str}")
    print()


# ---------------------------------------------------------------------------
# Six synthetic ARC tasks
# ---------------------------------------------------------------------------

G_GROUND = np.array(
    [
        [0, 0, 0, 0, 0],
        [0, 1, 0, 2, 0],
        [0, 0, 0, 0, 0],
        [0, 3, 0, 4, 0],
        [0, 0, 0, 0, 0],
    ],
    dtype=np.int64,
)


def case_1_exact():
    return ("Exact match", G_GROUND.copy(), G_GROUND.copy())


def case_2_palette_recolor():
    pred = np.array(
        [
            [0, 0, 0, 0, 0],
            [0, 5, 0, 6, 0],
            [0, 0, 0, 0, 0],
            [0, 7, 0, 8, 0],
            [0, 0, 0, 0, 0],
        ],
        dtype=np.int64,
    )
    return ("Bijective palette recolor (1->5, 2->6, 3->7, 4->8)", pred, G_GROUND.copy())


def case_3_rotation():
    # Asymmetric 4x4 grid whose 90-deg rotation is non-trivial
    gt = np.array(
        [
            [0, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 2, 0],
            [0, 0, 0, 3],
        ],
        dtype=np.int64,
    )
    pred = np.rot90(gt, k=-1)  # 90 deg clockwise rotation
    return ("90 deg rotation of an asymmetric grid", pred, gt)


def case_4_horizontal_flip():
    pred = np.fliplr(G_GROUND)
    return ("Horizontal flip", pred, G_GROUND.copy())


def case_5_color_swap():
    pred = np.array(
        [
            [0, 0, 0, 0, 0],
            [0, 1, 0, 2, 0],
            [0, 0, 0, 0, 0],
            [0, 4, 0, 3, 0],
            [0, 0, 0, 0, 0],
        ],
        dtype=np.int64,
    )
    return ("Color swap of objects 3 and 4 (palette perm -> tier 2)", pred, G_GROUND.copy())


def case_6_structural_partial():
    # 2 cells changed to new color IDs and 1 extra cell.
    pred = np.array(
        [
            [0, 0, 0, 0, 0],
            [0, 5, 0, 2, 0],   # (1,1) was 1, now 5 (new color)
            [0, 0, 7, 0, 0],   # (2,2) is a NEW object
            [0, 6, 0, 4, 0],   # (3,1) was 3, now 6 (new color)
            [0, 0, 0, 0, 0],
        ],
        dtype=np.int64,
    )
    return ("Cells changed to new colors + 1 extra cell (structural partial)", pred, G_GROUND.copy())


def case_7_translation():
    gt = np.array(
        [
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
        ],
        dtype=np.int64,
    )
    pred = np.array(
        [
            [0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
        ],
        dtype=np.int64,
    )
    return ("Object translated within bounds", pred, gt)


def case_8_completely_wrong():
    pred = np.array(
        [
            [9, 9, 9, 9, 9],
            [9, 0, 0, 0, 9],
            [9, 0, 0, 0, 9],
            [9, 0, 0, 0, 9],
            [9, 9, 9, 9, 9],
        ],
        dtype=np.int64,
    )
    return ("Completely different shape of cells (no partial credit)", pred, G_GROUND.copy())


# ---------------------------------------------------------------------------
# Aggregation example: a multi-example "task"
# ---------------------------------------------------------------------------

def task_summary():
    # A synthetic ARC task with three test examples
    print()
    print("=" * 70)
    print("Task-level aggregation (3 test examples)")
    title, p1, g1 = case_1_exact()
    _, p2, g2 = case_2_palette_recolor()
    _, p3, g3 = case_6_structural_partial()
    predicted = [p1, p2, p3]
    ground = [g1, g2, g3]
    result = grader.grade(predicted, ground)
    for i, r in enumerate(result["per_example"], 1):
        inv_label = grader.INVARIANCE_LABELS.get(r["matched_invariance"] or "", "-")
        print(
            f"  Example {i}: tier={r['tier']}  score={r['score']:.2f}  "
            f"matched={inv_label}  cell_match={r['cell_match']:.2f}"
        )
    print(f"  task_score (mean) = {result['task_score']:.3f}")
    print(f"  strict (tier-1 only) = {result['strict']}")
    print()


def main():
    cases = [
        case_1_exact,
        case_2_palette_recolor,
        case_3_rotation,
        case_4_horizontal_flip,
        case_5_color_swap,
        case_6_structural_partial,
        case_7_translation,
        case_8_completely_wrong,
    ]
    print("=" * 70)
    print("Hierarchical ARC grader - demo on synthetic tasks")
    print("=" * 70)
    for i, c in enumerate(cases, 1):
        title, pred, gt = c()
        _print_case(i, title, pred, gt)
    task_summary()


if __name__ == "__main__":
    main()