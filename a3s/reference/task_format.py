"""A3S §4 — Task format: JSON Schema, parser, serializer, validator.

Re-uses the ARC grid-validation primitives from
``01-task-generator/arc_gen/core.py`` (which we treat as the source of truth
for "what counts as a valid grid"). A3S adds the wrapper envelope
(``generator``, ``generator_signature``, ``public_seed``, ``private_seed``,
``parameters``, ``task_metadata``) on top.

Usage::

    from reference.task_format import validate_task, parse_task, dump_task

    with open("examples/task_family/examples/task_01.json") as fh:
        task = parse_task(fh.read())
    validate_task(task)        # raises A3SValidationError on bad shape
    text = dump_task(task)     # canonical, sorted-keys JSON
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict

# Make ``01-task-generator`` importable for its grid validator.
_THIS = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.abspath(os.path.join(_THIS, "..", ".."))

import importlib.util as _ilu  # noqa: E402
_ARC_CORE_PATH = os.path.join(_PROJECT, "01-task-generator", "arc_gen", "core.py")
_spec = _ilu.spec_from_file_location("_a3s_inner_arc_core", _ARC_CORE_PATH)
_arc_core = _ilu.module_from_spec(_spec)
sys.modules["_a3s_inner_arc_core"] = _arc_core
_spec.loader.exec_module(_arc_core)
validate_arc_task = _arc_core.validate_arc_task
ARCError          = _arc_core.ARCError


SCHEMA_VERSION = "1.0.0"

SIG_RE = re.compile(r"^[0-9a-f]{64}$")


class A3SValidationError(ValueError):
    """Raised when an A3S task does not conform to SPEC §4."""


REQUIRED_TOP = (
    "generator",
    "generator_signature",
    "public_seed",
    "private_seed",
    "parameters",
    "task",
)


def parse_task(text: str) -> Dict[str, Any]:
    """Parse a JSON string into an A3S task dict. Pure JSON, no side effects."""
    return json.loads(text)


def dump_task(task: Dict[str, Any], *, indent: int = 2) -> str:
    """Serialise an A3S task dict with sorted keys (canonical form)."""
    return json.dumps(task, sort_keys=True, indent=indent)


def validate_task(task: Any) -> None:
    """Validate an A3S task dict. Raises :class:`A3SValidationError`.

    Conformance: SPEC §4.1 (field rules) + §4.2 (JSON Schema).
    """
    if not isinstance(task, dict):
        raise A3SValidationError("task must be a JSON object")
    for key in REQUIRED_TOP:
        if key not in task:
            raise A3SValidationError(f"task missing required field '{key}'")

    gen = task["generator"]
    if not isinstance(gen, str) or not gen:
        raise A3SValidationError("'generator' must be a non-empty string")

    sig = task["generator_signature"]
    if not isinstance(sig, str) or not SIG_RE.match(sig):
        raise A3SValidationError(
            "'generator_signature' must be a 64-char lowercase hex sha256"
        )

    for key in ("public_seed", "private_seed"):
        if not isinstance(task[key], str):
            raise A3SValidationError(f"'{key}' must be a string")

    if not isinstance(task["parameters"], dict):
        raise A3SValidationError("'parameters' must be a JSON object")

    sub = task["task"]
    if not isinstance(sub, dict) or "train" not in sub or "test" not in sub:
        raise A3SValidationError("'task' must contain both 'train' and 'test'")
    if not isinstance(sub["train"], list) or not sub["train"]:
        raise A3SValidationError("'task.train' must be a non-empty list")
    if not isinstance(sub["test"], list) or len(sub["test"]) != 1:
        raise A3SValidationError("'task.test' must contain exactly one pair")

    # Delegate grid-shape validation to the existing ARC validator.
    try:
        validate_arc_task(sub, require_test_output=True)
    except Exception as exc:  # the ARC validator raises its own errors
        raise A3SValidationError(f"grid validation failed: {exc}") from exc


# --- quick CLI / doctest helper ---------------------------------------------

def _self_test() -> int:
    """Minimal self-test: build a valid task, validate it, serialise it."""
    sample = {
        "generator": "fill_enclosed",
        "generator_signature": "0" * 64,
        "public_seed": "demo",
        "private_seed": "priv",
        "parameters": {"n_shapes": 1},
        "task": {
            "train": [{"input": [[0, 0], [0, 0]], "output": [[0, 0], [0, 0]]}],
            "test":  [{"input": [[0, 0], [0, 0]], "output": [[0, 0], [0, 0]]}],
        },
    }
    validate_task(sample)
    dump_task(sample)
    print("task_format.py: self-test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
