"""Four-tier math grader.

Tiering
-------
* **tier1** — predicted string is exactly equal to ground-truth.
* **tier2** — both parse as numbers and the absolute difference is within
  ``tolerance`` (default ``1e-6``).
* **tier3** — both parse as numbers and ``abs(pred / truth)`` (or its
  reciprocal) is within a factor of 10 — i.e. off by a power of 10 or
  close to it. This catches unit-mixups and digit-shift mistakes.
* **tier0** — no match.

The grader exposes:

* :func:`grade(predicted, ground_truth, tolerance)` — single-pair scoring.
* :func:`grade_task(task, predictions, tolerance)` — aggregate over a math
  task with one or more predictions per test example (the A3S v1 spec only
  has a single test example, but the aggregate API mirrors the ARC grader's
  contract for cross-domain parity).

Tier weights
------------
* tier1 → 1.0
* tier2 → 0.7
* tier3 → 0.3
* tier0 → 0.0

These are the same weights the ARC grader uses, so cross-domain aggregate
scores are directly comparable.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

TIER_WEIGHTS: Dict[int, float] = {1: 1.0, 2: 0.7, 3: 0.3, 0: 0.0}

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_number(text: str) -> Optional[float]:
    """Return the first number found in ``text`` as a float, or ``None``."""
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)
    m = _NUMBER_RE.search(text)
    if m is None:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _same_magnitude(a: float, b: float) -> bool:
    """Return True iff ``a`` and ``b`` are within a factor of 10 of each other
    in either direction.

    Specifically::

        1/10 <= a/b <= 10   (with b != 0)

    Both zero is considered the same magnitude (trivially equal)."""
    if a == 0 and b == 0:
        return True
    if a == 0 or b == 0:
        return False
    ratio = abs(a / b)
    return 0.1 <= ratio <= 10.0


def grade(predicted: str, ground_truth: str, tolerance: float = 1e-6) -> Dict[str, Any]:
    """Score a single ``(predicted, ground_truth)`` pair.

    Returns a dict with ``tier`` in {0, 1, 2, 3}, ``score`` (the weight),
    and diagnostic fields:

    * ``predicted_value`` / ``ground_truth_value`` — the parsed numbers
      (``None`` if the string did not contain a number).
    * ``absolute_error`` — ``|pred - truth|`` (or ``None``).
    * ``magnitude_ratio`` — ``|pred / truth|`` (or ``None``).
    """
    pred_num = _parse_number(predicted)
    truth_num = _parse_number(ground_truth)

    abs_err: Optional[float] = None
    ratio: Optional[float] = None

    # --- tier 1: exact string equality (cheapest, do first) ------------------
    if predicted == ground_truth:
        if pred_num is not None and truth_num is not None:
            abs_err = abs(pred_num - truth_num)
            if truth_num != 0:
                ratio = abs(pred_num / truth_num)
        return {
            "tier": 1,
            "score": TIER_WEIGHTS[1],
            "predicted_value": pred_num,
            "ground_truth_value": truth_num,
            "absolute_error": abs_err,
            "magnitude_ratio": ratio,
        }

    # --- cannot parse one or both: only exact-string match counts ----------
    if pred_num is None or truth_num is None:
        return {
            "tier": 0,
            "score": TIER_WEIGHTS[0],
            "predicted_value": pred_num,
            "ground_truth_value": truth_num,
            "absolute_error": None,
            "magnitude_ratio": None,
        }

    abs_err = abs(pred_num - truth_num)
    ratio = abs(pred_num / truth_num) if truth_num != 0 else math.inf

    # --- tier 2: within tolerance ------------------------------------------
    if abs_err <= tolerance:
        return {
            "tier": 2,
            "score": TIER_WEIGHTS[2],
            "predicted_value": pred_num,
            "ground_truth_value": truth_num,
            "absolute_error": abs_err,
            "magnitude_ratio": ratio,
        }

    # --- tier 3: same magnitude (off by a power of 10 or so) ---------------
    if _same_magnitude(pred_num, truth_num):
        return {
            "tier": 3,
            "score": TIER_WEIGHTS[3],
            "predicted_value": pred_num,
            "ground_truth_value": truth_num,
            "absolute_error": abs_err,
            "magnitude_ratio": ratio,
        }

    # --- tier 0: no match ---------------------------------------------------
    return {
        "tier": 0,
        "score": TIER_WEIGHTS[0],
        "predicted_value": pred_num,
        "ground_truth_value": truth_num,
        "absolute_error": abs_err,
        "magnitude_ratio": ratio,
    }


def grade_task(task: Dict[str, Any],
               predictions: Sequence[Any],
               tolerance: float = 1e-6) -> Dict[str, Any]:
    """Score one or more predictions against a math task's test pair(s).

    ``task`` is a math task envelope or inner body. ``predictions`` is a
    sequence of the same length as ``task['test']``; each prediction is a
    string (the agent's answer). Returns the standard aggregate dict.
    """
    test_pairs = task.get("test") or task.get("task", {}).get("test", [])
    if not test_pairs:
        raise ValueError("grade_task: task has no 'test' pairs")
    if len(predictions) != len(test_pairs):
        raise ValueError(
            f"grade_task: predictions length {len(predictions)} != test length {len(test_pairs)}"
        )

    per_example: List[Dict[str, Any]] = []
    for pred, pair in zip(predictions, test_pairs):
        truth = pair["output"]
        per_example.append(grade(pred, truth, tolerance=tolerance))

    scores = [r["score"] for r in per_example]
    task_score = float(sum(scores) / len(scores)) if scores else 0.0
    tier1_scores = [r["score"] for r in per_example if r["tier"] == 1]
    strict_score = float(sum(tier1_scores) / len(tier1_scores)) if tier1_scores else None

    return {
        "per_example": per_example,
        "task_score": task_score,
        "strict": strict_score,
        "tolerance": tolerance,
    }


__all__ = [
    "TIER_WEIGHTS",
    "grade",
    "grade_task",
]
