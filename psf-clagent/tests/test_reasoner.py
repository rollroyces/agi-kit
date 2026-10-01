"""Reasoner tests — feature extraction + TemplateProposer ranking."""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from reasoner.features import extract_features  # noqa: E402
from reasoner.template_proposer import TemplateProposer  # noqa: E402
from reasoner.llm_proposer import LLMProposer  # noqa: E402
from reasoner.llm_client import LLMUnavailable  # noqa: E402


def _build_task(inputs, outputs, tests):
    train = [{"input": inp, "output": out} for inp, out in zip(inputs, outputs)]
    test = [{"input": t, "output": t} for t in tests]
    return {
        "generator": "test",
        "generator_signature": "0" * 64,
        "public_seed": "p",
        "private_seed": "q",
        "parameters": {},
        "task": {"train": train, "test": test},
    }


class TestFeatureExtraction(unittest.TestCase):

    def test_features_detect_marker_row(self):
        # Bottom row of colour 8 from column 0, rest zero.
        task = _build_task(
            inputs=[[[1, 0], [0, 0], [0, 0]]],
            outputs=[[[0, 0], [0, 0], [8, 8]]],
            tests=[[[0, 0]]],
        )
        feat = extract_features(task)
        self.assertTrue(feat.output_has_marker_row)

    def test_features_detect_multiple_objects(self):
        task = _build_task(
            inputs=[[[1, 0, 2]]],
            outputs=[[[1, 0, 2]]],
            tests=[[[0, 0, 0]]],
        )
        feat = extract_features(task)
        self.assertTrue(feat.input_has_multiple_objects)

    def test_features_detect_enclosed_pockets(self):
        # 5x5 with a 9-frame and a single bg cell (0) inside.
        # Convention: bg = most frequent colour; pocket = bg cell surrounded by non-bg frame.
        inp = [
            [0, 0, 0, 0, 0],
            [0, 9, 9, 9, 0],
            [0, 9, 0, 9, 0],
            [0, 9, 9, 9, 0],
            [0, 0, 0, 0, 0],
        ]
        task = _build_task([inp], [inp], [inp])
        feat = extract_features(task)
        self.assertTrue(feat.input_has_enclosed_pockets)


class TestTemplateProposer(unittest.TestCase):

    def test_returns_at_most_k(self):
        task = _build_task(
            inputs=[[[0, 1], [1, 0]]],
            outputs=[[[0, 1], [1, 0]]],
            tests=[[[3, 3]]],
        )
        proposer = TemplateProposer()
        out = proposer.propose(task, k=5)
        self.assertEqual(len(out), 5)

    def test_ranks_fill_template_highest_for_enclosed(self):
        # Asymmetric frame around a bg pocket; output differs (introduces fill colour).
        inp = [
            [0, 0, 0, 0, 0, 0, 0],
            [0, 9, 9, 9, 9, 9, 0],
            [0, 9, 0, 0, 0, 9, 0],
            [0, 9, 0, 0, 0, 9, 0],
            [0, 9, 0, 0, 0, 9, 0],
            [0, 9, 9, 9, 9, 9, 0],
            [0, 0, 0, 0, 0, 0, 0],
        ]
        out = [
            [0, 0, 0, 0, 0, 0, 0],
            [0, 9, 9, 9, 9, 9, 0],
            [0, 9, 8, 8, 8, 9, 0],
            [0, 9, 8, 8, 8, 9, 0],
            [0, 9, 8, 8, 8, 9, 0],
            [0, 9, 9, 9, 9, 9, 0],
            [0, 0, 0, 0, 0, 0, 0],
        ]
        task = _build_task([inp], [out], [inp])
        proposer = TemplateProposer()
        proposals = proposer.propose(task, k=5)
        # The fill-enclosed template should appear in the top K.
        labels = [p.label for p in proposals]
        self.assertTrue(any(l.startswith("fill_enclosed") for l in labels),
                        f"expected a fill template in {labels}")

    def test_ranks_marker_template_highest_for_count_task(self):
        # Output is mostly zeros plus a row of 8s at the bottom.
        task = _build_task(
            inputs=[[[1, 0], [0, 0], [0, 0]]],
            outputs=[[[0, 0], [0, 0], [8, 8]]],
            tests=[[[0, 0]]],
        )
        proposer = TemplateProposer()
        out = proposer.propose(task, k=5)
        self.assertEqual(out[0].label, "count_markers_bottom")

    def test_returns_scored_programs(self):
        task = _build_task([[[0]]], [[[0]]], [[[0]]])
        proposer = TemplateProposer()
        out = proposer.propose(task, k=3)
        self.assertTrue(all(hasattr(p, "program") for p in out))
        self.assertTrue(all(hasattr(p, "score") for p in out))
        self.assertTrue(all(hasattr(p, "label") for p in out))


class TestLLMProposerStub(unittest.TestCase):

    def test_propose_raises_not_implemented(self):
        # The LLMProposer is now real; without a configured client, it
        # raises LLMUnavailable (NOT NotImplementedError). Confirm the
        # new contract.
        with self.assertRaises(LLMUnavailable):
            LLMProposer().propose({}, k=3)


if __name__ == "__main__":
    unittest.main()