"""DSL primitive + combinator test suite.

20+ tests covering each primitive at least once, plus combinator behaviour and
the lightweight type checker.
"""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REPO = os.path.abspath(os.path.join(_ROOT, ".."))
sys.path.insert(0, _REPO)

from agent.dsl import (  # noqa: E402
    make_grid, from_list,
    shape, color_at, distinct_colors, count_color, background_color,
    rotate, flip_h, flip_v, translate,
    connected_components, largest_object, bounding_box,
    flood_fill, enclosed_regions,
    recolor, invert_palette,
    compose, iterate, zip_with, identity,
    typecheck_program, TypeError_,
)
from agent.dsl.interpreter import execute  # noqa: E402
from agent.dsl.registry import all_names, registry  # noqa: E402


class TestConstruction(unittest.TestCase):

    def test_make_grid_size_and_fill(self):
        g = make_grid(3, 4, 7)
        self.assertEqual(shape(g), (3, 4))
        self.assertTrue(all(v == 7 for row in g for v in row))

    def test_from_list_copies_rows(self):
        rows = [[1, 2], [3, 4]]
        g = from_list(rows)
        self.assertEqual(g, rows)
        # Mutating source must not affect grid.
        rows[0][0] = 99
        self.assertEqual(g[0][0], 1)


class TestInspection(unittest.TestCase):

    def test_shape(self):
        self.assertEqual(shape([[0, 1], [2, 3], [4, 5]]), (3, 2))
        self.assertEqual(shape([[]]), (1, 0))

    def test_color_at_in_bounds(self):
        self.assertEqual(color_at([[1, 2], [3, 4]], 1, 0), 3)

    def test_color_at_out_of_bounds(self):
        self.assertEqual(color_at([[1, 2]], 5, 5), 0)

    def test_distinct_colors_sorted(self):
        self.assertEqual(distinct_colors([[1, 2, 2], [3, 1, 0]]), [0, 1, 2, 3])

    def test_count_color(self):
        self.assertEqual(count_color([[1, 1], [1, 2]], 1), 3)
        self.assertEqual(count_color([[1, 1], [1, 2]], 9), 0)

    def test_background_color(self):
        self.assertEqual(background_color([[0, 0], [0, 1]]), 0)


class TestGeometry(unittest.TestCase):

    def test_rotate_0_is_identity(self):
        g = [[1, 2], [3, 4]]
        self.assertEqual(rotate(g, 0), g)

    def test_rotate_1_cw(self):
        g = [[1, 2], [3, 4]]
        self.assertEqual(rotate(g, 1), [[3, 1], [4, 2]])

    def test_rotate_2_180(self):
        g = [[1, 2], [3, 4]]
        self.assertEqual(rotate(g, 2), [[4, 3], [2, 1]])

    def test_rotate_3_270cw(self):
        g = [[1, 2], [3, 4]]
        self.assertEqual(rotate(g, 3), [[2, 4], [1, 3]])

    def test_rotate_k_4_is_identity(self):
        g = [[1, 2, 3], [4, 5, 6]]
        self.assertEqual(rotate(g, 4), [[1, 2, 3], [4, 5, 6]])

    def test_flip_h(self):
        self.assertEqual(flip_h([[1, 2, 3]]), [[3, 2, 1]])

    def test_flip_v(self):
        self.assertEqual(flip_v([[1], [2], [3]]), [[3], [2], [1]])

    def test_translate_positive(self):
        g = [[1, 1], [1, 1]]
        out = translate(g, 1, 1, fill=9)
        self.assertEqual(out, [[9, 9], [9, 1]])

    def test_translate_no_op(self):
        g = [[1, 2], [3, 4]]
        self.assertEqual(translate(g, 0, 0, fill=0), g)


class TestObjectOps(unittest.TestCase):

    def test_connected_components_two_blobs(self):
        g = [[1, 0], [0, 2]]
        comps = connected_components(g, 0)
        self.assertEqual({len(c) for c in comps}, {1, 1})
        self.assertEqual(len(comps), 2)

    def test_largest_object_picks_biggest(self):
        g = [[1, 1, 0, 0], [1, 0, 0, 0], [2, 2, 2, 2]]
        big = largest_object(g, 0)
        self.assertEqual(len(big), 4)
        self.assertEqual(set(big), {(2, 0), (2, 1), (2, 2), (2, 3)})

    def test_bounding_box(self):
        self.assertEqual(bounding_box([(0, 1), (2, 0), (1, 3)]), (0, 0, 2, 3))

    def test_flood_fill_replaces_region(self):
        g = [[1, 1, 0], [1, 1, 0]]
        out = flood_fill(g, 0, 0, 5)
        self.assertEqual(out, [[5, 5, 0], [5, 5, 0]])

    def test_enclosed_regions_finds_inside(self):
        # A 5x5 grid with a 3x3 frame of 9 around a single 0 inside.
        g = [
            [9, 9, 9, 9, 9],
            [9, 0, 0, 0, 9],
            [9, 0, 0, 0, 9],
            [9, 0, 0, 0, 9],
            [9, 9, 9, 9, 9],
        ]
        regs = enclosed_regions(g, 0)
        # Only the single interior pocket (9 cells) is enclosed.
        self.assertEqual(len(regs), 1)
        self.assertEqual(len(regs[0]), 9)


class TestPalette(unittest.TestCase):

    def test_recolor_mapping(self):
        g = [[1, 2], [3, 1]]
        self.assertEqual(recolor(g, {1: 9}), [[9, 2], [3, 9]])

    def test_invert_palette_endpoints(self):
        self.assertEqual(invert_palette([[0, 9, 5]]), [[9, 1, 5]])


class TestCombinators(unittest.TestCase):

    def test_compose_left_to_right(self):
        # First rotate 1, then flip_h.
        prog = compose(rotate, lambda g: _ops(g))
        g = [[1, 2], [3, 4]]
        out = prog(g)
        # rotate(1) of [[1,2],[3,4]] = [[3,1],[4,2]], then flip_h = [[1,3],[2,4]]
        self.assertEqual(out, [[1, 3], [2, 4]])

    def test_iterate_applies_n_times(self):
        out = iterate(flip_h, 2, [[1, 2, 3]])
        self.assertEqual(out, [[1, 2, 3]])

    def test_zip_with_cellwise_max(self):
        def pick(a, b):
            return max(a, b)
        a = [[1, 2], [3, 4]]
        b = [[4, 1], [2, 5]]
        out = zip_with(pick, a, b)
        self.assertEqual(out, [[4, 2], [3, 5]])

    def test_zip_with_shape_mismatch(self):
        with self.assertRaises(ValueError):
            zip_with(lambda a, b: 0, [[1, 2]], [[1]])


class TestInterpreter(unittest.TestCase):

    def test_execute_leaf_primitive(self):
        out = execute(("rotate", ("identity",), 2), [[1, 2], [3, 4]])
        self.assertEqual(out, [[4, 3], [2, 1]])

    def test_execute_nested_program(self):
        # compose(rotate, flip_h) over an identity-style input.
        ast = ("compose",
               ("rotate", ("identity",), 1),
               ("flip_h", ("identity",)))
        out = execute(ast, [[1, 2], [3, 4]])
        self.assertEqual(out, [[1, 3], [2, 4]])


class TestTypeChecker(unittest.TestCase):

    def test_valid_program(self):
        typecheck_program(("rotate", ("identity",), 1))

    def test_unknown_primitive(self):
        with self.assertRaises(TypeError_):
            typecheck_program(("does_not_exist",))

    def test_arity_mismatch(self):
        with self.assertRaises(TypeError_):
            typecheck_program(("rotate",))  # rotate needs grid + k

    def test_variadic_compose_min_one(self):
        with self.assertRaises(TypeError_):
            typecheck_program(("compose",))

    def test_registry_complete(self):
        names = all_names()
        self.assertGreaterEqual(len(names), 20)
        for n in names:
            self.assertIn(n, registry())


# Helper used by TestCombinators.test_compose_left_to_right.
def _ops(g):
    # alias for flip_h, defined here to keep the test readable.
    from agent.dsl.primitives import flip_h
    return flip_h(g)


if __name__ == "__main__":
    unittest.main()