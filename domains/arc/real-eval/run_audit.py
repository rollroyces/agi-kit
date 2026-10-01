"""run_audit.py — apply the 8 shallow heuristics to the real ARC-AGI-1 subset.

The headline metric of this benchmark is the **shallow-exploitable rate**:
the fraction of tasks that any one of the trivial heuristics in
``domains/arc/audit/heuristics.py`` solves exactly. This number tells us how
much of ARC-AGI-1's "difficulty" is illusory — solvable by a single rule that
never looks at the training pairs.

The script re-uses ``domains/arc/audit/audit.py`` as a library so the
heuristic set, scoring, and reporting stay consistent with the previous
(synthetic) audit.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

_HERE = Path(__file__).resolve().parent
_AUDIT_DIR = _HERE.parent / "audit"

if str(_AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(_AUDIT_DIR))

from audit import audit_task, audit_tasks, HEURISTICS  # noqa: E402


def _now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def _load_arc_tasks(data_dir: Path, n_train: int, n_eval: int) -> List[Dict[str, Any]]:
    """Load tasks in the bare ARC format that ``audit.audit_task`` expects.

    Note: this is different from ``run_real_eval.py`` — the audit module
    operates on the raw task dict (``{"train": ..., "test": ...}``), not the
    agent-wrapped envelope. We do NOT wrap here.
    """
    out: List[Dict[str, Any]] = []
    for sub, want in (("training", n_train), ("evaluation", n_eval)):
        sub_dir = data_dir / sub
        if not sub_dir.exists():
            print(f"WARN: missing dir {sub_dir}", file=sys.stderr)
            continue
        ids = sorted(p.stem for p in sub_dir.glob("*.json"))
        if want and want < len(ids):
            ids = ids[:want]
        for tid in ids:
            with open(sub_dir / f"{tid}.json", encoding="utf-8") as fh:
                raw = json.load(fh)
            # Attach task_id so audit_task has it.
            raw["task_id"] = tid
            raw["__split__"] = sub
            out.append(raw)
    return out


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=str(_HERE / "data" / "arc-agi-1"),
    )
    parser.add_argument("--n-train", type=int, default=100)
    parser.add_argument("--n-eval", type=int, default=50)
    parser.add_argument(
        "--output",
        default=str(_HERE / "outputs" / "audit_log.json"),
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print(f"[run_audit] loading from {data_dir} ({args.n_train}+{args.n_eval} tasks)")
    tasks = _load_arc_tasks(data_dir, args.n_train, args.n_eval)
    print(f"[run_audit] loaded {len(tasks)} tasks")

    started = time.time()
    report = audit_tasks(tasks)
    wallclock = time.time() - started

    # Enrich per-task records with __split__.
    enriched: List[Dict[str, Any]] = []
    for raw, r in zip(tasks, report["results"]):
        r = dict(r)
        r["split"] = raw.get("__split__", "?")
        enriched.append(r)
    report["results"] = enriched

    # Compute the *by-split* breakdown so we can talk about training vs
    # evaluation separately in the report.
    by_split: Dict[str, Dict[str, int]] = {}
    for raw, r in zip(tasks, enriched):
        sp = raw.get("__split__", "?")
        b = by_split.setdefault(
            sp, {"n": 0, "n_trivial": 0, "by_heuristic": {}}
        )
        b["n"] += 1
        if r["trivially_solvable"]:
            b["n_trivial"] += 1
        for name, hit in r["per_heuristic"].items():
            b["by_heuristic"].setdefault(name, {"hit": 0, "total": 0})
            b["by_heuristic"][name]["total"] += 1
            if hit:
                b["by_heuristic"][name]["hit"] += 1

    overall_rate = report["n_trivially_solvable"] / max(1, report["n_tasks"])

    log = {
        "schema_version": "0.1.0",
        "started_at": _now(),
        "finished_at": _now(),
        "wallclock_s": round(wallclock, 2),
        "n_tasks": report["n_tasks"],
        "n_trivially_solvable": report["n_trivially_solvable"],
        "shallow_exploitable_rate": overall_rate,
        "per_heuristic_accuracy": report["per_heuristic_accuracy"],
        "per_heuristic_hits": report["per_heuristic_hits"],
        "per_heuristic_total": report["per_heuristic_total"],
        "by_split": by_split,
        "results": enriched,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=2)
    print(f"[run_audit] wrote {out}")

    # Console summary
    print("\n=== domains/arc/real-eval :: run_audit summary ===")
    print(f"Tasks audited                  : {report['n_tasks']}")
    print(
        f"Trivially-solvable tasks       : {report['n_trivially_solvable']:3d} "
        f"/ {report['n_tasks']}"
    )
    print(f"Shallow-exploitable rate (HEAD): {overall_rate:6.2%}")
    print("\nPer-heuristic accuracy:")
    for name in sorted(HEURISTICS.keys()):
        hits = report["per_heuristic_hits"].get(name, 0)
        total = report["per_heuristic_total"].get(name, 0)
        acc = report["per_heuristic_accuracy"].get(name, 0.0)
        print(f"  {name:<22s} {hits:>3d}/{total:<3d}  ({acc:>6.2%})")
    print("\nBy split:")
    for sp, b in by_split.items():
        rate = b["n_trivial"] / max(1, b["n"])
        print(f"  {sp:12s} trivial={b['n_trivial']:3d}/{b['n']:3d}  ({rate:6.2%})")
    return 0


if __name__ == "__main__":
    sys.exit(_main())