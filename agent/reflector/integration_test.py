"""Reflector integration test — run the agent on a generated task and
print the resulting :class:`ReflectionReport`.

This is the *integration* counterpart of the unit tests in
``tests/test_reflector.py``. The unit tests exercise the Reflector in
isolation with synthetic candidates; this script exercises it inside
the full ``CLAgent.solve()`` loop on a real procedurally-generated
ARC task.

Usage::

    python -m agent.reflector.integration_test

Or from the repo root::

    cd agent
    python -m reflector.integration_test

The script prints a structured summary and exits 0 if the resulting
``ReflectionReport`` has a confidence in ``[0, 1]``, a contradiction
in ``[0, 1]``, and an action in the allowed set.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make `agent` importable when the script is run directly.
_THIS = Path(__file__).resolve().parent
_AGENT = _THIS.parent
_REPO = _AGENT.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "standard"))

from agent import CLAgent, SolveConfig, MemoryFacade  # noqa: E402
from agent.reflector import ReflectionReport  # noqa: E402
from reference.airt import ToolBridge  # noqa: E402


def _load_example_task(family: str = "rotate_largest", idx: int = 1) -> dict:
    """Load a single example task from ``domains/arc/generators/examples``."""
    path = (
        _REPO / "domains" / "arc" / "generators" / "examples"
        / family / f"task_{idx:02d}.json"
    )
    if not path.exists():
        # Fallback to the snapshot if the example tree was not checked out.
        alt = _REPO / "domains" / "arc" / "real-eval" / "snapshot"
        if alt.exists():
            # Last resort: use any rotate_largest task from the snapshot.
            for fam_dir in alt.rglob(f"task_{idx:02d}.json"):
                return json.loads(fam_dir.read_text())
        raise SystemExit(
            f"FATAL: no example task at {path}; "
            "run `python domains/arc/generators/generate_examples.py` first."
        )
    return json.loads(path.read_text())


def _main() -> int:
    task = _load_example_task("rotate_largest", 1)
    cfg = SolveConfig(k_initial=20, max_attempts=200, reasoner_type="template")
    agent = CLAgent(cfg)
    mem = MemoryFacade()
    tools = ToolBridge()

    ans = agent.solve(task, mem, tools)

    # The Reflector attached its report to the trace.
    reflection = ans.trace.get("reflection")
    if not isinstance(reflection, dict):
        print("ERROR: trace missing 'reflection' block")
        print("trace keys:", list(ans.trace.keys()))
        return 1

    print("=== Reflector integration test (CLAgent + Reflector on rotate_largest/task_01) ===\n")
    print(f"  committed program : {ans.trace['committed_program']}")
    print(f"  audit_flagged     : {ans.trace['audit_flagged']}")
    print(f"  attempts          : {ans.trace['attempts']}")
    print(f"  tier-1 prediction : {ans.test_predictions[0] == task['task']['test'][0]['output']}")
    print()
    print("  --- ReflectionReport ---")
    for key in (
        "confidence",
        "contradiction",
        "audit_flagged",
        "action",
        "winner_label",
        "reasoning_text",
    ):
        print(f"  {key:<14s} : {reflection.get(key)!r}")

    # Schema sanity checks.
    assert 0.0 <= reflection["confidence"] <= 1.0, "confidence out of range"
    assert 0.0 <= reflection["contradiction"] <= 1.0, "contradiction out of range"
    assert reflection["action"] in (
        "commit", "refine", "ask_for_help", "fallback",
    ), f"invalid action {reflection['action']!r}"

    print("\nReflector integration test PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
