"""v2 tests for multi-channel grid primitives + feature detection."""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from dsl import (  # noqa: E402
    make_multichannel, extract_channel, combine_channels,
    project_luminance, identity, is_multichannel,
)
from dsl.multichannel import channel_shape  # noqa: E402
from reasoner.features import extract_features  # noqa: E402


class TestMultichannelPrimitives(unittest.TestCase):

    def test_is_multichannel_true_for_list_of_grids(self):
        self.assertTrue(is_multichannel([[[1, 2]], [[3, 4]]]))

    def test_is_multichannel_false_for_single_grid(self):
        self.assertFalse(is_multichannel([[1, 2], [3, 4]]))

    def test_make_multichannel_returns_list(self):
        out = make_multichannel([[[1, 2]], [[3, 4]]])
        self.assertEqual(out, [[[1, 2]], [[3, 4]]])

    def test_make_multichannel_rejects_shape_mismatch(self):
        with self.assertRaises(ValueError):
            make_multichannel([[[1, 2]], [[3, 4, 5]]])

    def test_extract_channel_roundtrip(self):
        ch0 = [[1, 2], [3, 4]]
        ch1 = [[9, 8], [7, 6]]
        multi = make_multichannel([ch0, ch1])
        self.assertEqual(extract_channel(multi, 0), ch0)
        self.assertEqual(extract_channel(multi, 1), ch1)

    def test_extract_channel_from_single_grid(self):
        g = [[1, 2], [3, 4]]
        # A single grid is treated as channel 0; index out of range raises.
        self.assertEqual(extract_channel(g, 0), [[1, 2], [3, 4]])
        with self.assertRaises(IndexError):
            extract_channel(g, 1)

    def test_combine_channels_aliases_make(self):
        a = [[1, 0]]
        b = [[0, 1]]
        self.assertEqual(combine_channels([a, b]), make_multichannel([a, b]))

    def test_project_luminance_rounds_mean(self):
        # Mean of 0 and 9 = 4.5 → rounds to 4 (banker's rounding is .5 → even).
        multi = [[[0, 0]], [[9, 9]]]
        self.assertEqual(project_luminance(multi), [[4, 4]])

    def test_project_luminance_passthrough_single(self):
        g = [[1, 2], [3, 4]]
        out = project_luminance(g)
        self.assertEqual(out, g)
        # Must be a copy, not the same object.
        out[0][0] = 99
        self.assertEqual(g[0][0], 1)

    def test_channel_shape_validates_alignment(self):
        self.assertEqual(channel_shape([[[1, 2]]]), (1, 2))
        with self.assertRaises(ValueError):
            channel_shape([[[1, 2]], [[3]]])


class TestMultichannelFeatureDetection(unittest.TestCase):

    def _task(self, train_in, train_out, hints=None):
        return {
            "generator": "test",
            "generator_signature": "0" * 64,
            "public_seed": "p",
            "private_seed": "q",
            "parameters": {},
            "hints": hints or [],
            "task": {
                "train": [{"input": train_in, "output": train_out}],
                "test": [{"input": train_in, "output": train_out}],
            },
        }

    def test_features_flag_multichannel_input(self):
        multi_in = [[[1, 0], [0, 1]], [[2, 2], [2, 2]]]
        task = self._task(multi_in, multi_in)
        feat = extract_features(task)
        self.assertTrue(feat.is_multichannel)
        self.assertEqual(feat.n_channels, 2)

    def test_features_do_not_flag_single_channel(self):
        task = self._task([[1, 2]], [[1, 2]])
        feat = extract_features(task)
        self.assertFalse(feat.is_multichannel)
        self.assertEqual(feat.n_channels, 1)

    def test_features_capture_hints(self):
        task = self._task([[1, 2]], [[1, 2]],
                          hints=["rotate 90", "symmetry"])
        feat = extract_features(task)
        self.assertEqual(feat.hints, ["rotate 90", "symmetry"])

    def test_features_default_hints_empty(self):
        task = self._task([[1, 2]], [[1, 2]])
        feat = extract_features(task)
        self.assertEqual(feat.hints, [])


if __name__ == "__main__":
    unittest.main()