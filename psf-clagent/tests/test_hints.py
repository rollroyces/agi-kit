"""v2 tests for language-conditioned hints in the reasoner."""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from reasoner.template_proposer import (  # noqa: E402
    TemplateProposer, hint_keywords,
)
from reasoner.prompts import build_proposer_prompt  # noqa: E402
from tests.test_llm_proposer import MockLLMClient  # noqa: E402
from reasoner import LLMProposer  # noqa: E402


def _task(train_in, train_out):
    return {
        "generator": "test",
        "generator_signature": "0" * 64,
        "public_seed": "p",
        "private_seed": "q",
        "parameters": {},
        "task": {
            "train": [{"input": train_in, "output": train_out}],
            "test": [{"input": train_in, "output": train_out}],
        },
    }


class TestHintKeywords(unittest.TestCase):

    def test_hint_keywords_dedups_and_lowercases(self):
        out = hint_keywords(["ROTATE 90", "rotate", "mirror"])
        # ROTATE and rotate collapse; mirror stays distinct.
        self.assertIn("rotate", out)
        self.assertIn("mirror", out)
        self.assertEqual(out.count("rotate"), 1)

    def test_hint_keywords_empty_inputs(self):
        self.assertEqual(hint_keywords(None), [])
        self.assertEqual(hint_keywords([]), [])
        self.assertEqual(hint_keywords(["", "   "]), [])


class TestTemplateProposerWithHints(unittest.TestCase):

    def test_rotate_hint_boosts_rotation_score(self):
        # Single 2x2 grid with two diagonal 1s.
        task = _task([[0, 1], [1, 0]], [[1, 0], [0, 1]])
        tp = TemplateProposer()
        no_hints = tp.propose(task, k=20)
        with_hints = tp.propose(task, k=20, hints=["rotate 90 degrees"])
        score_no = next(p.score for p in no_hints
                        if p.label == "rotate_largest_90")
        score_with = next(p.score for p in with_hints
                          if p.label == "rotate_largest_90")
        # Hint must strictly increase the rotation score.
        self.assertGreater(score_with, score_no)

    def test_symmetry_hint_boosts_symmetry_score(self):
        task = _task([[1, 0], [1, 0]], [[1, 0], [0, 1]])
        tp = TemplateProposer()
        no_hints = tp.propose(task, k=20)
        with_hints = tp.propose(task, k=20, hints=["add horizontal symmetry"])
        # Top-3 labels must include a symmetry template.
        labels = [p.label for p in with_hints[:3]]
        self.assertTrue(
            any(l.startswith("symmetry_complete") or l == "flip_h" for l in labels),
            f"expected symmetry template in top-3, got {labels}"
        )
        # And the symmetry template score must exceed its no-hint score.
        sym_label = "symmetry_complete_horizontal"
        s_no = next(p.score for p in no_hints if p.label == sym_label)
        s_with = next(p.score for p in with_hints if p.label == sym_label)
        self.assertGreater(s_with, s_no)

    def test_count_hint_boosts_marker_template(self):
        task = _task([[1, 0]], [[0, 0], [8, 0]])
        tp = TemplateProposer()
        no_hints = tp.propose(task, k=20)
        with_hints = tp.propose(task, k=20, hints=["count the markers"])
        s_no = next(p.score for p in no_hints
                    if p.label == "count_markers_bottom")
        s_with = next(p.score for p in with_hints
                      if p.label == "count_markers_bottom")
        self.assertGreater(s_with, s_no)


class TestLLMProposerWithHints(unittest.TestCase):

    def test_prompt_includes_hints(self):
        client = MockLLMClient(canned='("identity",)')
        proposer = LLMProposer(client=client)
        task = _task([[[0, 1]]], [[[0, 1]]])
        proposer.propose(task, k=3, hints=["rotate 90", "use symmetry"])
        self.assertEqual(len(client.calls), 1)
        prompt = client.calls[0]
        self.assertIn("TASK HINTS", prompt)
        self.assertIn("rotate 90", prompt)
        self.assertIn("use symmetry", prompt)

    def test_prompt_omits_hint_block_when_no_hints(self):
        client = MockLLMClient(canned='("identity",)')
        proposer = LLMProposer(client=client)
        task = _task([[[0, 1]]], [[[0, 1]]])
        proposer.propose(task, k=3, hints=None)
        self.assertNotIn("TASK HINTS", client.calls[0])


if __name__ == "__main__":
    unittest.main()