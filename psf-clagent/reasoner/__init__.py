"""Reasoner — produces candidate programs for a task.

Two implementations:

* :class:`TemplateProposer` uses simple task-feature heuristics (palette
  size, object count, presence of symmetry, etc.) to rank a small set of
  hand-authored program templates. Default for the MVP; no LLM required.

* :class:`LLMProposer` wraps an OpenAI-compatible chat completion
  endpoint (see :mod:`reasoner.llm_client`). When ``OPENAI_API_KEY`` is
  set the agent can route ``--reasoner llm`` through it; otherwise
  :meth:`LLMProposer.is_available` returns ``False`` and the agent
  falls back to :class:`TemplateProposer` automatically.

v2 additions
------------
* Both proposers accept an optional ``hints`` argument (a list of strings).
  :class:`TemplateProposer` extracts them into a keyword bias map;
  :class:`LLMProposer` injects them into the prompt as a "TASK HINTS" block.
* :func:`hint_keywords` is exported for callers that want to inspect the
  mapping themselves.
"""
from __future__ import annotations

from reasoner.features import TaskFeatures, extract_features
from reasoner.template_proposer import (
    TemplateProposer, Program, ScoredProgram, hint_keywords,
)
from reasoner.llm_proposer import LLMProposer
from reasoner.llm_client import LLMClient, LLMUnavailable

__all__ = [
    "TaskFeatures", "extract_features",
    "TemplateProposer", "Program", "ScoredProgram", "hint_keywords",
    "LLMProposer", "LLMClient", "LLMUnavailable",
]