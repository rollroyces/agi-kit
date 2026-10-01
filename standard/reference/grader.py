"""Standard §8 — Scoring protocol: hierarchical 3-tier grader wrapper.

Imports :mod:`domains.arc.grading.grader` (canonical implementation) and
exposes the §8 per-task result schema. The wrapper enforces the SPEC §8.4
``task_score`` = mean(per-pair scores) rule.

Usage::

    from reference.grader import grade_predictions, INVARIANCES

    result = grade_predictions(
        predicted=[predicted_grid],
        ground_truth=[ground_truth_grid],
        task_metadata={"invariances": INVARIANCES},
    )
    print(result["task_score"])
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Sequence

_THIS = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.abspath(os.path.join(_THIS, "..", ".."))

import importlib.util as _ilu  # noqa: E402
_GRADER_PATH = os.path.join(
    _PROJECT, "domains", "arc", "grading", "grader.py",
)
_spec = _ilu.spec_from_file_location("_standard_inner_grader", _GRADER_PATH)
_inner = _ilu.module_from_spec(_spec)
sys.modules["_standard_inner_grader"] = _inner
_spec.loader.exec_module(_inner)

DEFAULT_INVARIANCES = _inner.DEFAULT_INVARIANCES
INVARIANCE_LABELS   = _inner.INVARIANCE_LABELS
TIER_WEIGHTS        = _inner.TIER_WEIGHTS
grade_example       = _inner.grade_example
grade               = _inner.grade
exact_match         = _inner.exact_match
equivalence_match   = _inner.equivalence_match
structural_match    = _inner.structural_match


# Standard v1 freezes these tier weights; re-exported for downstream code.
TIER_WEIGHTS_FROZEN = {0: 0.0, 1: 1.0, 2: 0.7, 3: 0.3}
INVARIANCES_FROZEN = ("id", "pal", "rot90", "rot180", "rot270", "fh", "fv", "tr")

assert TIER_WEIGHTS_FROZEN == TIER_WEIGHTS, "Tier weights must match SPEC §8.1"


def audit_failed_passthrough(verdict: Optional[Dict[str, Any]]) -> bool:
    """Return ``True`` if a §7 audit verdict quarantines the task.

    Per SPEC §7.4, quarantined tasks **MUST** be reported with
    ``audit_failed: true`` rather than silently scored as zero.
    """
    if verdict is None:
        return False
    return verdict.get("verdict") == "quarantine"


def grade_predictions(predicted: Sequence[Any],
                      ground_truth: Sequence[Any],
                      task_metadata: Optional[Dict[str, Any]] = None,
                      audit_verdict: Optional[Dict[str, Any]] = None
                      ) -> Dict[str, Any]:
    """Wrap :func:`grader.grade` with the §8 envelope + audit gating."""
    meta = dict(task_metadata or {})
    meta.setdefault("invariances", list(INVARIANCES_FROZEN))

    result = grade(predicted, ground_truth, task_metadata=meta)
    result["invariances_used"] = list(meta["invariances"])
    result["audit_failed"] = audit_failed_passthrough(audit_verdict)

    # Convert per_example rows into the §8.3 schema (aliasing existing keys).
    per_example_standard = []
    for row in result["per_example"]:
        per_example_standard.append({
            "tier":              row["tier"],
            "score":             row["score"],
            "matched_invariance":row["matched_invariance"],
            "palette_mapping":   row["palette_mapping"],
            "cell_match":        row["cell_match"],
            "object_iou":        row["object_iou"],
            "audit_failed":      result["audit_failed"],
        })
    result["per_example"] = per_example_standard
    return result


# --- usage example -----------------------------------------------------------

if __name__ == "__main__":
    pred = [[0, 1], [1, 0]]
    gt   = [[0, 1], [1, 0]]
    res = grade_predictions([pred], [gt])
    assert res["task_score"] == 1.0
    assert res["per_example"][0]["tier"] == 1
    print(f"grader.py: tier1 score={res['task_score']}, "
          f"audit_failed={res['audit_failed']}")
