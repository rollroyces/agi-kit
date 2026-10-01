"""Generate the 12 bundled example tasks (4 per generator).

This script is idempotent — re-running it overwrites the existing
``task_NN.json`` files. The generator functions guarantee byte-determinism, so
the bundled examples are stable across re-runs.

Usage:
    python examples/_generate_examples.py
"""
from __future__ import annotations

import json
import os
import sys
from typing import Iterable

_HERE = os.path.dirname(os.path.abspath(__file__))
_MATH = os.path.dirname(_HERE)
sys.path.insert(0, _MATH)

from generators import GENERATORS  # noqa: E402

GENERATOR_PARAMS = {
    "arithmetic_word_problems": [
        {"min_operand": 2, "max_operand": 50, "operation": "add"},
        {"min_operand": 5, "max_operand": 30, "operation": "sub"},
        {"min_operand": 2, "max_operand": 12, "operation": "div"},
        {"min_operand": 10, "max_operand": 80, "operation": "add"},
    ],
    "multi_step_arithmetic": [
        {"min_operand": 2, "max_operand": 10},
        {"min_operand": 1, "max_operand": 6},
        {"min_operand": 3, "max_operand": 12},
        {"min_operand": 2, "max_operand": 8, "answer_max": 500},
    ],
    "unit_conversion": [
        {"family": "length"},
        {"family": "mass"},
        {"family": "time"},
        {"min_value": 1, "max_value": 50},
    ],
}


def _write(path: str, task: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(task, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main() -> int:
    for gen_name, params_list in GENERATOR_PARAMS.items():
        gen = GENERATORS[gen_name]
        target_dir = os.path.join(_HERE, gen_name)
        for i, params in enumerate(params_list, start=1):
            task = gen(f"demo-{gen_name}-{i}", f"priv-{gen_name}-{i}", **params)
            path = os.path.join(target_dir, f"task_{i:02d}.json")
            _write(path, task)
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
