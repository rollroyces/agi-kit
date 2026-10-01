"""OpenAI-compatible HTTP client (zero external dependencies).

Plain ``urllib.request`` — no ``openai`` SDK, no ``httpx``. Reads
``OPENAI_API_KEY``, ``OPENAI_BASE_URL`` and ``OPENAI_MODEL`` from the
environment, with safe defaults so the rest of the agent can still
import and use the client when no key is configured (in which case
:meth:`LLMClient.complete` raises :exc:`LLMUnavailable` so the caller
can fall back gracefully).

The same client works against any OpenAI-compatible chat completion
endpoint:

* OpenAI: ``https://api.openai.com/v1`` (default)
* Ollama: ``http://localhost:11434/v1`` (serves OpenAI shape)
* LM Studio: ``http://localhost:1234/v1``
* vLLM: ``http://localhost:8000/v1``
* Any other OpenAI-compatible proxy
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class LLMUnavailable(Exception):
    """Raised when the LLM cannot be reached (missing key, network error, etc.).

    The agent catches this exception and falls back to the template proposer.
    """


@dataclass
class LLMClient:
    """Thin OpenAI-compatible chat completion wrapper.

    Parameters
    ----------
    api_key:
        ``OPENAI_API_KEY``. If ``None`` or empty, :meth:`complete` will
        raise :exc:`LLMUnavailable` immediately — no network call is made.
    base_url:
        ``OPENAI_BASE_URL``. Default ``https://api.openai.com/v1``.
    model:
        ``OPENAI_MODEL``. Default ``gpt-4o-mini``.
    timeout:
        Per-request timeout in seconds. Default 60.
    """

    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout: float = 60.0

    # ---- factory ---------------------------------------------------------

    @classmethod
    def from_env(cls, *, default_timeout: float = 60.0) -> "LLMClient":
        """Build a client from environment variables.

        ``OPENAI_API_KEY``, ``OPENAI_BASE_URL``, ``OPENAI_MODEL`` are read
        with the defaults described in the module docstring.
        """
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            timeout=float(os.environ.get("OPENAI_TIMEOUT_S", str(default_timeout))),
        )

    # ---- availability ----------------------------------------------------

    def is_available(self) -> bool:
        """True iff an API key is present. The cheapest guard."""
        return bool(self.api_key) and bool(self.base_url) and bool(self.model)

    # ---- core call -------------------------------------------------------

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
    ) -> str:
        """Run a single chat completion against the configured endpoint.

        Parameters
        ----------
        prompt:
            The user message. The system prompt is kept tiny and is inlined
            by the caller via the templates in :mod:`reasoner.prompts`.
        temperature, max_tokens, timeout:
            Standard knobs. ``timeout`` defaults to ``self.timeout``.

        Returns
        -------
        str
            The assistant text. Strips the OpenAI JSON envelope; raises
            :exc:`LLMUnavailable` on missing key, HTTP error, timeout, or
            malformed response.

        Notes
        -----
        * No streaming. One round-trip per call.
        * The system message is just enough to anchor the format; the
          bulk of the prompt lives in the user message so the model's
          context budget is spent on examples, not preamble.
        """
        if not self.is_available():
            raise LLMUnavailable(
                "OPENAI_API_KEY is not set; LLM client is unavailable. "
                "The agent will fall back to TemplateProposer."
            )

        url = f"{self.base_url}/chat/completions"
        system_msg = (
            "You are a careful ARC program synthesiser. "
            "Output ONLY DSL AST tuples, one per line, no commentary."
        )
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        effective_timeout = float(timeout) if timeout is not None else self.timeout
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            raise LLMUnavailable(
                f"LLM HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMUnavailable(f"LLM network error: {exc.reason}") from exc
        except (TimeoutError, OSError) as exc:
            raise LLMUnavailable(f"LLM request timed out / failed: {exc}") from exc

        if status >= 400:
            raise LLMUnavailable(f"LLM HTTP {status}: {raw[:200]}")

        try:
            parsed = json.loads(raw)
            text = parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise LLMUnavailable(
                f"LLM returned an unexpected response shape: {exc}; "
                f"raw[:200]={raw[:200]!r}"
            ) from exc

        if not isinstance(text, str):
            raise LLMUnavailable(
                f"LLM assistant content is not a string: {type(text).__name__}"
            )
        return text