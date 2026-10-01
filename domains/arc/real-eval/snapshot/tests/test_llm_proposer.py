"""Unit tests for :mod:`reasoner.llm_proposer` and :mod:`reasoner.llm_client`.

These tests use a :class:`MockLLMClient` so no live network calls happen.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from reasoner.llm_client import LLMClient, LLMUnavailable  # noqa: E402
from reasoner.llm_proposer import (  # noqa: E402
    LLMProposer,
    _looks_like_ast,
    _parse_response,
    _safe_eval_ast,
    _strip_wrappers,
)
from reasoner.template_proposer import ScoredProgram  # noqa: E402


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------

class MockLLMClient(LLMClient):
    """An :class:`LLMClient` whose ``complete()`` returns a canned response.

    Parameters
    ----------
    canned:
        Either a string (returned verbatim from ``complete``) or a callable
        ``(prompt) -> str`` so tests can pattern-match on the prompt.
    raise_exc:
        Optional exception class to raise instead of returning ``canned``.
    """

    def __init__(self, canned="", *, raise_exc=None, **kwargs):
        # Force the availability flag to True so tests can exercise the
        # propose() path without a real API key.
        super().__init__(
            api_key=kwargs.get("api_key", "sk-mock"),
            base_url=kwargs.get("base_url", "http://mock.local/v1"),
            model=kwargs.get("model", "mock-model"),
            timeout=kwargs.get("timeout", 1.0),
        )
        self.canned = canned
        self.raise_exc = raise_exc
        self.calls: list = []

    def complete(self, prompt: str, **kwargs):
        self.calls.append(prompt)
        if self.raise_exc is not None:
            raise self.raise_exc
        if callable(self.canned):
            return self.canned(prompt)
        return self.canned


def _build_task(inputs, outputs, tests=None):
    train = [{"input": inp, "output": out} for inp, out in zip(inputs, outputs)]
    tests = tests or [[[0]]]
    test = [{"input": t, "output": t} for t in tests]
    return {
        "generator": "test",
        "generator_signature": "0" * 64,
        "public_seed": "p",
        "private_seed": "q",
        "parameters": {},
        "task": {"train": train, "test": test},
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestStripHelpers(unittest.TestCase):

    def test_strip_wrappers_drops_numbering(self):
        self.assertEqual(_strip_wrappers("1. (\"rotate\", (\"identity\",), 1)"),
                         "(\"rotate\", (\"identity\",), 1)")

    def test_strip_wrappers_drops_bullet(self):
        self.assertEqual(_strip_wrappers("- (\"flip_h\", (\"identity\",))"),
                         "(\"flip_h\", (\"identity\",))")

    def test_strip_wrappers_drops_trailing_fence(self):
        self.assertEqual(_strip_wrappers("```"), "")
        self.assertEqual(_strip_wrappers("  (\"rotate\", x, 1)  ```"),
                         "(\"rotate\", x, 1)")


class TestLooksLikeAST(unittest.TestCase):

    def test_accepts_simple_tuple(self):
        self.assertTrue(_looks_like_ast("(\"rotate\", (\"identity\",), 1)"))

    def test_accepts_compose_tuple(self):
        self.assertTrue(_looks_like_ast('("compose", ("flip_h", ("identity",)), ("rotate", ("identity",), 1))'))

    def test_rejects_python_comment(self):
        self.assertFalse(_looks_like_ast("# this is a comment"))

    def test_rejects_numbered_line(self):
        self.assertFalse(_looks_like_ast("1. (\"rotate\", (\"identity\",), 1)"))  # gets stripped first

    def test_rejects_plain_text(self):
        self.assertFalse(_looks_like_ast("Here is the program:"))

    def test_rejects_empty(self):
        self.assertFalse(_looks_like_ast(""))

    def test_rejects_fence(self):
        self.assertFalse(_looks_like_ast("```python"))


class TestSafeEvalAST(unittest.TestCase):

    def test_parses_tuple(self):
        v = _safe_eval_ast('("rotate", ("identity",), 1)')
        self.assertEqual(v, ("rotate", ("identity",), 1))

    def test_returns_none_for_non_tuple(self):
        self.assertIsNone(_safe_eval_ast("42"))
        self.assertIsNone(_safe_eval_ast('"string"'))

    def test_returns_none_for_garbage(self):
        self.assertIsNone(_safe_eval_ast('("rotate", '))

    def test_rejects_call_attempt(self):
        # literal_eval should refuse function calls.
        self.assertIsNone(_safe_eval_ast('__import__("os").system("rm")'))


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

class TestParseResponse(unittest.TestCase):

    def test_parses_single_program(self):
        resp = '("rotate", ("identity",), 1)\n'
        out = _parse_response(resp, max_programs=5)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], ScoredProgram)
        self.assertTrue(callable(out[0].program))

    def test_parses_multiple_programs(self):
        resp = (
            '("rotate", ("identity",), 1)\n'
            '("flip_h", ("identity",))\n'
            '("flip_v", ("identity",))\n'
        )
        out = _parse_response(resp, max_programs=10)
        self.assertEqual(len(out), 3)
        labels = [p.label for p in out]
        self.assertTrue(all(l.startswith("llm::") for l in labels))

    def test_respects_k(self):
        resp = "\n".join(
            f'("rotate", ("identity",), {(i % 4) + 1})' for i in range(10)
        )
        out = _parse_response(resp, max_programs=4)
        self.assertEqual(len(out), 4)

    def test_filters_unparseable_lines(self):
        resp = (
            "Some intro text.\n"
            '```\n'
            '("rotate", ("identity",), 1)\n'
            "More commentary.\n"
            '("flip_h", ("identity",))\n'
            "And another sentence.\n"
            "# nope\n"
            '("flip_v", ("identity",))\n'
            "```\n"
        )
        out = _parse_response(resp, max_programs=10)
        self.assertEqual(len(out), 3)

    def test_filters_unknown_primitives(self):
        resp = '("no_such_primitive", ("identity",))\n("identity",)\n'
        out = _parse_response(resp, max_programs=10)
        # Only the valid identity primitive should survive.
        self.assertEqual(len(out), 1)

    def test_empty_response(self):
        self.assertEqual(_parse_response("", max_programs=5), [])
        self.assertEqual(_parse_response("   \n\n  \n", max_programs=5), [])


# ---------------------------------------------------------------------------
# LLMProposer behaviour
# ---------------------------------------------------------------------------

class TestLLMProposerAvailability(unittest.TestCase):

    def test_default_is_unavailable_without_env(self):
        # Clear any inherited env so the test is deterministic.
        old = {k: os.environ.pop(k, None) for k in
               ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")}
        try:
            proposer = LLMProposer()
            self.assertFalse(proposer.is_available())
            with self.assertRaises(LLMUnavailable):
                proposer.propose(_build_task([[[0]]], [[[0]]]), k=3)
        finally:
            for k, v in old.items():
                if v is not None:
                    os.environ[k] = v

    def test_explicit_unavailable_client(self):
        client = LLMClient(api_key=None)
        proposer = LLMProposer(client=client)
        self.assertFalse(proposer.is_available())

    def test_mock_client_reports_available(self):
        proposer = LLMProposer(client=MockLLMClient(canned=""))
        self.assertTrue(proposer.is_available())


class TestLLMProposerHappyPath(unittest.TestCase):

    def test_propose_returns_callable_programs(self):
        client = MockLLMClient(canned='("identity",)\n("rotate", ("identity",), 1)\n')
        proposer = LLMProposer(client=client)
        task = _build_task([[[0]]], [[[0]]])
        programs = proposer.propose(task, k=5)
        self.assertGreaterEqual(len(programs), 1)
        self.assertTrue(all(callable(p.program) for p in programs))
        # The mock client's complete() was invoked exactly once.
        self.assertEqual(len(client.calls), 1)

    def test_propose_respects_k(self):
        client = MockLLMClient(canned="\n".join(
            f'("rotate", ("identity",), {(i % 4) + 1})' for i in range(20)
        ))
        proposer = LLMProposer(client=client)
        task = _build_task([[[0]]], [[[0]]])
        programs = proposer.propose(task, k=3)
        self.assertEqual(len(programs), 3)

    def test_propose_raises_on_llm_unavailable(self):
        client = MockLLMClient(canned="", raise_exc=LLMUnavailable("boom"))
        proposer = LLMProposer(client=client)
        with self.assertRaises(LLMUnavailable):
            proposer.propose(_build_task([[[0]]], [[[0]]]), k=3)

    def test_prompt_contains_task_and_examples(self):
        client = MockLLMClient(canned='("identity",)')
        proposer = LLMProposer(client=client)
        task = _build_task([[[1, 0], [0, 1]]], [[[1, 0], [0, 1]]])
        proposer.propose(task, k=2)
        prompt = client.calls[0]
        # The prompt should mention the DSL primitives and the family examples.
        self.assertIn("rotate", prompt)
        self.assertIn("count_colors", prompt)
        self.assertIn("fill_enclosed", prompt)
        # It should also contain the literal task data.
        self.assertIn("pair 1 input", prompt)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

class TestPrompts(unittest.TestCase):

    def test_build_proposer_prompt_under_budget(self):
        from reasoner.prompts import build_proposer_prompt, list_dsl_primitives
        task = _build_task([[[0, 1], [1, 0]]], [[[0, 1], [1, 0]]])
        prompt = build_proposer_prompt(
            task, k=5,
            dsl_primitives=list_dsl_primitives(),
            examples=[],
        )
        # Token budget: ~4 chars/token for English + structured lists.
        # Under 2000 tokens → under ~8000 chars. Be generous: 12000.
        self.assertLess(len(prompt), 12000)
        self.assertIn("DSL", prompt)
        self.assertIn("K", prompt.upper())  # the request mentions K

    def test_build_proposer_prompt_includes_test_input(self):
        from reasoner.prompts import build_proposer_prompt, list_dsl_primitives
        task = _build_task([[[0]]], [[[0]]], tests=[[[5, 6]]])
        prompt = build_proposer_prompt(
            task, k=3,
            dsl_primitives=list_dsl_primitives(),
            examples=[],
        )
        self.assertIn("5 6", prompt)


# ---------------------------------------------------------------------------
# LLMClient.is_available
# ---------------------------------------------------------------------------

class TestLLMClientAvailability(unittest.TestCase):

    def test_unavailable_without_key(self):
        client = LLMClient(api_key=None)
        self.assertFalse(client.is_available())

    def test_unavailable_with_empty_string_key(self):
        client = LLMClient(api_key="")
        self.assertFalse(client.is_available())

    def test_available_with_key(self):
        client = LLMClient(api_key="sk-test")
        self.assertTrue(client.is_available())

    def test_complete_without_key_raises(self):
        client = LLMClient(api_key=None)
        with self.assertRaises(LLMUnavailable):
            client.complete("hello")


if __name__ == "__main__":
    unittest.main()