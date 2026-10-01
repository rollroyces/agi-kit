"""A3S-conformant wrapper for the existing ``fill_enclosed`` generator.

This module does NOT re-implement the rule; it imports the original from
``01-task-generator/generators/fill_enclosed.py`` and exposes it under
the A3S §5 contract:

    generate(public_seed: str, private_seed: str, **params) -> dict

The output is the A3S task envelope (§4) with a real ``generator_signature``
computed from the source.

Usage (from a third party)::

    from generator import FillEnclosedGenerator
    task = FillEnclosedGenerator().generate("pub", "priv", n_shapes=2)
    # task is a fully conformant A3S task dict
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from typing import Any, Dict

_THIS = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS, "..", "..", ".."))
_GENERATOR_PY = os.path.join(
    _PROJECT_ROOT, "01-task-generator", "generators", "fill_enclosed.py",
)


def _load_fill_enclosed():
    """Late-import the original generator from the project tree.

    Adds ``01-task-generator`` to ``sys.path`` so the relative import
    ``from arc_gen.core import ...`` inside ``fill_enclosed.py`` resolves.
    """
    pkg_root = os.path.dirname(_GENERATOR_PY)             # .../generators
    project_root = os.path.dirname(pkg_root)             # .../01-task-generator
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    spec = importlib.util.spec_from_file_location(
        "generators.fill_enclosed", _GENERATOR_PY,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load fill_enclosed from {_GENERATOR_PY}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _source_signature(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class FillEnclosedGenerator:
    """A3S wrapper around the fill_enclosed generator.

    Conforms to SPEC §5: ``name``, ``version``, ``generate(public_seed,
    private_seed, **params)`` returning a fully wrapped A3S task.
    """

    name = "fill_enclosed"
    version = "1.0.0"

    def __init__(self) -> None:
        self._mod = _load_fill_enclosed()
        self.signature = _source_signature(_GENERATOR_PY)

    def generate(self, public_seed: str, private_seed: str, **params: Any) -> Dict[str, Any]:
        body = self._mod.generate(public_seed, private_seed, **params)
        envelope = {
            "generator":           self.name,
            "generator_signature": self.signature,
            "public_seed":         public_seed,
            "private_seed":        private_seed,
            "parameters":          dict(params),
            "task":                body,
            "task_metadata": {
                "invariances":   ["id", "pal", "rot90", "rot180", "rot270", "fh", "fv", "tr"],
                "primitives":    ["color", "shape", "object"],
                "license":       "CC0-1.0",
                "source_url":    "",
                "audit_version": "",
            },
        }
        return envelope


# --- usage ------------------------------------------------------------------

if __name__ == "__main__":
    gen = FillEnclosedGenerator()
    print(f"name={gen.name} version={gen.version} sig={gen.signature[:12]}...")
    task = gen.generate("demo-public", "demo-private", n_shapes=2)
    print(f"train pairs: {len(task['task']['train'])}")
    print(f"signature_in_envelope_matches: {task['generator_signature'] == gen.signature}")
