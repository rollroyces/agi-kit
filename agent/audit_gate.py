"""Audit gate: integrate ``standard/reference/audit.py`` into the agent.

Imports the sibling ``standard`` audit module and exposes two helpers:

* :func:`audit_task_quickly` — runs the audit heuristics from
  ``domains/arc/audit/heuristics.py`` (via the standard wrapper) on a task,
  returning the full §7 verdict dict.

* :func:`is_audit_flagged_for_answer` — given a candidate answer and the
  underlying task, returns ``True`` iff any shallow heuristic produced exactly
  the same test prediction as the agent.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
_STANDARD = _ROOT / "standard"
sys.path.insert(0, str(_STANDARD))

# Importing ``reference.audit`` will trigger a sibling-import of the
# domains/arc/audit heuristics file. That side effect is by design — the
# standard audit module owns the registry.
from reference.audit import audit_task, HEURISTICS  # noqa: E402  (path injected above)


def audit_task_quickly(task: Dict[str, Any]) -> Dict[str, Any]:
    """Run the canonical §7 audit on a single task."""
    return audit_task(task)


def _train_pairs(task: Dict[str, Any]) -> List[Any]:
    return [(ex["input"], ex["output"]) for ex in task.get("task", {}).get("train", [])]


def is_audit_flagged_for_answer(task: Dict[str, Any], predicted_test: List[List[int]]) -> bool:
    """True iff any shallow heuristic produced exactly the same test prediction."""
    if not task.get("task", {}).get("test"):
        return False
    test_in = task["task"]["test"][0]["input"]
    train = _train_pairs(task)
    for name, fn in HEURISTICS.items():
        try:
            pred = fn(train, test_in)
        except Exception:
            continue
        if pred == predicted_test:
            return True
    return False
