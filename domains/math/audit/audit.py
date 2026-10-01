"""Adversarial audit harness for math word-problem tasks.

Loads math-format task JSON, runs every registered shallow heuristic against
the test input, compares each prediction against the ground-truth test
output (via :func:`grading.grade`), and reports:

    * per-heuristic accuracy (# tier-1 hits / # tasks),
    * per-task ``trivially_solvable`` flag (True if any heuristic hits tier 1),
    * the list of solvers that hit on each flagged task.

Usage::

    python audit.py                       # uses bundled synthetic tasks
    python audit.py path/to/tasks.json    # loads tasks from a JSON file

The expected JSON shape matches the math task format: a list of task objects,
each with ``train`` and ``test`` lists of ``{"input": str, "output": str}``.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence, Tuple

# ``audit.py`` is also runnable as a script (``python audit.py ...``), so the
# heuristics import must work both as ``from .heuristics`` (when imported as
# part of the ``audit`` package) and as ``from heuristics`` (when run directly).
try:
    from .heuristics import HEURISTICS
except ImportError:  # pragma: no cover - script mode fallback
    from heuristics import HEURISTICS

# Optional integration with the math grader for tier-1 evaluation. We treat
# tier-1 of the math grader as "exact match"; tier-2 (within tolerance) and
# tier-3 (same magnitude) are *partial* credit and are *not* counted as a hit
# for the trivial-solver flag.
try:
    from grading.grade import grade as _grade
except Exception:  # pragma: no cover - we still want a useful baseline
    _grade = None


TrainPair = Tuple[str, str]


def _exact_match(pred: str, target: str) -> bool:
    """String-equality match — sufficient for the audit's "trivial hit" flag."""
    return pred == target


def _train_pairs(task: Dict[str, Any]) -> List[TrainPair]:
    return [(ex["input"], ex["output"]) for ex in task.get("train", [])]


def _test_io(task: Dict[str, Any]) -> Tuple[str, str]:
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
    per_heuristic_hits: Dict[str, int] = defaultdict(int)
    per_heuristic_total: Dict[str, int] = defaultdict(int)
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
    """Load tasks from a JSON file (list, single object, or A3S envelope).

    Accepts three shapes:

    * a top-level list of task bodies (or envelopes);
    * a single task body (``{"train": ..., "test": ...}``);
    * a single A3S envelope (``{"generator": ..., "task": {...}}``) — we
      unwrap the inner ``task`` body so callers see the same shape.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    # Envelope shape: unwrap ``task`` once.
    if isinstance(data, dict) and "task" in data and "train" not in data:
        data = data["task"]

    if isinstance(data, dict) and "train" in data:
        return [data]
    if isinstance(data, list):
        # Unwrap each element that is an envelope.
        out = []
        for elem in data:
            if isinstance(elem, dict) and "task" in elem and "train" not in elem:
                out.append(elem["task"])
            else:
                out.append(elem)
        return out
    raise ValueError(f"Unexpected JSON shape: {type(data).__name__}")


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
    lines.append(f"  {'task_id':<40s} {'trivial':<8s} solvers")
    for r in report["results"]:
        solvers = ",".join(r["solvers_hit"]) if r["solvers_hit"] else "-"
        lines.append(
            f"  {r['task_id']:<40s} {str(r['trivially_solvable']):<8s} {solvers}"
        )
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if len(argv) > 1:
        tasks = load_tasks(argv[1])
        source = argv[1]
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        examples_dir = os.path.abspath(os.path.join(here, "..", "examples"))
        tasks = []
        for gen_name in ("arithmetic_word_problems",
                         "multi_step_arithmetic",
                         "unit_conversion"):
            gen_dir = os.path.join(examples_dir, gen_name)
            for fname in sorted(os.listdir(gen_dir)):
                if fname.endswith(".json"):
                    tasks.append(load_tasks(os.path.join(gen_dir, fname))[0])
        source = "(bundled examples)"

    print(f"Loaded {len(tasks)} task(s) from {source}")
    report = audit_tasks(tasks)
    print(_format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
