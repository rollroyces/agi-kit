"""Standard §5 — Generator API: abstract base + determinism test.

This module does **not** import any concrete generator from
``domains/arc/generators/generators/``; it only defines the contract. A
conforming generator is anything that subclasses :class:`Generator` (or
duck-types ``generate(public_seed, private_seed, **params) -> dict``).

Usage::

    from reference.generator import Generator, determinism_test

    class MyGen(Generator):
        name = "my_gen"
        version = "1.0.0"

        def generate(self, public_seed, private_seed, **params):
            return {...}  # build a task from the seeds + params

    gen = MyGen()
    determinism_test(gen, public_seed="seed-a", private_seed="seed-b")
"""
from __future__ import annotations

import hashlib
import inspect
import json
from typing import Any, Callable, Dict, List


class GeneratorError(RuntimeError):
    """Raised when a generator violates its contract."""


class Generator:
    """Abstract base for standard-conformant generators.

    Subclasses **MUST** override :meth:`generate`. They **SHOULD** set the
    class attributes ``name`` (string) and ``version`` (semver).
    """

    name: str = ""
    version: str = "0.0.0"

    def generate(self, public_seed: str, private_seed: str, **params: Any) -> Dict[str, Any]:
        """Return a fresh task dict. **MUST** be byte-deterministic."""
        raise NotImplementedError


def source_signature(callable_: Callable[..., Any]) -> str:
    """Return the lowercase hex sha256 of a callable's source code.

    For methods, pass ``MyClass.method``; for functions, pass the bare
    function. Lambdas, built-ins, and callables without ``__code__`` raise
    :class:`GeneratorError`.
    """
    try:
        src = inspect.getsource(callable_)
    except (OSError, TypeError) as exc:
        raise GeneratorError(
            f"cannot read source for {callable_!r}; "
            "use @functools.wraps and define the function in a real .py file"
        ) from exc
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def generate_with_signature(gen: Generator,
                            public_seed: str,
                            private_seed: str,
                            **params: Any) -> Dict[str, Any]:
    """Wrap a generator's output with the envelope (§4).

    Adds the four envelope fields (``generator``, ``generator_signature``,
    ``public_seed``, ``private_seed``, ``parameters``) around whatever
    the underlying generator returns.
    """
    task = gen.generate(public_seed, private_seed, **params)
    envelope = {
        "generator":           gen.name or gen.__class__.__name__,
        "generator_signature": source_signature(gen.generate),
        "public_seed":         public_seed,
        "private_seed":        private_seed,
        "parameters":          dict(params),
        "task":                task,
    }
    return envelope


def determinism_test(gen: Generator,
                     public_seed: str = "det-public",
                     private_seed: str = "det-private",
                     n_runs: int = 2,
                     **params: Any) -> bool:
    """Run ``gen.generate(...)`` ``n_runs`` times and assert byte equality.

    Returns ``True`` on success; raises :class:`GeneratorError` on any
    divergence. This is the conformance check for SPEC §5.1.
    """
    outputs: List[str] = []
    for i in range(n_runs):
        task = gen.generate(public_seed, private_seed, **params)
        outputs.append(json.dumps(task, sort_keys=True))
    if len(set(outputs)) != 1:
        raise GeneratorError(
            f"generator {gen.name!r} produced different outputs across {n_runs} runs"
        )
    return True


# --- usage examples ----------------------------------------------------------

class _IdentityGenerator(Generator):
    """Trivial generator that produces a 1x1 grid pair."""

    name = "identity_gen"
    version = "1.0.0"

    def generate(self, public_seed, private_seed, **params):
        return {
            "train": [{"input": [[0]], "output": [[0]]}],
            "test":  [{"input": [[0]], "output": [[0]]}],
        }


if __name__ == "__main__":
    gen = _IdentityGenerator()
    determinism_test(gen)
    env = generate_with_signature(gen, "pub", "priv")
    assert env["generator"] == "identity_gen"
    assert len(env["generator_signature"]) == 64
    print("generator.py: self-test passed")
