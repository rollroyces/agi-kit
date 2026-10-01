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
"""
from __future__ import annotations

from reasoner.features import TaskFeatures, extract_features
from reasoner.template_proposer import TemplateProposer, Program, ScoredProgram
from reasoner.llm_proposer import LLMProposer
from reasoner.llm_client import LLMClient, LLMUnavailable

__all__ = [
    "TaskFeatures", "extract_features",
    "TemplateProposer", "Program", "ScoredProgram",
    "LLMProposer", "LLMClient", "LLMUnavailable",
]