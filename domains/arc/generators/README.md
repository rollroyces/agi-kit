# Procedural ARC Task Generator

A small Python framework that emits an unlimited supply of novel ARC-format
tasks from parametric generators. Used by the agi-kit project to side-step
public-task contamination: every task is derived from a seed, and the
demonstration pairs and the held-out test pair are driven by **separate
seeds**, so an evaluator can keep the private seed secret.

---

## What's in here

```
domains/arc/generators/
├── arc_gen/                  # shared core library
│   ├── __init__.py
│   ├── core.py               # grid helpers, RNG, ARC schema validation
│   └── registry.py           # name -> generator dispatch
├── generators/               # one module per parametric task family
│   ├── __init__.py
│   ├── fill_enclosed.py      # fill enclosed regions with a new colour
│   ├── rotate_largest.py     # rotate the largest non-background object
│   ├── count_colors.py       # count distinct colours and stamp markers
│   └── symmetry_complete.py  # mirror one half of a pattern across an axis
├── examples/                 # saved example tasks
│   ├── count_colors/         #   4 tasks per generator, as JSON
│   ├── fill_enclosed/
│   ├── rotate_largest/
│   └── symmetry_complete/
├── generate_examples.py      # regenerate the example/ tree
├── validate.py               # schema, determinism, seed-split harness
└── README.md                 # this file
```

---

## The four generators

| name                | transformation rule                                                       |
| ------------------- | ------------------------------------------------------------------------- |
| `fill_enclosed`     | Find every enclosed background region (a hole inside a closed border) and fill it with a new colour. |
| `rotate_largest`    | Of 2-4 small coloured objects on a background, rotate the largest (by cell count) 90° clockwise in place. Other objects are untouched. |
| `count_colors`      | Count the distinct non-background colours in the input. The output is identical in shape but every cell is reset to background except the bottom row, which contains exactly that many marker cells (colour 8). |
| `symmetry_complete` | Mirror the populated half of the grid across a vertical or horizontal axis. |

Each generator exposes the same signature:

```python
def generate(public_seed, private_seed, **params) -> dict:
    """Return a full ARC task: {"train": [...], "test": [...]}."""
```

The task object conforms to the standard ARC schema: each pair has an
`input` and an `output`, both 2D lists of ints in `[0, 9]`, and the input
and output of every pair share the same shape.

---

## Quick start

```bash
# Regenerate the example/ tree (4 tasks per generator by default).
python generate_examples.py

# Re-validate everything that was just written.
python validate.py
```

To use a generator directly from your own code:

```python
from arc_gen import generate_task

task = generate_task(
    "rotate_largest",
    public_seed="demo-rot-A",
    private_seed="test-rot-42",
    n_objects=3,
    grid_size=(12, 12),
)

print(task["train"][0]["input"])
print(task["train"][0]["output"])
print(task["test"][0])
```

---

## Public/private seed split

ARC contamination is a serious risk: once a public task enters an LLM
training corpus, that task is no longer a fair test. Procedural generation
fixes this by **never publishing the test pair ahead of time**:

* `public_seed` controls **every demonstration pair** (the train list). These
  can be released freely.
* `private_seed` controls **only the test pair**. This seed is held back by
  the evaluator.

Crucially, the two streams must not leak. In this framework every pair is
generated from a single per-pair seed:

```
train[0]  ←  f"{public_seed}-0"
train[1]  ←  f"{public_seed}-1"
...
test[0]   ←  private_seed
```

No pair-level parameter (grid size, palette, geometry, …) is derived from
`public_seed` outside the train pairs themselves. `validate.py` enforces
this: it re-generates the task using `(private_seed, private_seed)` and
asserts that the test pair is byte-identical to the original.

---

## Determinism

All randomness comes from `arc_gen.core.make_rng`, which builds a
`random.Random` instance seeded with `combined_seed(...)`. The combinator
hashes the seed parts with a stable 64-bit FNV-style mix, so the same
inputs always produce the same sequence — across processes, platforms, and
Python versions. This is verified by `validate.py` (see "What validate.py
checks" below).

---

## How to add a new generator

1. **Pick a transformation rule.** It must be a well-defined mapping from
   input grid to output grid that an ARC solver could plausibly learn from
   a handful of demo pairs. Avoid open-ended tasks (free-form drawing,
   arithmetic on cell values) — those are very hard for current solvers
   and make bad benchmarks.

2. **Make it parametric.** Decide which dimensions vary: number of
   objects, grid size, palette, axis, density, rotation angle, etc. Each
   dimension should be controllable through a `**kwargs` parameter so the
   generator can be sampled at many difficulty levels.

3. **Keep `public_seed` and `private_seed` independent.** Inside the
   generator, derive the test pair purely from `private_seed` and the
   train pairs purely from `public_seed`. Anything shared between the two
   streams is a contamination risk.

4. **Create a module under `generators/`** with this signature:

   ```python
   # generators/my_task.py
   from arc_gen.core import make_rng, combined_seed, validate_arc_task

   def _build_pair(seed, params):
       rng = make_rng(combined_seed("my_task", seed, params))
       # ... build input_grid, output_grid ...
       return {"input": input_grid, "output": output_grid}

   def generate(public_seed, private_seed, **params):
       n_train = int(params.get("n_train", 3))
       train = [_build_pair(f"{public_seed}-{i}", params) for i in range(n_train)]
       test = [_build_pair(private_seed, params)]
       task = {"train": train, "test": test}
       validate_arc_task(task, require_test_output=True)
       return task
   ```

5. **Register it** in `generators/__init__.py` and `arc_gen/registry.py`
   (the `GENERATORS` dict).

6. **Add a few example parameter combos** in
   `domains/arc/generators/generate_examples.py::_examples_per_generator` so
   the example tree exercises your generator.

7. **Run `python validate.py`**. It will catch any schema, determinism,
   or seed-split problems immediately.

---

## What `validate.py` checks

For every JSON file under `examples/`:

* **Schema** — `validate_arc_task` enforces the ARC contract (2D list of
  ints in `[0, 9]`; train and test pairs both have matching input/output
  shapes; all required keys are present).
* **Determinism** — re-running the generator with the recorded
  `(public_seed, private_seed, **parameters)` produces a byte-identical
  JSON payload (compared as canonicalised JSON).
* **Seed split** — the test pair generated under `(public, private)` is
  identical to the test pair generated under `(private, private)`. This
  proves `private_seed` actually controls the test pair and there is no
  accidental leakage from `public_seed`.

Exit code is 0 if everything passes.

---

## ARC JSON format

Each saved file under `examples/` looks like:

```json
{
  "generator": "rotate_largest",
  "public_seed": "demo-rot-1",
  "private_seed": "test-rot-1",
  "parameters": {"n_objects": 2},
  "task": {
    "train": [
      {"input": [[...]], "output": [[...]]},
      {"input": [[...]], "output": [[...]]}
    ],
    "test": [
      {"input": [[...]], "output": [[...]]}
    ]
  }
}
```

The `task` field is what an ARC solver consumes. The other top-level
fields are metadata so a downstream evaluator can re-derive the task from
seeds if needed.

---

## Known limitations / suggested extensions

* **Pattern library in `rotate_largest` is small** (4 patterns: 2-, 3-,
  4-, and 5-cell asymmetric shapes in a 3×3 bbox). Add more 3×3 patterns
  with distinct cell counts to widen variety, or extend the pattern
  schema to allow 4×4 / 5×5 bboxes.
* **Colour palette in `count_colors` is constrained** to one cell per
  colour. The task is intentionally simple so current solvers can solve
  it; for harder variants, place each colour as a 2-3 cell cluster.
* **`fill_enclosed` only draws rectangular frames.** Non-rectangular
  closed shapes (circles, blobs) would make the task much harder.
* **`symmetry_complete` always uses density ~0.45.** A controllable
  density (already exposed in the API) lets an evaluator tune difficulty.
* **No automatic difficulty scoring.** Future work could compute a
  per-task difficulty estimate from the generated geometry (e.g. number
  of cells, dispersion, palette entropy) and route tasks to difficulty
  bins.
* **No automatic deduplication** across seeds. If two seeds happen to
  produce nearly-identical tasks (rare, but possible), a downstream
  evaluator should still catch this with a similarity check.