"""Unit tests for the hierarchical ARC grader.

Run with: `python -m unittest test_grader.py` from this directory.

These tests exercise the three tiers and the partial-credit transitions using
synthetic ARC-shaped grids. They do NOT depend on real ARC task data.
"""
import unittest

import numpy as np

import grader


# ---------------------------------------------------------------------------
# Shared synthetic ARC tasks
# ---------------------------------------------------------------------------

# A small "four-object on background" grid; objects are single cells.
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

# Same grid, but the colors of object 3 and object 4 are swapped (still valid
# bijective recolor: {3:4, 4:3}). With default invariances (palette perm
# included) this is tier 2.
G_SWAP = np.array(
    [
        [0, 0, 0, 0, 0],
        [0, 1, 0, 2, 0],
        [0, 0, 0, 0, 0],
        [0, 4, 0, 3, 0],  # 3 and 4 swapped
        [0, 0, 0, 0, 0],
    ],
    dtype=np.int64,
)

# Same grid recolored: 1->5, 2->6, 3->7, 4->8 — valid palette permutation
# (different color IDs, same shape). Default invariances score this as tier 2.
G_RECOLOR = np.array(
    [
        [0, 0, 0, 0, 0],
        [0, 5, 0, 6, 0],
        [0, 0, 0, 0, 0],
        [0, 7, 0, 8, 0],
        [0, 0, 0, 0, 0],
    ],
    dtype=np.int64,
)

# Two cells changed to NEW color IDs not in G_GROUND's palette, plus an
# extra cell. Palette size differs from G_GROUND, so palette perm can't
# biject — falls through to tier 3 if rate >= threshold.
G_T3 = np.array(
    [
        [0, 0, 0, 0, 0],
        [0, 5, 0, 2, 0],   # (1,1) was 1, now 5 (new color)
        [0, 0, 7, 0, 0],   # (2,2) is a NEW cell
        [0, 6, 0, 4, 0],   # (3,1) was 3, now 6 (new color)
        [0, 0, 0, 0, 0],
    ],
    dtype=np.int64,
)

# Predicted that is completely different
G_RANDOM = np.array(
    [
        [9, 9, 9, 9, 9],
        [9, 0, 0, 0, 9],
        [9, 0, 0, 0, 9],
        [9, 0, 0, 0, 9],
        [9, 9, 9, 9, 9],
    ],
    dtype=np.int64,
)


# ---------------------------------------------------------------------------
# Tier 1
# ---------------------------------------------------------------------------

class TestTier1Exact(unittest.TestCase):
    def test_exact_match_true(self):
        self.assertTrue(grader.exact_match(G_GROUND, G_GROUND))

    def test_exact_match_false_on_recolor(self):
        # Palette-recolored grid is NOT an exact match — that's tier 2.
        self.assertFalse(grader.exact_match(G_RECOLOR, G_GROUND))

    def test_exact_match_false_on_shape_mismatch(self):
        wrong_shape = G_GROUND[:, :3]
        self.assertFalse(grader.exact_match(wrong_shape, G_GROUND))

    def test_grade_tier1(self):
        result = grader.grade_example(G_GROUND, G_GROUND)
        self.assertEqual(result["tier"], 1)
        self.assertAlmostEqual(result["score"], 1.0)
        self.assertEqual(result["matched_invariance"], "id")


# ---------------------------------------------------------------------------
# Tier 2 — equivalence-class match
# ---------------------------------------------------------------------------

class TestTier2Equivalence(unittest.TestCase):
    def test_palette_permutation(self):
        # G_RECOLOR is a bijective recolor of G_GROUND (sets {1,2,3,4} <-> {5,6,7,8}).
        matched, kind, mapping = grader.equivalence_match(G_RECOLOR, G_GROUND)
        self.assertTrue(matched)
        self.assertEqual(kind, "pal")
        self.assertIsNotNone(mapping)
        # Every source color should map to a ground-truth color.
        for src, dst in mapping.items():
            self.assertIn(dst, {0, 1, 2, 3, 4})

    def test_palette_permutation_not_tier1(self):
        # Same recolored grid scores tier 2, not tier 1.
        result = grader.grade_example(G_RECOLOR, G_GROUND)
        self.assertEqual(result["tier"], 2)
        self.assertAlmostEqual(result["score"], 0.7)
        self.assertEqual(result["matched_invariance"], "pal")

    def test_color_swap_is_tier2_via_palette_perm(self):
        # G_SWAP swaps colors 3 and 4. With palette perm in invariances, this is tier 2.
        result = grader.grade_example(G_SWAP, G_GROUND)
        self.assertEqual(result["tier"], 2)
        self.assertAlmostEqual(result["score"], 0.7)
        self.assertEqual(result["matched_invariance"], "pal")

    def test_90_rotation(self):
        src = np.array(
            [
                [0, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 2, 0],
                [0, 0, 0, 3],
            ],
            dtype=np.int64,
        )
        gt = np.rot90(src, k=-1)  # rotated 90 deg clockwise
        result = grader.grade_example(src, gt)
        self.assertEqual(result["tier"], 2)
        self.assertEqual(result["matched_invariance"], "rot90")
        self.assertAlmostEqual(result["score"], 0.7)

    def test_horizontal_flip(self):
        src = np.array(
            [
                [0, 0, 0, 0],
                [1, 0, 0, 2],
                [0, 0, 0, 0],
                [3, 0, 0, 4],
            ],
            dtype=np.int64,
        )
        gt = np.fliplr(src)
        result = grader.grade_example(src, gt)
        self.assertEqual(result["tier"], 2)
        self.assertEqual(result["matched_invariance"], "fh")
        self.assertAlmostEqual(result["score"], 0.7)

    def test_vertical_flip(self):
        src = np.array(
            [
                [0, 0, 0, 0],
                [1, 0, 0, 2],
                [0, 0, 0, 0],
                [3, 0, 0, 4],
            ],
            dtype=np.int64,
        )
        gt = np.flipud(src)
        result = grader.grade_example(src, gt)
        self.assertEqual(result["tier"], 2)
        self.assertEqual(result["matched_invariance"], "fv")

    def test_180_rotation(self):
        src = np.array(
            [
                [0, 0, 0, 0],
                [1, 0, 0, 2],
                [0, 0, 0, 0],
                [3, 0, 0, 4],
            ],
            dtype=np.int64,
        )
        gt = np.rot90(src, k=2)
        result = grader.grade_example(src, gt)
        self.assertEqual(result["tier"], 2)
        self.assertEqual(result["matched_invariance"], "rot180")

    def test_270_rotation(self):
        src = np.array(
            [
                [0, 0, 0, 0],
                [1, 0, 0, 2],
                [0, 0, 0, 0],
                [3, 0, 0, 4],
            ],
            dtype=np.int64,
        )
        gt = np.rot90(src, k=1)
        result = grader.grade_example(src, gt)
        self.assertEqual(result["tier"], 2)
        self.assertEqual(result["matched_invariance"], "rot270")

    def test_invariance_filtering_blocks_rotation(self):
        # "color-by-example" task: rotation is excluded, palette perm is allowed.
        # A 90-rotated G_GROUND has the same palette but different cell positions.
        # Palette perm alone (without rotation) does fix it because the palette
        # is identical — the cells' colors happen to align under a bijection.
        # The point of this test is that rotation isn't *needed*: palette perm
        # is sufficient. Verify it scores tier 2 via palette perm.
        invariances = ("id", "pal")
        result = grader.grade_example(
            np.rot90(G_GROUND, k=-1),
            G_GROUND,
            invariances=invariances,
        )
        self.assertEqual(result["tier"], 2)
        self.assertEqual(result["matched_invariance"], "pal")

    def test_invariance_filtering_blocks_palette_perm_when_excluded(self):
        # When palette perm is excluded (invariances = ("id",)), a palette-perm
        # equivalent prediction still falls through to tier 3 (structural) because
        # tier 3 alignment still uses palette alignment.
        result = grader.grade_example(
            G_RECOLOR, G_GROUND, invariances=("id",)
        )
        self.assertEqual(result["tier"], 3)

    def test_strict_flag_disables_partial_credit(self):
        # strict=True in task_metadata disables tiers 2 and 3.
        result = grader.grade([G_RECOLOR], [G_GROUND],
                              task_metadata={"invariances": ("id",), "strict": True})
        self.assertEqual(result["per_example"][0]["tier"], 0)


# ---------------------------------------------------------------------------
# Tier 3 — structural match
# ---------------------------------------------------------------------------

class TestTier3Structural(unittest.TestCase):
    def test_two_cells_changed_to_new_colors(self):
        # G_T3 has 2 cells changed to new colors and 1 extra cell.
        # Cell-match rate after alignment is high (>= 0.6), object counts differ
        # by 1 (within tolerance), shape matches → tier 3.
        result = grader.grade_example(G_T3, G_GROUND)
        self.assertEqual(result["tier"], 3)
        self.assertAlmostEqual(result["score"], 0.3)
        self.assertGreaterEqual(result["cell_match"], 0.6)

    def test_shape_mismatch_blocks_tier3(self):
        wrong_shape = G_GROUND[:, :3]
        ok, info = grader.structural_match(wrong_shape, G_GROUND)
        self.assertFalse(ok)
        self.assertFalse(info["shape_ok"])

    def test_palette_mismatch_still_scores(self):
        # If the palettes are identical but a couple of cells differ, structural
        # match returns a clear metric.
        weird = np.array(
            [
                [0, 0, 0],
                [1, 2, 3],
                [0, 0, 0],
            ],
            dtype=np.int64,
        )
        ok, info = grader.structural_match(weird, weird)
        self.assertTrue(ok)
        self.assertEqual(info["cell_match_rate"], 1.0)

    def test_threshold_above_and_below(self):
        # Two predictions against the same ground truth:
        #   - "above": most cells match after alignment -> tier 3
        #   - "below": few cells match -> tier 0
        gt = np.array(
            [
                [0, 0, 0, 0, 0],
                [0, 1, 0, 2, 0],
                [0, 0, 0, 0, 0],
                [0, 3, 0, 4, 0],
                [0, 0, 0, 0, 0],
            ],
            dtype=np.int64,
        )
        # Above threshold: change 2 cells to new colors. Palettes differ in size;
        # brute force falls back to greedy, which gives rate 23/25 = 0.92.
        above = gt.copy()
        above[1, 1] = 5  # was 1
        above[3, 1] = 6  # was 3
        ok_above, info_above = grader.structural_match(above, gt)
        self.assertGreaterEqual(info_above["cell_match_rate"], 0.6)
        self.assertTrue(ok_above)

        # Below threshold: 13 background cells still match, but the 4 objects are
        # at completely different positions and most cells disagree. Greedy aligns
        # by intersection but cannot fix positional errors -> rate ~ 0.52.
        below = np.array(
            [
                [9, 0, 9, 0, 9],
                [0, 9, 0, 9, 0],
                [9, 0, 9, 0, 9],
                [0, 9, 0, 9, 0],
                [9, 0, 9, 0, 9],
            ],
            dtype=np.int64,
        )
        ok_below, info_below = grader.structural_match(below, gt)
        self.assertLess(info_below["cell_match_rate"], 0.6)
        self.assertFalse(ok_below)

    def test_object_count_too_far_blocks_tier3(self):
        # A grid with many small objects vs one with a single big object —
        # object count delta exceeds tolerance, tier 3 must be blocked.
        gt = np.array(
            [
                [0, 0, 0, 0],
                [0, 1, 1, 0],
                [0, 1, 1, 0],
                [0, 0, 0, 0],
            ],
            dtype=np.int64,
        )
        pred = np.array(
            [
                [1, 0, 0, 1],
                [0, 0, 0, 0],
                [0, 0, 0, 0],
                [1, 0, 0, 1],
            ],
            dtype=np.int64,
        )
        ok, info = grader.structural_match(pred, gt)
        self.assertGreater(
            abs(info["object_count_pred"] - info["object_count_gt"]),
            grader.TIER3_OBJECT_COUNT_TOLERANCE,
        )
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# Tier 0 — no credit
# ---------------------------------------------------------------------------

class TestTier0Zero(unittest.TestCase):
    def test_completely_wrong(self):
        result = grader.grade_example(G_RANDOM, G_GROUND)
        self.assertEqual(result["tier"], 0)
        self.assertAlmostEqual(result["score"], 0.0)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

class TestAggregation(unittest.TestCase):
    def test_task_score_is_mean(self):
        # Example 1: exact        (1.0)
        # Example 2: palette perm (0.7)
        # Example 3: structural   (0.3)
        # Example 4: zero         (0.0)
        predicted = [G_GROUND, G_RECOLOR, G_T3, G_RANDOM]
        ground = [G_GROUND, G_GROUND, G_GROUND, G_GROUND]
        result = grader.grade(predicted, ground)
        self.assertAlmostEqual(result["task_score"], (1.0 + 0.7 + 0.3 + 0.0) / 4.0)
        self.assertEqual(len(result["per_example"]), 4)
        self.assertEqual([r["tier"] for r in result["per_example"]], [1, 2, 3, 0])

    def test_strict_score_only_tier1(self):
        predicted = [G_GROUND, G_RECOLOR, G_T3]
        ground = [G_GROUND, G_GROUND, G_GROUND]
        result = grader.grade(predicted, ground)
        self.assertEqual(result["strict"], 1.0)

    def test_strict_score_none_when_no_tier1(self):
        predicted = [G_RECOLOR, G_T3]
        ground = [G_GROUND, G_GROUND]
        result = grader.grade(predicted, ground)
        self.assertIsNone(result["strict"])

    def test_metadata_invariances_override(self):
        # Restrict to identity-only AND strict: palette perm is excluded AND
        # tier 3 is disabled. Only tier 1 counts.
        predicted = [G_RECOLOR]
        ground = [G_GROUND]
        result = grader.grade(
            predicted,
            ground,
            task_metadata={"invariances": ("id",), "strict": True},
        )
        self.assertEqual(result["per_example"][0]["tier"], 0)


# ---------------------------------------------------------------------------
# Partial-credit ordering
# ---------------------------------------------------------------------------

class TestPartialCreditOrdering(unittest.TestCase):
    def test_tiers_strictly_ordered(self):
        weights = grader.TIER_WEIGHTS
        self.assertGreater(weights[1], weights[2])
        self.assertGreater(weights[2], weights[3])
        self.assertGreater(weights[2], weights[0])
        self.assertEqual(weights[0], 0.0)


# ---------------------------------------------------------------------------
# Invariance enumeration
# ---------------------------------------------------------------------------

class TestInvarianceEnum(unittest.TestCase):
    def test_all_documented_invariances_apply_to_default_task(self):
        for inv in grader.DEFAULT_INVARIANCES:
            self.assertIn(inv, grader.INVARIANCE_LABELS)

    def test_translation_within_bounds_matches(self):
        # A grid with a single object; translate it within the grid bounds.
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
        matched, kind, _ = grader.equivalence_match(pred, gt)
        self.assertTrue(matched)
        self.assertEqual(kind, "tr")


if __name__ == "__main__":
    unittest.main(verbosity=2)