"""Driver that exercises the math domain end-to-end on the bundled examples.

Steps:

1. Load all 12 example tasks from ``examples/`` (4 per generator).
2. Run the audit on each — flag any task a shallow heuristic solves exactly.
3. Grade a baseline (the ``echo_first_number`` heuristic) and an
   identity-echo baseline against each task's ground truth.
4. Write ``outputs/eval_log.json`` with per-task results.
5. Print a summary table.

Usage:
    python run_eval.py
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from audit.audit import audit_task, load_tasks  # noqa: E402
from audit.heuristics import HEURISTICS  # noqa: E402
from grading.grade import grade, grade_task  # noqa: E402


EXAMPLE_DIR = os.path.join(_HERE, "examples")
OUTPUT_DIR = os.path.join(_HERE, "outputs")
GENERATORS = ("arithmetic_word_problems", "multi_step_arithmetic", "unit_conversion")


def _load_examples() -> List[Dict[str, Any]]:
    """Load all 12 example tasks (4 per generator).

    Each task is augmented with ``task_id`` (e.g. ``"arithmetic_word_problems/task_01"``)
    and ``generator`` so the summary table is meaningful.
    """
    tasks: List[Dict[str, Any]] = []
    for gen in GENERATORS:
        gen_dir = os.path.join(EXAMPLE_DIR, gen)
        for fname in sorted(os.listdir(gen_dir)):
            if fname.endswith(".json"):
                path = os.path.join(gen_dir, fname)
                loaded = load_tasks(path)
                for body in loaded:
                    body["task_id"] = f"{gen}/{fname[:-len('.json')]}"
                    body["generator"] = gen
                tasks.extend(loaded)
    return tasks


def _format_summary(rows: List[Dict[str, Any]]) -> str:
    """Render a tabular summary of the eval run."""
    lines = []
    lines.append(f"Math domain eval — {len(rows)} task(s)")
    lines.append("")
    header = (
        f"  {'task':<40s} {'generator':<26s} "
        f"{'trivial':<8s} {'first_num':<10s} {'echo':<6s}"
    )
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    trivially_solvable = 0
    for r in rows:
        lines.append(
            f"  {r['task_id']:<40s} {r['generator']:<26s} "
            f"{str(r['trivially_solvable']):<8s} "
            f"{r['first_num_tier']:<10d} {r['echo_tier']:<6d}"
        )
        if r["trivially_solvable"]:
            trivially_solvable += 1
    lines.append("")
    lines.append(f"Trivially-solvable: {trivially_solvable} / {len(rows)}")
    avg_first_num = (
        sum(r["first_num_score"] for r in rows) / len(rows) if rows else 0.0
    )
    avg_echo = (
        sum(r["echo_score"] for r in rows) / len(rows) if rows else 0.0
    )
    lines.append(f"Avg baseline score (echo_first_number): {avg_first_num:.3f}")
    lines.append(f"Avg baseline score (identity_echo):    {avg_echo:.3f}")
    return "\n".join(lines)


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tasks = _load_examples()
    print(f"Loaded {len(tasks)} example task(s)")

    rows: List[Dict[str, Any]] = []
    for task in tasks:
        # --- audit ---------------------------------------------------------
        audit_result = audit_task(task)
        # --- grade baselines ----------------------------------------------
        train = [(ex["input"], ex["output"]) for ex in task["train"]]
        test_in = task["test"][0]["input"]
        test_out = task["test"][0]["output"]

        first_num_pred = HEURISTICS["echo_first_number"](train, test_in)
        echo_pred = HEURISTICS["identity_echo"](train, test_in)

        first_num_grade = grade(first_num_pred, test_out)
        echo_grade = grade(echo_pred, test_out)

        # Use the task-aggregate grader too — it's the same answer for
        # single-pair tasks but we want to exercise the API.
        agg = grade_task(task, [first_num_pred])

        rows.append({
            "task_id": task.get("task_id", "<unnamed>"),
            "generator": task.get("generator", "<unknown>"),
            "trivially_solvable": audit_result["trivially_solvable"],
            "solvers_hit": audit_result["solvers_hit"],
            "per_heuristic": audit_result["per_heuristic"],
            "first_num_pred": first_num_pred,
            "first_num_tier": first_num_grade["tier"],
            "first_num_score": first_num_grade["score"],
            "echo_pred": echo_pred,
            "echo_tier": echo_grade["tier"],
            "echo_score": echo_grade["score"],
            "ground_truth": test_out,
            "aggregate_task_score": agg["task_score"],
        })

    log_path = os.path.join(OUTPUT_DIR, "eval_log.json")
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump({
            "n_tasks": len(rows),
            "rows": rows,
        }, fh, indent=2, sort_keys=True)
    print(f"Wrote {log_path}")

    print()
    print(_format_summary(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
