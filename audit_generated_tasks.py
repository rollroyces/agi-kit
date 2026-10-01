"""Audit the 16 procedurally-generated ARC tasks against the shallow-heuristic battery.

This script is glue between:
  - the procedural generator output (one JSON per task, wrapped)
  - the adversarial audit harness (expects flat task objects)

It loads every task under 01-task-generator/examples/, strips the generator metadata
wrapper, runs the audit harness, and writes a report to 05-audit/audit_report.json
plus a human-readable text dump to 05-audit/audit_report.txt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the audit harness importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "05-audit"))

from audit import audit_tasks, _format_report  # type: ignore

EXAMPLES_ROOT = HERE / "01-task-generator" / "examples"
REPORT_JSON = HERE / "05-audit" / "audit_report.json"
REPORT_TXT = HERE / "05-audit" / "audit_report.txt"


def _load_all_generated_tasks() -> list[dict]:
    """Walk 01-task-generator/examples/**/task_*.json, strip wrapper, return flat list."""
    tasks: list[dict] = []
    for path in sorted(EXAMPLES_ROOT.rglob("task_*.json")):
        with open(path, "r", encoding="utf-8") as fh:
            wrapped = json.load(fh)
        gen = wrapped.get("generator", "<unknown>")
        params = wrapped.get("parameters", {})
        task = wrapped["task"]
        # Audit harness reads task.get("task_id", "<unnamed>") - inject a useful id.
        task["task_id"] = f"{gen}/{path.stem}"
        task["generator"] = gen
        task["parameters"] = params
        tasks.append(task)
    return tasks


def main() -> int:
    tasks = _load_all_generated_tasks()
    print(f"Loaded {len(tasks)} generated task(s) from {EXAMPLES_ROOT}")

    report = audit_tasks(tasks)

    with open(REPORT_JSON, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"Wrote {REPORT_JSON}")

    text = _format_report(report)
    with open(REPORT_TXT, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(f"Wrote {REPORT_TXT}")
    print()
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())