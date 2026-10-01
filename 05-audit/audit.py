"""Adversarial audit harness for ARC tasks.

Loads ARC-format task JSON, runs every registered shallow heuristic against the
test input, compares each prediction against the ground-truth test output, and
reports:

    * per-heuristic accuracy (# exact matches / # tasks),
    * per-task "trivially_solvable" flag (True if any heuristic is exact),
    * the list of solvers that hit on each flagged task.

Usage:
    python audit.py                       # uses bundled synthetic tasks
    python audit.py path/to/tasks.json    # loads tasks from a JSON file

The expected JSON shape matches the ARC-AGI public release: a list of task
objects, each with `train` and `test` lists of {"input": grid, "output": grid}.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from heuristics import HEURISTICS


Grid = List[List[int]]


def _exact_match(pred: Grid, target: Grid) -> bool:
    if not pred or not target:
        return pred == target
    if len(pred) != len(target):
        return False
    for r1, r2 in zip(pred, target):
        if list(r1) != list(r2):
            return False
    return True


def _train_pairs(task: Dict[str, Any]) -> Sequence[Tuple[Grid, Grid]]:
    return [(ex["input"], ex["output"]) for ex in task.get("train", [])]


def _test_io(task: Dict[str, Any]) -> Tuple[Grid, Grid]:
    test = task["test"][0]
    return test["input"], test["output"]


def audit_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Run every heuristic against a single task and report results."""
    train = _train_pairs(task)
    test_in, test_out = _test_io(task)

    solvers_hit: List[str] = []
    per_heuristic: Dict[str, bool] = {}
    for name, fn in HEURISTICS.items():
        try:
            pred = fn(train, test_in)
        except Exception as exc:  # pragma: no cover - heuristics should not raise
            per_heuristic[name] = False
            print(f"  [!] {name} raised: {exc}", file=sys.stderr)
            continue
        hit = _exact_match(pred, test_out)
        per_heuristic[name] = hit
        if hit:
            solvers_hit.append(name)

    return {
        "task_id": task.get("task_id", "<unnamed>"),
        "trivially_solvable": bool(solvers_hit),
        "solvers_hit": solvers_hit,
        "per_heuristic": per_heuristic,
    }


def audit_tasks(tasks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Run the audit over many tasks and aggregate statistics."""
    results: List[Dict[str, Any]] = []
    per_heuristic_hits = defaultdict(int)
    per_heuristic_total = defaultdict(int)
    trivially_solvable_count = 0

    for task in tasks:
        result = audit_task(task)
        results.append(result)
        if result["trivially_solvable"]:
            trivially_solvable_count += 1
        for name, hit in result["per_heuristic"].items():
            per_heuristic_total[name] += 1
            if hit:
                per_heuristic_hits[name] += 1

    accuracy = {
        name: (
            per_heuristic_hits[name] / per_heuristic_total[name]
            if per_heuristic_total[name]
            else 0.0
        )
        for name in HEURISTICS
    }

    return {
        "n_tasks": len(results),
        "n_trivially_solvable": trivially_solvable_count,
        "per_heuristic_accuracy": accuracy,
        "per_heuristic_hits": dict(per_heuristic_hits),
        "per_heuristic_total": dict(per_heuristic_total),
        "results": results,
    }


def load_tasks(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "train" in data:
        return [data]
    if not isinstance(data, list):
        raise ValueError(f"Unexpected JSON shape: {type(data).__name__}")
    return data


def _format_report(report: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"Audit summary across {report['n_tasks']} task(s)")
    lines.append(f"Trivially-solvable tasks: {report['n_trivially_solvable']} / {report['n_tasks']}")
    lines.append("")
    lines.append("Per-heuristic accuracy:")
    for name, acc in report["per_heuristic_accuracy"].items():
        hits = report["per_heuristic_hits"].get(name, 0)
        total = report["per_heuristic_total"].get(name, 0)
        lines.append(f"  {name:<22s} {hits:>3d}/{total:<3d}  ({acc:>6.1%})")
    lines.append("")
    lines.append("Per-task results:")
    lines.append(f"  {'task_id':<22s} {'trivial':<8s} solvers")
    for r in report["results"]:
        solvers = ",".join(r["solvers_hit"]) if r["solvers_hit"] else "-"
        lines.append(
            f"  {r['task_id']:<22s} {str(r['trivially_solvable']):<8s} {solvers}"
        )
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if len(argv) > 1:
        tasks = load_tasks(argv[1])
        source = argv[1]
    else:
        from synthetic_tasks import TASKS
        tasks = TASKS
        source = "(bundled synthetic_tasks.TASKS)"

    print(f"Loaded {len(tasks)} task(s) from {source}")
    report = audit_tasks(tasks)
    print(_format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))