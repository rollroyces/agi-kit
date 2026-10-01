# Math Word-Problem Domain (agi-kit)

Second task family of `agi-kit`. Where the ARC domain tests *spatial*
abstraction over grids, this one tests *numeric* abstraction over plain
strings: each task is a word problem whose answer is an integer.

## Layout

```
domains/math/
├── README.md                # this file
├── run_eval.py              # driver: loads examples, runs audit + grading
├── generators/
│   ├── __init__.py          # registry + generate_task()
│   ├── core.py              # RNG, validator, unit-conversion tables
│   ├── arithmetic_word_problems.py
│   ├── multi_step_arithmetic.py
│   └── unit_conversion.py
├── examples/
│   ├── arithmetic_word_problems/task_01..04.json
│   ├── multi_step_arithmetic/task_01..04.json
│   └── unit_conversion/task_01..04.json
├── audit/
│   ├── __init__.py
│   ├── heuristics.py        # echo_first_number, return_zero, …
│   ├── audit.py             # harness analogous to domains/arc/audit/audit.py
│   └── test_math_audit.py
├── grading/
│   ├── __init__.py
│   ├── grade.py             # four-tier grader (tier1..tier3 + tier0)
│   └── test_math_grading.py
├── tests/
│   └── test_math_dsl.py     # domain-level DSL primitive tests
└── outputs/
    └── eval_log.json        # written by run_eval.py
```

## Task shape

A math task is the same A3S envelope as an ARC task, but the inner
`input`/`output` values are **strings** instead of grids:

```json
{
  "generator": "arithmetic_word_problems",
  "public_seed": "demo-…",
  "private_seed": "priv-…",
  "parameters": { "operation": "add" },
  "task": {
    "train": [
      { "input": "If you have 9 stickers and 98 more are added, …", "output": "107" }
    ],
    "test": [
      { "input": "If you have 16 books and 55 more are added, …", "output": "71" }
    ]
  }
}
```

The `audit/audit.py` harness accepts both this envelope shape and the inner
body shape (`{"train": ..., "test": ...}`).

## Generators

Every generator exposes the same signature as the ARC ones:

```python
generate(public_seed, private_seed, **params) -> dict
```

| Generator                       | Family                                                  |
|---------------------------------|---------------------------------------------------------|
| `arithmetic_word_problems`      | One-step add / sub / divide worded as a story problem. |
| `multi_step_arithmetic`         | Three-step `+ - *` chain phrased as “start with N…”.    |
| `unit_conversion`               | m↔cm, kg↔g, h↔min with operand values that yield ints.  |

All generators are byte-deterministic given `(public_seed, private_seed, **params)`.

## Math-specific DSL primitives (in `agent/dsl/math_primitives.py`)

| Primitive         | Signature                       | Purpose                              |
|-------------------|---------------------------------|--------------------------------------|
| `parse_number`    | `(text: str) -> float`          | first integer / float in free text   |
| `safe_eval`       | `(expr: str) -> float`          | AST-restricted arithmetic evaluation |
| `extract_template`| `(text: str) -> str`            | `{slot}` → slot name replacement     |

Registered in `agent/dsl/registry.py` and added to the `_ARITY` table in
`agent/dsl/typechecker.py` (arity 1 for all three).

## Audit heuristics

Five shallow baselines live in `audit/heuristics.py`:

* `echo_first_number` – first integer in the input.
* `return_zero` – constant 0.
* `return_max` – largest integer in the input.
* `return_count` – count of integer tokens in the input.
* `random_guess` – deterministic random integer in [0, 100] (seed = input).

Plus `identity_echo` for sanity. A task is flagged as
`trivially_solvable` if any heuristic returns the exact ground-truth string.

## Grading

`grading/grade.py` defines four tiers:

* `tier1` – exact string match (`weight=1.0`).
* `tier2` – both parse as numbers and `|pred − truth| ≤ tolerance` (`0.7`).
* `tier3` – same magnitude within a factor of 10 (`0.3`).
* `tier0` – no match (`0.0`).

The weights match the ARC grader so cross-domain aggregate scores are
directly comparable. `grade_task(task, predictions)` mirrors the ARC
grader’s contract for cross-domain parity.

## Run the bundled eval

```bash
cd domains/math
python run_eval.py
```

This:

1. Loads all 12 example tasks.
2. Runs the audit on each.
3. Scores the `echo_first_number` and `identity_echo` baselines.
4. Writes `outputs/eval_log.json` with per-task results.
5. Prints a summary table.

## Tests

```bash
cd domains/math
python -m unittest discover -s tests            # ≥ 5 math-DSL tests
python -m unittest discover -s audit             # ≥ 8 audit tests
python -m unittest discover -s grading           # ≥ 8 grading tests
```

The agent-level DSL tests live in `agent/tests/test_math_dsl.py` so the
DSL additions can be exercised from the agent test suite as well.
