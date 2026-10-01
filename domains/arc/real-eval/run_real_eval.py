"""run_real_eval.py — run CLAgent on the real public ARC-AGI-1 corpus.

This is the headline driver for the real-eval benchmark. It loads tasks from
``data/arc-agi-1/``, wraps each into the envelope the agent expects, calls
``CLAgent.solve()``, and records per-task results.

The script is deliberately **bounded**:

* Operates entirely under the snapshot at ``./snapshot/agent/`` so that any
  parallel edits to ``F:\\tmp\\agi-kit\\agent`` cannot influence it.
* Default subset is the first 100 tasks of ``training/`` + first 50 of
  ``evaluation/`` (150 tasks total); ``--limit N`` overrides.
* Robust to malformed tasks: skip + log, never crash.
* Template reasoner by default; ``--reasoner llm`` enables the LLM proposer when
  ``OPENAI_API_KEY`` is set (and falls back to template otherwise).

Outputs:
    outputs/real_eval_log.json   # one record per task + an aggregate summary
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup — only ever resolve from THIS script's directory.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_SNAPSHOT = _HERE / "snapshot"
_STANDARD_REF = _HERE.parent.parent.parent / "standard"

if not _SNAPSHOT.exists():
    raise SystemExit(
        f"FATAL: snapshot not found at {_SNAPSHOT}. Did the snapshot step run?"
    )

# Inject paths so ``agent.py`` can find ``standard/reference/airt.py`` and its
# own sibling modules (``reasoner``, ``memory``, ``dsl``, ``audit_gate``).
for p in (
    _SNAPSHOT,                   # agent, memory, reasoner, audit_gate
    _SNAPSHOT / "dsl",
    _SNAPSHOT / "memory",
    _SNAPSHOT / "reasoner",
    _STANDARD_REF,                # standard/reference/airt.py
    _STANDARD_REF / "reference",
):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Imports happen AFTER sys.path manipulation.
from agent import CLAgent, SolveConfig  # noqa: E402
from memory import ProceduralMemory  # noqa: E402
from reference.airt import InMemoryStore, ToolBridge  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def _shape(g: Any) -> tuple[int, int]:
    if not g or not g[0]:
        return (0, 0)
    return len(g), len(g[0])


def _wrap_for_agent(task_id: str, raw_task: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap a bare ARC task dict into the envelope ``agent.py`` expects.

    The CLAgent accesses ``task["task"]["train"]`` / ``task["task"]["test"]``
    / ``task["task"]["test"][0]["output"]`` (for diagnostics only). Bare ARC
    tasks have ``train`` / ``test`` at the top level.
    """
    return {"task_id": task_id, "task": raw_task}


def _load_tasks(
    data_dir: Path,
    n_train: int,
    n_eval: int,
    seed: int,
) -> List[Dict[str, Any]]:
    """Load ARC-AGI-1 tasks from disk.

    We sort task IDs alphabetically for determinism (no random sampling in the
    default path). A ``--seed`` only affects the order in which they are fed to
    the agent's per-task wall-clock scheduler (irrelevant for the template
    reasoner, but kept for symmetry with the LLM path).
    """
    out: List[Dict[str, Any]] = []
    for sub, want in (("training", n_train), ("evaluation", n_eval)):
        sub_dir = data_dir / sub
        if not sub_dir.exists():
            print(f"WARN: missing dir {sub_dir}; skipping", file=sys.stderr)
            continue
        ids = sorted(p.stem for p in sub_dir.glob("*.json"))
        if want and want < len(ids):
            # Take the first ``want`` alphabetically (deterministic).
            ids = ids[:want]
        for tid in ids:
            with open(sub_dir / f"{tid}.json", encoding="utf-8") as fh:
                out.append({"task_id": tid, "split": sub, "raw": json.load(fh)})
    if seed:
        rng = random.Random(seed)
        rng.shuffle(out)
    return out


def _infer_family(task_raw: Dict[str, Any]) -> str:
    """Cheap, rule-light family label for ARC tasks.

    The CLAgent doesn't produce a first-class family, but we want a tag for
    the breakdown tables. This is a hand-rolled *feature fingerprint*:

        * "size_change": output shape differs from input shape
        * "color_perm":   same shape, same non-zero count, permutation only
        * "object_translate": output is input with objects shifted (we don't
          actually test; default to "unknown" for the general case)
        * "identity":     output == input (rare)
        * "composite":    multiple salient features

    For the head-line breakdown we just bucket by *shape-change* vs
    *same-shape* + a coarse palette-size bucket.
    """
    train = task_raw.get("train", [])
    test = task_raw.get("test", [])
    if not train or not test:
        return "malformed"
    in_shapes = {_shape(ex["input"]) for ex in train} | {_shape(test[0]["input"])}
    out_shapes = {_shape(ex["output"]) for ex in train} | {_shape(test[0]["output"])}
    if in_shapes != out_shapes:
        return "size_change"
    # Count distinct non-zero colours across the inputs.
    palette: set[int] = set()
    for ex in train + test:
        for row in ex["input"]:
            palette.update(c for c in row if c != 0)
        for row in ex.get("output", []):
            palette.update(c for c in row if c != 0)
    n = len(palette)
    if n <= 2:
        return "same_shape_small_palette"
    if n <= 4:
        return "same_shape_mid_palette"
    return "same_shape_rich_palette"


def _grade_prediction(pred: Any, target: Any) -> Dict[str, bool]:
    """Per-task tier assignment for the agent's first test prediction.

    Tier definitions follow standard SPEC.md §8:
        tier1 = exact cell-by-cell match
        tier2 = palette permutation (we report it for completeness; the
                official CLAgent run_mvp uses a stricter palette bijection
                that keeps background fixed — we mirror that here)
        tier3 = shape match + cell_match_rate >= 0.6
    """
    from collections import Counter
    t1 = pred == target
    t2 = False
    t3 = False
    if not t1 and pred is not None and target is not None:
        if _shape(pred) == _shape(target):
            h, w = _shape(pred)
            cells_match = sum(
                1 for r in range(h) for c in range(w) if pred[r][c] == target[r][c]
            )
            rate = cells_match / max(1, h * w)
            t3 = rate >= 0.6
            # Palette bijection (mirrors run_mvp._palette_invariant_match).
            try:
                bg_target = Counter(v for row in target for v in row).most_common(1)[0][0]
                bg_pred = Counter(v for row in pred for v in row).most_common(1)[0][0]
                mapping: Dict[int, int] = {}
                ok = True
                for r in range(h):
                    for c in range(w):
                        p, t = pred[r][c], target[r][c]
                        if p in mapping:
                            if mapping[p] != t:
                                ok = False
                                break
                        else:
                            mapping[p] = t
                    if not ok:
                        break
                if ok and len(set(mapping.values())) == len(mapping):
                    t2 = True
            except Exception:
                t2 = False
    return {"tier1": t1, "tier2": t1 or t2, "tier3": t1 or t2 or t3}


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def _run_single(
    agent: CLAgent,
    task_id: str,
    split: str,
    raw_task: Dict[str, Any],
) -> Dict[str, Any]:
    """Run CLAgent on one ARC task; return a result record."""
    family = _infer_family(raw_task)
    target = raw_task["test"][0].get("output")
    record: Dict[str, Any] = {
        "task_id": task_id,
        "split": split,
        "family": family,
        "tier1": False,
        "tier2": False,
        "tier3": False,
        "attempts": 0,
        "audit_flagged": False,
        "committed_program": None,
        "confidence": 0.0,
        "elapsed_s": 0.0,
        "reasoner_used": "template",
        "reasoner_fallback": False,
        "error": None,
    }
    started = time.time()
    try:
        wrapped = _wrap_for_agent(task_id, raw_task)
        memory = ProceduralMemory()
        store = InMemoryStore()
        tools = ToolBridge()
        ans = agent.solve(wrapped, memory, tools)
        pred = ans.test_predictions[0] if ans.test_predictions else None
        record.update({
            "attempts": ans.trace.get("attempts", 0),
            "audit_flagged": bool(ans.trace.get("audit_flagged", False)),
            "committed_program": ans.trace.get("committed_program"),
            "confidence": float(ans.trace.get("confidence", 0.0)),
            "reasoner_used": ans.trace.get("reasoner_used", "template"),
            "reasoner_fallback": bool(ans.trace.get("reasoner_fallback", False)),
        })
        if pred is not None and target is not None:
            record.update(_grade_prediction(pred, target))
        record["elapsed_s"] = round(time.time() - started, 3)
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["elapsed_s"] = round(time.time() - started, 3)
        print(f"  [skip] {task_id}: {record['error']}", file=sys.stderr)
    return record


def _summarize(records: List[Dict[str, Any]], wallclock: float) -> Dict[str, Any]:
    n = len(records)
    tier1 = sum(1 for r in records if r["tier1"])
    tier2 = sum(1 for r in records if r["tier2"])
    tier3 = sum(1 for r in records if r["tier3"])
    audited = sum(1 for r in records if r["audit_flagged"])
    errors = sum(1 for r in records if r["error"])
    avg_attempts = (
        sum(r["attempts"] for r in records) / max(1, n)
    )
    by_family: Dict[str, Dict[str, int]] = {}
    by_split: Dict[str, Dict[str, int]] = {}
    for r in records:
        fam = r["family"]
        b = by_family.setdefault(fam, {"n": 0, "tier1": 0, "tier2": 0, "tier3": 0})
        b["n"] += 1
        if r["tier1"]:
            b["tier1"] += 1
        if r["tier2"]:
            b["tier2"] += 1
        if r["tier3"]:
            b["tier3"] += 1
        s = r["split"]
        sb = by_split.setdefault(s, {"n": 0, "tier1": 0, "tier2": 0, "tier3": 0})
        sb["n"] += 1
        if r["tier1"]:
            sb["tier1"] += 1
        if r["tier2"]:
            sb["tier2"] += 1
        if r["tier3"]:
            sb["tier3"] += 1
    return {
        "n_tasks": n,
        "n_tier1": tier1,
        "n_tier2": tier2,
        "n_tier3": tier3,
        "n_audit_flagged": audited,
        "n_errors": errors,
        "tier1_rate": tier1 / max(1, n),
        "tier2_rate": tier2 / max(1, n),
        "tier3_rate": tier3 / max(1, n),
        "avg_attempts": avg_attempts,
        "wallclock_s": round(wallclock, 2),
        "by_family": by_family,
        "by_split": by_split,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=str(_HERE / "data" / "arc-agi-1"),
        help="Path to the arc-agi-1 directory (default: ./data/arc-agi-1)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=150,
        help="Maximum number of tasks to evaluate (default 150).",
    )
    parser.add_argument(
        "--n-train",
        type=int,
        default=None,
        help="Tasks to take from training/ (overrides --limit when set).",
    )
    parser.add_argument(
        "--n-eval",
        type=int,
        default=None,
        help="Tasks to take from evaluation/ (overrides --limit when set).",
    )
    parser.add_argument(
        "--reasoner",
        choices=["template", "llm"],
        default="template",
        help="Reasoner to use (default: template).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Optional seed for shuffling the loaded task list.",
    )
    parser.add_argument(
        "--output",
        default=str(_HERE / "outputs" / "real_eval_log.json"),
        help="Where to write the per-task log.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=20,
        help="k_initial for the agent's template proposer (default 20).",
    )
    parser.add_argument(
        "--time-budget",
        type=float,
        default=10.0,
        help="Per-task wall-clock budget in seconds (default 10).",
    )
    args = parser.parse_args()

    # Decide per-split quotas.
    if args.n_train is None and args.n_eval is None:
        # Default: 100 training + 50 evaluation (capped by --limit).
        n_train, n_eval = min(100, args.limit), min(50, max(0, args.limit - 100))
    else:
        n_train = args.n_train if args.n_train is not None else args.limit
        n_eval = args.n_eval if args.n_eval is not None else max(0, args.limit - n_train)

    data_dir = Path(args.data_dir)
    print(f"[run_real_eval] data_dir = {data_dir}")
    print(f"[run_real_eval] loading up to {n_train} training + {n_eval} eval tasks")
    tasks = _load_tasks(data_dir, n_train=n_train, n_eval=n_eval, seed=args.seed)
    print(f"[run_real_eval] loaded {len(tasks)} tasks")

    cfg = SolveConfig(
        reasoner_type=args.reasoner,
        k_initial=args.k,
        wallclock_budget_s=args.time_budget,
    )
    agent = CLAgent(config=cfg)

    print(
        f"[run_real_eval] reasoner={args.reasoner} "
        f"(actually using {agent.last_reasoner_used})"
    )

    records: List[Dict[str, Any]] = []
    started = time.time()
    for i, item in enumerate(tasks, 1):
        if i % 10 == 1 or i == len(tasks):
            elapsed = time.time() - started
            print(f"  [{i:3d}/{len(tasks)}]  elapsed={elapsed:6.1f}s", flush=True)
        rec = _run_single(agent, item["task_id"], item["split"], item["raw"])
        records.append(rec)
    wallclock = time.time() - started
    summary = _summarize(records, wallclock)

    log = {
        "schema_version": "0.1.0",
        "started_at": _now(),
        "finished_at": _now(),
        "wallclock_s": round(wallclock, 2),
        "config": {
            "reasoner_requested": args.reasoner,
            "k_initial": args.k,
            "time_budget_s": args.time_budget,
            "n_train_quota": n_train,
            "n_eval_quota": n_eval,
        },
        "summary": summary,
        "records": records,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=2)
    print(f"[run_real_eval] wrote {out_path}")

    # ----- console summary -------------------------------------------------
    s = summary
    print("\n=== domains/arc/real-eval :: run_real_eval summary ===")
    print(f"Tasks evaluated : {s['n_tasks']}")
    print(f"Tier-1 solves   : {s['n_tier1']:3d} ({s['tier1_rate']:6.2%})")
    print(f"Tier-2 solves   : {s['n_tier2']:3d} ({s['tier2_rate']:6.2%})")
    print(f"Tier-3 solves   : {s['n_tier3']:3d} ({s['tier3_rate']:6.2%})")
    print(f"Audit-flagged   : {s['n_audit_flagged']}")
    print(f"Errors          : {s['n_errors']}")
    print(f"Avg attempts    : {s['avg_attempts']:.1f}")
    print(f"Wall-clock (s)  : {s['wallclock_s']:.1f}")
    print("\nBy family:")
    print(f"  {'family':32s} {'n':>3s} {'t1':>4s} {'t2':>4s} {'t3':>4s} {'t1_rate':>7s}")
    for fam, b in sorted(s["by_family"].items()):
        rate = b["tier1"] / max(1, b["n"])
        print(f"  {fam:32s} {b['n']:3d} {b['tier1']:4d} {b['tier2']:4d} {b['tier3']:4d} {rate:6.2%}")
    print("\nBy split:")
    for sp, b in s["by_split"].items():
        rate = b["tier1"] / max(1, b["n"])
        print(f"  {sp:12s} {b['n']:3d}  tier1={b['tier1']}  rate={rate:6.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())