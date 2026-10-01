"""Generate example ARC tasks and write them as JSON files.

Run from the repo root::

    python generate_examples.py

By default this produces 4 example tasks per generator and writes them to
``examples/<generator_name>/<n>.json``. Override with CLI flags; see
``--help``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Allow running this script from the repo root without installation.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arc_gen import GENERATORS  # noqa: E402


def _examples_per_generator(name: str) -> List[Dict[str, Any]]:
    """Pick a small, illustrative set of example parameter combos."""
    if name == "fill_enclosed":
        return [
            {"public_seed": "demo-fill-1", "private_seed": "test-fill-1", "n_shapes": 1},
            {"public_seed": "demo-fill-2", "private_seed": "test-fill-2", "n_shapes": 2, "grid_size": [10, 12]},
            {"public_seed": "demo-fill-3", "private_seed": "test-fill-3", "n_shapes": 3, "grid_size": [12, 14]},
            {"public_seed": "demo-fill-4", "private_seed": "test-fill-4", "n_shapes": 2, "grid_size": [9, 11]},
        ]
    if name == "rotate_largest":
        return [
            {"public_seed": "demo-rot-1", "private_seed": "test-rot-1", "n_objects": 2},
            {"public_seed": "demo-rot-2", "private_seed": "test-rot-2", "n_objects": 3},
            {"public_seed": "demo-rot-3", "private_seed": "test-rot-3", "n_objects": 4, "grid_size": [12, 12]},
            {"public_seed": "demo-rot-4", "private_seed": "test-rot-4", "n_objects": 3, "grid_size": [10, 14]},
        ]
    if name == "count_colors":
        return [
            {"public_seed": "demo-count-1", "private_seed": "test-count-1", "n_colors": 2},
            {"public_seed": "demo-count-2", "private_seed": "test-count-2", "n_colors": 3},
            {"public_seed": "demo-count-3", "private_seed": "test-count-3", "n_colors": 5, "grid_size": [7, 7]},
            {"public_seed": "demo-count-4", "private_seed": "test-count-4", "n_colors": 4},
        ]
    if name == "symmetry_complete":
        return [
            {"public_seed": "demo-sym-1", "private_seed": "test-sym-1", "axis": "vertical"},
            {"public_seed": "demo-sym-2", "private_seed": "test-sym-2", "axis": "horizontal"},
            {"public_seed": "demo-sym-3", "private_seed": "test-sym-3"},
            {"public_seed": "demo-sym-4", "private_seed": "test-sym-4", "density": 0.6},
        ]
    raise ValueError(f"No examples configured for generator '{name}'")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate example ARC tasks.")
    parser.add_argument("--out", default=str(ROOT / "examples"), help="Output directory.")
    parser.add_argument("--generator", action="append", default=None,
                        help="Restrict to specific generator name(s); may repeat.")
    parser.add_argument("--count", type=int, default=4,
                        help="Number of example tasks per generator.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    selected = args.generator or list(GENERATORS)
    summary: Dict[str, List[str]] = {}

    for name in selected:
        if name not in GENERATORS:
            print(f"[skip] Unknown generator '{name}'", file=sys.stderr)
            continue
        examples = _examples_per_generator(name)[: args.count]
        written: List[str] = []
        for idx, ex in enumerate(examples, start=1):
            public_seed = ex.pop("public_seed")
            private_seed = ex.pop("private_seed")
            task = GENERATORS[name](public_seed, private_seed, **ex)
            path = out_dir / name / f"task_{idx:02d}.json"
            payload = {
                "generator": name,
                "public_seed": public_seed,
                "private_seed": private_seed,
                "parameters": ex,
                "task": task,
            }
            _write_json(path, payload)
            written.append(str(path))
        summary[name] = written
        print(f"[ok] {name}: wrote {len(written)} example(s) -> {out_dir / name}")

    print("\nSummary:")
    for name, files in summary.items():
        for f in files:
            print(f"  {name}: {os.path.relpath(f, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())