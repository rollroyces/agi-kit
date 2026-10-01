"""Standard §7 — Audit protocol: run heuristics from the canonical registry.

This module imports the existing heuristics from
``domains/arc/audit/heuristics.py`` (rather than re-implementing them) and
wraps each with the §7 verdict schema. Conformance requires ≥5 heuristics
covering ≥5 categories; the imported registry already satisfies this.

Usage::

    from reference.audit import audit_task, audit_tasks, REQUIRED_CATEGORIES

    verdict = audit_task(task_dict)
    report  = audit_tasks([task_dict, ...])
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Sequence, Tuple

_THIS = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.abspath(os.path.join(_THIS, "..", ".."))

import importlib.util as _ilu  # noqa: E402
_HEURISTICS_PATH = os.path.join(
    _PROJECT, "domains", "arc", "audit", "heuristics.py",
)
_spec = _ilu.spec_from_file_location("_standard_inner_heuristics", _HEURISTICS_PATH)
_inner = _ilu.module_from_spec(_spec)
sys.modules["_standard_inner_heuristics"] = _inner
_spec.loader.exec_module(_inner)
HEURISTICS = _inner.HEURISTICS


REQUIRED_CATEGORIES = {
    "identity":   ["identity"],
    "palette":    ["palette_majority", "palette_invert", "background_swap"],
    "geometry":   ["mirror", "diagonal_replicate"],
    "object":     ["largest_object"],
    "counting":   ["single_color_fill"],
}


def _categories_covered() -> Dict[str, bool]:
    return {cat: any(h in HEURISTICS for h in members)
            for cat, members in REQUIRED_CATEGORIES.items()}


def _audit_version() -> str:
    """sha256 of the heuristics.py source, mirroring SPEC §7's audit_version."""
    src_path = os.path.join(
        _PROJECT, "domains", "arc", "audit", "heuristics.py",
    )
    with open(src_path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _train_pairs(task: Dict[str, Any]) -> Sequence[Tuple[List[List[int]], List[List[int]]]]:
    return [(ex["input"], ex["output"]) for ex in task.get("task", {}).get("train", [])]


def _test_io(task: Dict[str, Any]) -> Tuple[List[List[int]], List[List[int]]]:
    test = task["task"]["test"][0]
    return test["input"], test["output"]


def _exact_match(pred: Any, target: Any) -> bool:
    return pred == target


def audit_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Run every registered heuristic against one task (§7.3 schema)."""
    train = _train_pairs(task)
    test_in, test_out = _test_io(task)

    per_heuristic: Dict[str, Dict[str, Any]] = {}
    solvers_hit: List[str] = []
    for name, fn in HEURISTICS.items():
        try:
            pred = fn(train, test_in)
        except Exception as exc:
            per_heuristic[name] = {"hit": False, "rationale": f"raised: {exc}"}
            continue
        hit = _exact_match(pred, test_out)
        per_heuristic[name] = {"hit": hit, "rationale": "exact match" if hit else "miss"}
        if hit:
            solvers_hit.append(name)

    trivially_solvable = bool(solvers_hit)
    return {
        "task_id":           task.get("task_id", task.get("generator", "<unnamed>")),
        "audited_at":        _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
        "audit_version":     _audit_version(),
        "heuristics_run":    list(HEURISTICS.keys()),
        "per_heuristic":     per_heuristic,
        "trivially_solvable": trivially_solvable,
        "verdict":           "quarantine" if trivially_solvable else "pass",
    }


def audit_tasks(tasks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Audit many tasks; aggregate per-heuristic accuracy + verdicts (§7)."""
    verdicts = [audit_task(t) for t in tasks]
    hits = defaultdict(int)
    totals = defaultdict(int)
    for v in verdicts:
        for h, info in v["per_heuristic"].items():
            totals[h] += 1
            if info["hit"]:
                hits[h] += 1
    return {
        "n_tasks":            len(verdicts),
        "n_trivially_solvable": sum(1 for v in verdicts if v["trivially_solvable"]),
        "per_heuristic_accuracy": {
            h: (hits[h] / totals[h] if totals[h] else 0.0) for h in HEURISTICS
        },
        "categories_covered":   _categories_covered(),
        "verdicts":             verdicts,
    }


# --- usage example -----------------------------------------------------------

if __name__ == "__main__":
    sample = {
        "generator": "demo",
        "task": {
            "train": [{"input": [[0]], "output": [[0]]}],
            "test":  [{"input": [[0]], "output": [[0]]}],
        },
    }
    v = audit_task(sample)
    assert v["verdict"] in ("pass", "quarantine")
    print(f"audit.py: 1 task audited, verdict={v['verdict']}, "
          f"categories_covered={_categories_covered()}")
