"""LLM-backed program proposer.

Wires a real OpenAI-compatible chat completion client (see
:mod:`reasoner.llm_client`) into the same ``propose(task, k) -> list[ScoredProgram]``
contract used by :class:`TemplateProposer`. When no API key is configured,
:meth:`LLMProposer.is_available` returns ``False`` so the agent can fall
back to the template proposer without raising.

The proposer parses the assistant's response line-by-line, attempts to
compile each line as a DSL AST, filters out anything that does not
parse, and returns up to ``k`` :class:`ScoredProgram` objects.

The fallback policy:

* Missing key / no client  → :meth:`is_available` returns ``False``
  (the agent chooses template mode and never calls ``propose``).
* Network / parse error mid-call  → :meth:`propose` raises
  :exc:`LLMUnavailable` (the agent catches and falls back).
* Unparseable lines in an otherwise-valid response  → silently skipped.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, List, Optional

from reasoner.llm_client import LLMClient, LLMUnavailable
from reasoner.prompts import build_proposer_prompt, EXAMPLES as _PROMPT_EXAMPLES
from reasoner.template_proposer import Program, ScoredProgram

# Optional DSL import — only used when an AST line is parseable. Pure
# callables returned by the template proposer do not go through the
# interpreter, so a missing DSL at import time would break the agent.
try:
    from dsl.interpreter import compile_program as _compile_program
except Exception:  # pragma: no cover — defensive
    _compile_program = None  # type: ignore[assignment]


_log = logging.getLogger("psf_clagent.llm_proposer")


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

# Tolerate code fences, comments, numbering, and blank lines.
_FENCE_RE = re.compile(r"^\s*```")
_NON_AST_LINE_RE = re.compile(
    r"^\s*(?:\#|//|\d+[.)]|`{3})"
)


def _strip_wrappers(line: str) -> str:
    """Strip a leading ``- `` bullet, code fence, or numbering from ``line``."""
    s = line.strip()
    # Strip leading "1. ", "12) ", "- ", "* "
    s = re.sub(r"^\s*(?:\d+[.)]|[-*])\s+", "", s)
    # Strip trailing code fence or stray markdown
    s = s.rstrip("`").rstrip()
    return s


def _looks_like_ast(line: str) -> bool:
    """Heuristic: does this line look like a DSL AST tuple?

    The AST syntax is a tuple whose first element is a string primitive
    name (or a nested tuple, for ``compose``). We accept any line that
    starts with ``(`` after stripping wrappers.
    """
    if not line:
        return False
    if _FENCE_RE.match(line):
        return False
    if _NON_AST_LINE_RE.match(line):
        return False
    return line.lstrip().startswith("(") and line.rstrip().endswith(")")


def _safe_eval_ast(line: str) -> Optional[Any]:
    """Parse ``line`` as a Python literal; return the tuple (or None).

    We deliberately use ``ast.literal_eval`` so we never ``exec`` the
    model's output. The DSL interpreter is the only thing that ever
    runs the produced AST.
    """
    import ast
    try:
        node = ast.parse(line, mode="eval")
    except SyntaxError:
        return None
    value = getattr(node, "body", None)
    if not isinstance(value, ast.Tuple):
        return None
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return None


def _try_compile(parsed: Any) -> Optional[Callable[[Any], Any]]:
    """Compile a parsed AST into a callable, or return ``None``."""
    if _compile_program is None:
        return None
    try:
        return _compile_program(parsed)
    except Exception:
        return None


def _parse_response(
    response: str,
    *,
    max_programs: int,
) -> List[ScoredProgram]:
    """Parse a single ``complete()`` response into up to ``max_programs``.

    Returns the parsed programs in the order the model emitted them.
    """
    out: List[ScoredProgram] = []
    if not response:
        return out

    # Split on newlines; tolerate CR and CRLF.
    for raw_line in response.splitlines():
        line = _strip_wrappers(raw_line)
        if not _looks_like_ast(line):
            continue
        parsed = _safe_eval_ast(line)
        if parsed is None:
            continue
        # Reject obviously non-AST things (a list literal, etc.).
        if not isinstance(parsed, tuple) or not parsed:
            continue
        prog = _try_compile(parsed)
        if prog is None:
            continue
        # Use a stable label derived from the AST head.
        head = parsed[0] if isinstance(parsed[0], str) else "compose"
        label = f"llm::{head}::{len(out)}"
        out.append(ScoredProgram(program=prog, score=1.0, label=label))
        if len(out) >= max_programs:
            break

    return out


# ---------------------------------------------------------------------------
# Proposer
# ---------------------------------------------------------------------------

class LLMProposer:
    """LLM-backed reasoner using an OpenAI-compatible chat completion API.

    Construction
    ------------
    ::

        proposer = LLMProposer()                       # picks up env
        proposer = LLMProposer(LLMClient.from_env())   # explicit
        proposer = LLMProposer(LLMClient(api_key=None))  # for tests

    Behaviour
    ---------
    * :meth:`is_available` returns ``False`` when no client or no key.
      The agent uses this to pick the fallback path before any HTTP call.
    * :meth:`propose` calls ``client.complete(prompt)`` and parses the
      response. On :exc:`LLMUnavailable` from the HTTP layer it logs and
      re-raises so the agent can catch and fall back.
    """

    name = "llm"

    def __init__(self, client: Optional[LLMClient] = None) -> None:
        self.client: Optional[LLMClient] = client
        self.last_prompt_chars: int = 0
        self.last_response_chars: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """True iff a client is configured with an API key."""
        return self.client is not None and self.client.is_available()

    def propose(self, task: dict, k: int = 20) -> List[ScoredProgram]:
        """Return up to ``k`` candidate programs from the LLM.

        Raises
        ------
        LLMUnavailable
            When the HTTP client is unavailable or the model response
            cannot be obtained. The agent catches this and falls back.
        """
        if not self.is_available() or self.client is None:
            raise LLMUnavailable(
                "LLMProposer.propose called with no available client; "
                "agent should check is_available() first."
            )

        from reasoner.prompts import list_dsl_primitives
        prompt = build_proposer_prompt(
            task,
            k=k,
            dsl_primitives=list_dsl_primitives(),
            examples=_PROMPT_EXAMPLES,
        )
        self.last_prompt_chars = len(prompt)

        text = self.client.complete(prompt)
        self.last_response_chars = len(text or "")
        programs = _parse_response(text or "", max_programs=k)
        if not programs:
            _log.warning(
                "LLMProposer: model returned no parseable programs "
                "(prompt=%d chars, response=%d chars)",
                self.last_prompt_chars, self.last_response_chars,
            )
        return programs