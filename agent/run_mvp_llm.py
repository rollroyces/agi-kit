"""Compare the template reasoner vs the LLM reasoner on all 16 example tasks.

Three modes:

1. **template** — the default reasoner. Always run.
2. **llm (no key)** — runs when ``OPENAI_API_KEY`` is unset; immediately
   falls back to template. This is the *baseline* for the LLM path.
3. **llm (key set)** — runs when ``OPENAI_API_KEY`` is present. If the
   key is invalid or the network is down, the driver catches the
   per-task :exc:`LLMUnavailable` and records a fallback for that task.

Output:

* ``outputs/compare_template_vs_llm.json`` — full per-task results.
* A side-by-side comparison table printed to stdout.

Usage::

    python run_mvp_llm.py
    OPENAI_API_KEY=sk-... python run_mvp_llm.py
"""
from __future__ import annotations

import argparse
import copy
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
from agent.reasoner import LLMClient  # noqa: E402
from reference.airt import ToolBridge  # noqa: E402


EXAMPLES = _REPO / "domains" / "arc" / "generators" / "examples"
FAMILIES = ["fill_enclosed", "rotate_largest", "count_colors", "symmetry_complete"]
OUTPUT_DIR = _ROOT / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "compare_template_vs_llm.json"


# ---------------------------------------------------------------------------
# Tier helpers (mirror run_mvp.py)
# ---------------------------------------------------------------------------

def _shape(g):
    return (len(g), len(g[0]) if g else 0)


def _palette_invariant_match(pred: Any, target: Any) -> bool:
    if _shape(pred) != _shape(target):
        return False
    h, w = _shape(pred)
    from collections import Counter
    bg_target = Counter(v for row in target for v in row).most_common(1)[0][0]
    bg_pred = Counter(v for row in pred for v in row).most_common(1)[0][0]
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
    if len(set(mapping.values())) != len(mapping):
        return False
    return True


def _tier1(pred, target) -> bool:
    return pred == target


def _tier2(pred, target) -> bool:
    return _palette_invariant_match(pred, target)


def _tier3(pred, target) -> bool:
    if _shape(pred) != _shape(target):
        return False
    h, w = _shape(pred)
    cells_match = sum(1 for r in range(h) for c in range(w)
                      if pred[r][c] == target[r][c])
    return cells_match / max(1, h * w) >= 0.6


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


# ---------------------------------------------------------------------------
# Per-mode evaluation
# ---------------------------------------------------------------------------

def _run_mode(reasoner_type: str, *, llm_client: LLMClient = None,
              label: str = "") -> Dict[str, Any]:
    """Run a single pass over the 16 tasks; return a result dict.

    Each task gets a fresh ``CLAgent`` so cross-task state is isolated
    (we compare like-for-like with the template regression).
    """
    tools = ToolBridge()
    cfg = SolveConfig(reasoner_type=reasoner_type, llm_client=llm_client)
    per_task: List[Dict[str, Any]] = []
    totals = {"tier1": 0, "tier2": 0, "tier3": 0,
              "attempts": 0, "wallclock": 0.0,
              "fallback_count": 0, "tokens_estimate": 0}

    for fam, idx, task in _load_examples():
        agent = CLAgent(cfg)
        mem = MemoryFacade()
        started = time.time()
        ans = agent.solve(task, mem, tools)
        elapsed = time.time() - started

        target = task["task"]["test"][0]["output"]
        pred = ans.test_predictions[0]
        tier1 = _tier1(pred, target)
        tier2 = tier1 or _tier2(pred, target)
        tier3 = tier2 or _tier3(pred, target)

        # If the agent actually used the LLM reasoner, pull prompt and
        # response sizes (best-effort token estimate = chars / 4).
        token_estimate = 0
        used = ans.trace.get("reasoner_used", "template")
        if used == "llm" and isinstance(agent.proposer, object):
            lp = getattr(agent.proposer, "last_prompt_chars", 0)
            lr = getattr(agent.proposer, "last_response_chars", 0)
            token_estimate = (lp + lr) // 4

        fallback = bool(ans.trace.get("reasoner_fallback", False))

        totals["tier1"] += int(tier1)
        totals["tier2"] += int(tier2)
        totals["tier3"] += int(tier3)
        totals["attempts"] += ans.trace["attempts"]
        totals["wallclock"] += elapsed
        totals["fallback_count"] += int(fallback)
        totals["tokens_estimate"] += token_estimate

        per_task.append({
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
            "reasoner_used": used,
            "reasoner_fallback": fallback,
            "tokens_estimate": token_estimate,
        })

    n = len(per_task)
    summary = {
        "label": label,
        "reasoner_type": reasoner_type,
        "n_tasks": n,
        "tier1_solves": totals["tier1"],
        "tier1_rate": totals["tier1"] / max(1, n),
        "tier2_solves": totals["tier2"],
        "tier3_solves": totals["tier3"],
        "total_attempts": totals["attempts"],
        "total_wallclock_s": round(totals["wallclock"], 3),
        "fallback_count": totals["fallback_count"],
        "tokens_estimate_total": totals["tokens_estimate"],
    }
    return {"summary": summary, "per_task": per_task}


# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

def _print_comparison(template: Dict[str, Any], llm: Dict[str, Any]) -> None:
    print("\n=== Side-by-side: template vs llm ===")
    header = f"{'metric':30s}  {'template':>16s}  {'llm':>16s}"
    print(header)
    print("-" * len(header))
    rows = [
        ("tier-1 solves", template["summary"]["tier1_solves"],
                          llm["summary"]["tier1_solves"]),
        ("tier-1 rate",   f"{template['summary']['tier1_rate']:.2%}",
                          f"{llm['summary']['tier1_rate']:.2%}"),
        ("tier-2 solves", template["summary"]["tier2_solves"],
                          llm["summary"]["tier2_solves"]),
        ("tier-3 solves", template["summary"]["tier3_solves"],
                          llm["summary"]["tier3_solves"]),
        ("total attempts", template["summary"]["total_attempts"],
                           llm["summary"]["total_attempts"]),
        ("fallback count", template["summary"]["fallback_count"],
                           llm["summary"]["fallback_count"]),
        ("wallclock (s)", round(template["summary"]["total_wallclock_s"], 2),
                           round(llm["summary"]["total_wallclock_s"], 2)),
        ("tokens estimate (llm)",
                           "-",
                           llm["summary"]["tokens_estimate_total"]),
    ]
    for name, t, l in rows:
        print(f"{name:30s}  {str(t):>16s}  {str(l):>16s}")

    # Per-family tier-1 breakdown.
    print("\nPer-family tier-1:")
    print(f"{'family':20s}  {'template':>10s}  {'llm':>10s}")
    by_fam_t: Dict[str, int] = {}
    by_fam_l: Dict[str, int] = {}
    n_by_fam: Dict[str, int] = {}
    for r in template["per_task"]:
        by_fam_t[r["family"]] = by_fam_t.get(r["family"], 0) + int(r["tier1"])
        n_by_fam[r["family"]] = n_by_fam.get(r["family"], 0) + 1
    for r in llm["per_task"]:
        by_fam_l[r["family"]] = by_fam_l.get(r["family"], 0) + int(r["tier1"])
    for fam in sorted(n_by_fam):
        n = n_by_fam[fam]
        print(f"{fam:20s}  {by_fam_t.get(fam, 0):>3d}/{n:<3d}    "
              f"  {by_fam_l.get(fam, 0):>3d}/{n:<3d}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _main():
    parser = argparse.ArgumentParser(description="Compare template vs LLM reasoner.")
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Skip the LLM-mode pass even if OPENAI_API_KEY is set.",
    )
    parser.add_argument(
        "--llm-base-url", default=None,
        help="Override OPENAI_BASE_URL (e.g. http://localhost:11434/v1).",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    tasks = _load_examples()
    has_key = bool(os.environ.get("OPENAI_API_KEY"))

    print(f"Loaded {len(tasks)} tasks across {len(FAMILIES)} families.")
    print(f"OPENAI_API_KEY is {'SET' if has_key else 'NOT SET'}.")

    # Pass 1 — template (always).
    print("\n[1/3] Running template reasoner ...")
    template_result = _run_mode("template", label="template")
    print(f"  template tier-1: {template_result['summary']['tier1_solves']}/"
          f"{template_result['summary']['n_tasks']} "
          f"({template_result['summary']['tier1_rate']:.2%})")

    # Pass 2 — LLM (always run; agent falls back if no key).
    if args.no_llm:
        print("\n[2/3] Skipping LLM pass (--no-llm).")
        llm_result = {"summary": {
            "label": "llm (skipped)", "reasoner_type": "llm",
            "n_tasks": 0, "tier1_solves": 0, "tier1_rate": 0.0,
            "tier2_solves": 0, "tier3_solves": 0,
            "total_attempts": 0, "total_wallclock_s": 0.0,
            "fallback_count": 0, "tokens_estimate_total": 0,
        }, "per_task": []}
    else:
        print("\n[2/3] Running LLM reasoner "
              f"({'with key' if has_key else 'without key - will fall back'}) ...")
        llm_client = None
        if has_key or args.llm_base_url:
            llm_client = LLMClient.from_env()
            if args.llm_base_url:
                llm_client.base_url = args.llm_base_url
        llm_result = _run_mode("llm", llm_client=llm_client, label="llm")
        s = llm_result["summary"]
        print(f"  llm tier-1: {s['tier1_solves']}/{s['n_tasks']} "
              f"({s['tier1_rate']:.2%})  "
              f"fallbacks={s['fallback_count']}  "
              f"tokens~{s['tokens_estimate_total']}")

    # Pass 3 — write outputs.
    log = {
        "schema_version": "0.1.0",
        "n_tasks": len(tasks),
        "openai_api_key_present": has_key,
        "template_pass": template_result,
        "llm_pass": llm_result,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {OUTPUT_FILE}")

    # Side-by-side table.
    _print_comparison(template_result, llm_result)

    # Acceptance summary.
    print("\n=== Acceptance summary ===")
    print(f"  template tier-1: {template_result['summary']['tier1_solves']}/16 "
          f"({template_result['summary']['tier1_rate']:.2%})")
    print(f"  llm     tier-1: {llm_result['summary']['tier1_solves']}/16 "
          f"({llm_result['summary']['tier1_rate']:.2%})")
    if not has_key:
        print("  (LLM ran without a key; agent fell back to template for every task.)")


if __name__ == "__main__":
    _main()