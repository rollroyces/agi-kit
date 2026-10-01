"""Run the PSF-CLAgent MVP on every example task and emit a results log.

Two passes:

* **fresh pass** — every task gets a brand-new procedural memory. Measures
  per-task solve rate without cross-task transfer.
* **cumulative pass** — one shared procedural memory across all 16 tasks.
  Measures whether the agent's lift heuristic actually transfers knowledge.

A "tier-1" solve = the agent's prediction matches the test output exactly.
A "tier-2" solve = the prediction is palette-equivalent to the test output
(SPEC §8.2 invariance ``pal``). The MVP reports both rates; the headline
"tier-1 solve rate" is the bar for the acceptance criteria.

The driver also runs a *raw LLM guess* baseline that returns the test input
unchanged (a worst-case tier-0 reference). This anchors the comparison.

Usage::

    python run_mvp.py                          # default: template reasoner
    python run_mvp.py --reasoner template      # explicit
    python run_mvp.py --reasoner llm            # LLM-backed (needs OPENAI_API_KEY)
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "standard"))

from agent import CLAgent, SolveConfig, MemoryFacade  # noqa: E402
from agent.memory import ProceduralMemory  # noqa: E402
from reference.airt import InMemoryStore, ToolBridge  # noqa: E402


EXAMPLES = _REPO / "domains" / "arc" / "generators" / "examples"
FAMILIES = ["fill_enclosed", "rotate_largest", "count_colors", "symmetry_complete"]
OUTPUT_DIR = _ROOT / "outputs"


def _now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def _palette_invariant_match(pred: Any, target: Any) -> bool:
    """True iff there's a bijection over colours that maps ``pred`` → ``target``.

    Bijection is constrained to identity-on-bg (the most common colour stays).
    """
    if _shape(pred) != _shape(target):
        return False
    h, w = _shape(pred)
    # Find bg of target (most common).
    from collections import Counter
    bg_target = Counter(v for row in target for v in row).most_common(1)[0][0]
    bg_pred = Counter(v for row in pred for v in row).most_common(1)[0][0]
    # Build a colour mapping (pred_colour -> target_colour) cell-by-cell.
    mapping: Dict[int, int] = {}
    for r in range(h):
        for c in range(w):
            p = pred[r][c]
            t = target[r][c]
            if p in mapping:
                if mapping[p] != t:
                    return False
            else:
                mapping[p] = t
    # Ensure bijection (mapping is injective — already enforced above; also check surjectivity).
    if len(set(mapping.values())) != len(mapping):
        return False
    return True


def _shape(g):
    return (len(g), len(g[0]) if g else 0)


def _tier1(pred: Any, target: Any) -> bool:
    return pred == target


def _tier2(pred: Any, target: Any) -> bool:
    return _palette_invariant_match(pred, target)


def _tier3(pred: Any, target: Any) -> bool:
    """Structural match per SPEC §8.1 tier 3."""
    if _shape(pred) != _shape(target):
        return False
    h, w = _shape(pred)
    cells_match = sum(1 for r in range(h) for c in range(w)
                       if pred[r][c] == target[r][c])
    return cells_match / max(1, h * w) >= 0.6


def _baseline_guess(task: dict) -> Any:
    """Tier-0 baseline: echo the test input."""
    return copy.deepcopy(task["task"]["test"][0]["input"])


def _load_examples() -> List[Tuple[str, int, dict]]:
    out: List[Tuple[str, int, dict]] = []
    for fam in FAMILIES:
        for i in range(1, 5):
            path = EXAMPLES / fam / f"task_{i:02d}.json"
            if not path.exists():
                continue
            with open(path, encoding="utf-8") as fh:
                out.append((fam, i, json.load(fh)))
    return out


def _evaluate_agent(agent: CLAgent, tasks: List[Tuple[str, int, dict]],
                    memory: Any) -> List[Dict[str, Any]]:
    """Run the agent on each task; return a per-task results list."""
    tools = ToolBridge()
    results: List[Dict[str, Any]] = []
    for fam, idx, task in tasks:
        started = time.time()
        ans = agent.solve(task, memory, tools)
        elapsed = time.time() - started
        target = task["task"]["test"][0]["output"]
        pred = ans.test_predictions[0]
        tier1 = _tier1(pred, target)
        tier2 = _tier1(pred, target) or _tier2(pred, target)
        tier3 = tier2 or _tier3(pred, target)
        results.append({
            "family": fam,
            "task_idx": idx,
            "tier1": tier1,
            "tier2": tier2,
            "tier3": tier3,
            "attempts": ans.trace["attempts"],
            "confidence": ans.trace["confidence"],
            "audit_flagged": ans.trace["audit_flagged"],
            "committed_program": ans.trace["committed_program"],
            "elapsed_s": round(elapsed, 3),
            "memory_size_before": len(memory._procedural) if hasattr(memory, "_procedural") else None,
            "reasoner_used": ans.trace.get("reasoner_used", "template"),
            "reasoner_fallback": bool(ans.trace.get("reasoner_fallback", False)),
        })
    return results


def _evaluate_baseline(tasks: List[Tuple[str, int, dict]]) -> List[Dict[str, Any]]:
    """Tier-0 baseline: return the test input unchanged; compare against test OUTPUT."""
    results: List[Dict[str, Any]] = []
    for fam, idx, task in tasks:
        target = task["task"]["test"][0]["output"]   # correct ground truth
        pred = _baseline_guess(task)
        results.append({
            "family": fam,
            "task_idx": idx,
            "tier1": _tier1(pred, target),
            "tier2": _tier1(pred, target) or _tier2(pred, target),
            "tier3": _tier1(pred, target) or _tier3(pred, target),
            "attempts": 1,
            "confidence": 0.0,
            "audit_flagged": False,
            "committed_program": "baseline_echo",
            "elapsed_s": 0.0,
            "memory_size_before": None,
        })
    return results


def _summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_family: Dict[str, Dict[str, int]] = {}
    total_attempts = 0
    total_solved = 0
    for r in results:
        fam = r["family"]
        bucket = by_family.setdefault(fam, {
            "n": 0, "tier1": 0, "tier2": 0, "tier3": 0, "attempts_sum": 0,
        })
        bucket["n"] += 1
        if r["tier1"]:
            bucket["tier1"] += 1
            total_solved += 1
        if r["tier2"]:
            bucket["tier2"] += 1
        if r["tier3"]:
            bucket["tier3"] += 1
        bucket["attempts_sum"] += r["attempts"]
        total_attempts += r["attempts"]
    n_tasks = sum(b["n"] for b in by_family.values())
    return {
        "n_tasks": n_tasks,
        "tier1_solves": total_solved,
        "tier1_rate": total_solved / max(1, n_tasks),
        "avg_attempts_per_solve": total_attempts / max(1, total_solved) if total_solved else 0,
        "by_family": by_family,
    }


def _print_table(name: str, summary: Dict[str, Any]) -> None:
    print(f"\n=== {name} ===")
    print(f"{'family':20s}  n  tier1  tier2  tier3  avg_attempts")
    for fam, b in summary["by_family"].items():
        avg = b["attempts_sum"] / max(1, b["tier1"])
        print(f"{fam:20s}  {b['n']:2d}  {b['tier1']:5d}  {b['tier2']:5d}  {b['tier3']:5d}  {avg:6.2f}")
    print(f"{'TOTAL':20s}  {summary['n_tasks']:2d}  {summary['tier1_solves']:5d}  "
          f"rate={summary['tier1_rate']:.2%}")


def _main():
    parser = argparse.ArgumentParser(description="Run PSF-CLAgent MVP.")
    parser.add_argument(
        "--reasoner",
        choices=["template", "llm"],
        default="template",
        help="Which reasoner to use (default: template). 'llm' falls back to "
             "template automatically when OPENAI_API_KEY is unset.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    tasks = _load_examples()
    log: Dict[str, Any] = {
        "schema_version": "0.1.0",
        "started_at": _now(),
        "finished_at": None,
        "families": FAMILIES,
        "n_tasks": len(tasks),
        "reasoner_requested": args.reasoner,
    }

    cfg = SolveConfig(reasoner_type=args.reasoner)

    # Pass 1: fresh procedural memory per task (no transfer).
    print(f"Running agent on all tasks with FRESH procedural memory per task "
          f"(reasoner={args.reasoner}) ...")
    fresh_results: List[Dict[str, Any]] = []
    for fam, idx, task in tasks:
        agent = CLAgent(cfg)
        mem = MemoryFacade()
        rlist = _evaluate_agent(agent, [(fam, idx, task)], mem)
        fresh_results.extend(rlist)
        solved = "+" if rlist[0]["tier1"] else ("~" if rlist[0]["tier2"] else "-")
        print(f"  {fam}/task_{idx:02d}: tier1={solved}  "
              f"attempts={rlist[0]['attempts']:3d}  "
              f"audit={'F' if rlist[0]['audit_flagged'] else 'P'}  "
              f"prog={rlist[0]['committed_program']}")
    fresh_summary = _summarize(fresh_results)

    # Pass 2: cumulative procedural memory across tasks.
    print("\nRunning agent on all tasks with CUMULATIVE procedural memory ...")
    cumulative_mem = MemoryFacade()
    cumulative_results: List[Dict[str, Any]] = []
    for fam, idx, task in tasks:
        agent = CLAgent(cfg)
        # Snapshot the procedural memory size before this solve.
        before = len(cumulative_mem._procedural)
        rlist = _evaluate_agent(agent, [(fam, idx, task)], cumulative_mem)
        rlist[0]["memory_size_before"] = before
        rlist[0]["memory_size_after"] = len(cumulative_mem._procedural)
        cumulative_results.extend(rlist)
        solved = "+" if rlist[0]["tier1"] else ("~" if rlist[0]["tier2"] else "-")
        print(f"  {fam}/task_{idx:02d}: tier1={solved}  "
              f"attempts={rlist[0]['attempts']:3d}  "
              f"mem: {before} -> {len(cumulative_mem._procedural)}  "
              f"prog={rlist[0]['committed_program']}")
    cumulative_summary = _summarize(cumulative_results)

    # Baseline
    print("\nRunning baseline (raw input echo) ...")
    baseline_results = _evaluate_baseline(tasks)
    baseline_summary = _summarize(baseline_results)

    log["fresh_pass"] = {
        "per_task": fresh_results,
        "summary": fresh_summary,
    }
    log["cumulative_pass"] = {
        "per_task": cumulative_results,
        "summary": cumulative_summary,
        "final_procedural_size": len(cumulative_mem._procedural),
        "lifted_subroutine_count":
            sum(1 for n, _ in cumulative_mem._procedural.list_all() if n.startswith("auto_lift_")),
    }
    log["baseline"] = {
        "per_task": baseline_results,
        "summary": baseline_summary,
    }
    log["finished_at"] = _now()

    log_path = OUTPUT_DIR / "solve_log.json"
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote log to {log_path}")

    _print_table("Agent — fresh memory", fresh_summary)
    _print_table("Agent — cumulative memory", cumulative_summary)
    _print_table("Baseline (raw input echo)", baseline_summary)

    # Acceptance summary
    print("\n=== Acceptance summary ===")
    print(f"  Tier-1 solve rate (fresh)   : {fresh_summary['tier1_rate']:.2%}  "
          f"({fresh_summary['tier1_solves']}/{fresh_summary['n_tasks']})")
    print(f"  Tier-1 solve rate (cumul.)  : {cumulative_summary['tier1_rate']:.2%}  "
          f"({cumulative_summary['tier1_solves']}/{cumulative_summary['n_tasks']})")
    print(f"  Final procedural size       : {len(cumulative_mem._procedural)}")
    print(f"  Lifted subroutines          : "
          f"{log['cumulative_pass']['lifted_subroutine_count']}")


if __name__ == "__main__":
    _main()