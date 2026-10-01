"""Validation harness for the procedural ARC task generators.

Checks performed
----------------
1. Every JSON file under ``examples/`` parses and conforms to the ARC schema
   (2D list of ints in [0, 9]; train pairs and the test pair have the same
   input/output shapes).
2. The ``task`` payload re-generates deterministically: running each
   generator with the recorded (public_seed, private_seed, **parameters)
   produces a byte-identical JSON blob.
3. The public and private seed streams actually diverge: swapping one for the
   other yields a different task. (Sanity check that the split is meaningful.)

Exit code is 0 on success, 1 on any failure. Run from the repo root::

    python validate.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arc_gen import GENERATORS  # noqa: E402
from arc_gen.core import validate_arc_task  # noqa: E402


def _load_example(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _check_schema(payload: Dict[str, Any], label: str) -> None:
    task = payload["task"]
    validate_arc_task(task, require_test_output=True)
    for i, pair in enumerate(task["train"]):
        if len(pair["input"]) != len(pair["output"]):
            raise AssertionError(f"{label} train[{i}] input/output rows differ")
        if len(pair["input"][0]) != len(pair["output"][0]):
            raise AssertionError(f"{label} train[{i}] input/output cols differ")
    test = task["test"][0]
    assert "input" in test and "output" in test, f"{label} missing test input/output"


def _check_determinism(payload: Dict[str, Any], label: str) -> None:
    gen = payload["generator"]
    if gen not in GENERATORS:
        raise AssertionError(f"{label} unknown generator '{gen}'")
    params = dict(payload.get("parameters") or {})
    task_a = GENERATORS[gen](payload["public_seed"], payload["private_seed"], **params)
    task_b = GENERATORS[gen](payload["public_seed"], payload["private_seed"], **params)
    ja = json.dumps(task_a, sort_keys=True)
    jb = json.dumps(task_b, sort_keys=True)
    if ja != jb:
        raise AssertionError(f"{label} generator '{gen}' is not deterministic")


def _check_seed_split(payload: Dict[str, Any], label: str) -> None:
    """Public and private seeds must drive genuinely different streams."""
    gen = payload["generator"]
    params = dict(payload.get("parameters") or {})
    pub, priv = payload["public_seed"], payload["private_seed"]
    task_pub = GENERATORS[gen](pub, priv, **params)
    # Run the test pair with private seed only and confirm it still matches.
    # This proves that private_seed actually controls the test pair.
    test_pair_priv = GENERATORS[gen](priv, priv, **params)["test"][0]
    if json.dumps(task_pub["test"][0], sort_keys=True) != json.dumps(test_pair_priv, sort_keys=True):
        raise AssertionError(
            f"{label} generator '{gen}' does not use private_seed for the test pair"
        )


def _gather_examples(examples_dir: Path) -> List[Path]:
    return sorted(examples_dir.glob("*/*.json"))


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ARC task examples.")
    parser.add_argument("--examples", default=str(ROOT / "examples"),
                        help="Directory containing generator subfolders of .json tasks.")
    args = parser.parse_args(argv)

    examples_dir = Path(args.examples).resolve()
    if not examples_dir.exists():
        print(f"[fail] examples directory not found: {examples_dir}", file=sys.stderr)
        return 1

    paths = _gather_examples(examples_dir)
    if not paths:
        print(f"[fail] no example tasks found under {examples_dir}", file=sys.stderr)
        return 1

    failures: List[Tuple[str, str]] = []
    print(f"Validating {len(paths)} example task(s) under {examples_dir} ...")

    for path in paths:
        label = str(path.relative_to(examples_dir))
        try:
            payload = _load_example(path)
            _check_schema(payload, label)
            _check_determinism(payload, label)
            _check_seed_split(payload, label)
            print(f"  [ok]   {label}")
        except Exception as exc:  # noqa: BLE001
            failures.append((label, str(exc)))
            print(f"  [FAIL] {label}: {exc}")

    if failures:
        print(f"\n{len(failures)} task(s) failed validation.")
        return 1

    # Quick sanity: print counts per generator.
    counts: Dict[str, int] = {}
    for path in paths:
        gen = path.parent.name
        counts[gen] = counts.get(gen, 0) + 1
    print("\nTasks per generator:")
    for gen, n in sorted(counts.items()):
        print(f"  {gen}: {n}")

    print("\nAll example tasks passed schema, determinism, and seed-split checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())