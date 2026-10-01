"""run_grading.py — apply the hierarchical grader to the real-eval subset.

Loads ``outputs/real_eval_log.json`` (produced by ``run_real_eval.py``) and
re-grades every agent prediction against ground truth using the canonical
``domains/arc/grading/grader.grade_example``. Falls back to the identity grid
(test input) for tasks where the agent committed nothing.

Tier definitions are unchanged from grader.py:
    tier 1 : exact match
    tier 2 : equivalence under (rot, flip, palette-perm, translation)
    tier 3 : structural (cell-match >= 0.6 + count within ±1)
    tier 0 : otherwise

The script also records which tier *was* assigned vs which tier the *baseline*
(echo-input) gets, so the audit table can show the lift over baseline.
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE = Path(__file__).resolve().parent
_GRADER = _HERE.parent / "grading"

if str(_GRADER) not in sys.path:
    sys.path.insert(0, str(_GRADER))

from grader import grade_example  # noqa: E402


def _now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def _load_arc_tasks(data_dir: Path, n_train: int, n_eval: int) -> Dict[str, Dict[str, Any]]:
    """Bare ARC tasks indexed by ``split/task_id`` for lookup during grading."""
    out: Dict[str, Dict[str, Any]] = {}
    for sub, want in (("training", n_train), ("evaluation", n_eval)):
        sub_dir = data_dir / sub
        if not sub_dir.exists():
            continue
        ids = sorted(p.stem for p in sub_dir.glob("*.json"))
        if want and want < len(ids):
            ids = ids[:want]
        for tid in ids:
            with open(sub_dir / f"{tid}.json", encoding="utf-8") as fh:
                raw = json.load(fh)
            out[f"{sub}/{tid}"] = raw
    return out


def _baseline_guess(task_raw: Dict[str, Any]) -> Any:
    return copy.deepcopy(task_raw["test"][0]["input"])


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(_HERE / "data" / "arc-agi-1"))
    parser.add_argument("--n-train", type=int, default=100)
    parser.add_argument("--n-eval", type=int, default=50)
    parser.add_argument(
        "--real-eval-log",
        default=str(_HERE / "outputs" / "real_eval_log.json"),
    )
    parser.add_argument(
        "--output",
        default=str(_HERE / "outputs" / "grading_log.json"),
    )
    args = parser.parse_args()

    real_log_path = Path(args.real_eval_log)
    if not real_log_path.exists():
        print(f"FATAL: {real_log_path} not found. Run run_real_eval.py first.",
              file=sys.stderr)
        return 2
    with open(real_log_path, encoding="utf-8") as fh:
        real_log = json.load(fh)

    # Need ground-truth tasks. We re-run the agent to get its *prediction*;
    # but the real_eval_log already has predictions? No — it doesn't store
    # the raw grid (only the tier flags). We re-run, with caching, then
    # grade against ground truth. To keep this script self-contained AND
    # fast, we re-import the agent.
    print("[run_grading] loading tasks + agent (re-import)...")
    sys.path.insert(0, str(_HERE))
    from run_real_eval import _wrap_for_agent, _load_tasks  # noqa: E402
    from agent import CLAgent, SolveConfig  # noqa: E402
    from memory import ProceduralMemory  # noqa: E402
    from reference.airt import InMemoryStore, ToolBridge  # noqa: E402

    cfg = SolveConfig(reasoner_type="template", k_initial=20, wallclock_budget_s=10.0)
    agent = CLAgent(config=cfg)
    data_dir = Path(args.data_dir)
    tasks = _load_tasks(data_dir, n_train=args.n_train, n_eval=args.n_eval, seed=0)
    by_split_id = {(t["split"], t["task_id"]): t["raw"] for t in tasks}

    graded_records: List[Dict[str, Any]] = []
    for item in tasks:
        sid, tid, raw = item["split"], item["task_id"], item["raw"]
        key = f"{sid}/{tid}"
        target = raw["test"][0].get("output")
        # Find matching real_eval record for tier flags
        re_rec = next(
            (r for r in real_log["records"] if r["task_id"] == tid and r["split"] == sid),
            None,
        )
        # Re-run the agent (cheap — template proposer is fast).
        try:
            wrapped = _wrap_for_agent(tid, raw)
            ans = agent.solve(wrapped, ProceduralMemory(), ToolBridge())
            pred = ans.test_predictions[0] if ans.test_predictions else None
            committed = ans.trace.get("committed_program")
        except Exception as exc:
            pred, committed = None, None
            print(f"  [skip-grade] {key}: {exc}", file=sys.stderr)
        if pred is None:
            # Fallback: identity (the agent's documented fallback for shape
            # failures) — see run_grading's spec for the "identity fallback".
            pred = _baseline_guess(raw)
            used_fallback = True
        else:
            used_fallback = False
        # Grade the prediction vs ground truth
        try:
            graded = grade_example(pred, target)
        except Exception as exc:
            graded = {
                "tier": 0,
                "score": 0.0,
                "matched_invariance": None,
                "cell_match": 0.0,
                "object_iou": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
            }
        # Grade the baseline (echo) as a reference point.
        try:
            baseline = grade_example(_baseline_guess(raw), target)
        except Exception:
            baseline = {"tier": 0, "score": 0.0, "cell_match": 0.0}
        graded_records.append({
            "task_id": tid,
            "split": sid,
            "agent_tier": graded["tier"],
            "agent_score": graded["score"],
            "agent_cell_match": graded.get("cell_match", 0.0),
            "agent_matched_invariance": graded.get("matched_invariance"),
            "baseline_tier": baseline["tier"],
            "baseline_score": baseline["score"],
            "lift": graded["score"] - baseline["score"],
            "committed_program": committed,
            "used_identity_fallback": used_fallback,
            "real_eval_tier1": re_rec["tier1"] if re_rec else None,
            "real_eval_tier2": re_rec["tier2"] if re_rec else None,
            "real_eval_tier3": re_rec["tier3"] if re_rec else None,
            "real_eval_attempts": re_rec["attempts"] if re_rec else None,
            "real_eval_audit_flagged": re_rec["audit_flagged"] if re_rec else None,
        })

    # Aggregate
    n = len(graded_records)
    by_tier_agent = defaultdict(int)
    by_tier_baseline = defaultdict(int)
    by_split = defaultdict(lambda: {"n": 0, "tier1": 0, "tier2": 0, "tier3": 0,
                                    "baseline_tier1": 0})
    total_lift = 0.0
    n_lift = 0
    for r in graded_records:
        by_tier_agent[r["agent_tier"]] += 1
        by_tier_baseline[r["baseline_tier"]] += 1
        b = by_split[r["split"]]
        b["n"] += 1
        if r["agent_tier"] == 1:
            b["tier1"] += 1
        if r["agent_tier"] >= 2:
            b["tier2"] += 1
        if r["agent_tier"] >= 3:
            b["tier3"] += 1
        if r["baseline_tier"] == 1:
            b["baseline_tier1"] += 1
        total_lift += r["lift"]
        n_lift += 1

    summary = {
        "n_tasks": n,
        "by_tier_agent": dict(by_tier_agent),
        "by_tier_baseline": dict(by_tier_baseline),
        "tier1_rate_agent": by_tier_agent[1] / max(1, n),
        "tier2_rate_agent": by_tier_agent[2] / max(1, n),
        "tier3_rate_agent": by_tier_agent[3] / max(1, n),
        "tier1_rate_baseline": by_tier_baseline[1] / max(1, n),
        "tier2_rate_baseline": by_tier_baseline[2] / max(1, n),
        "tier3_rate_baseline": by_tier_baseline[3] / max(1, n),
        "avg_lift_over_baseline": total_lift / max(1, n_lift),
        "by_split": dict(by_split),
    }

    log = {
        "schema_version": "0.1.0",
        "started_at": _now(),
        "finished_at": _now(),
        "summary": summary,
        "records": graded_records,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=2)
    print(f"[run_grading] wrote {out}")

    print("\n=== domains/arc/real-eval :: run_grading summary ===")
    print(f"Tasks graded : {n}")
    print("Agent tiers  :", dict(by_tier_agent))
    print("Baseline tiers:", dict(by_tier_baseline))
    print(f"Tier-1 (agent)  : {summary['tier1_rate_agent']:6.2%}")
    print(f"Tier-2 (agent)  : {summary['tier2_rate_agent']:6.2%}")
    print(f"Tier-3 (agent)  : {summary['tier3_rate_agent']:6.2%}")
    print(f"Tier-1 (baseline): {summary['tier1_rate_baseline']:6.2%}")
    print(f"Avg lift over baseline: {summary['avg_lift_over_baseline']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())