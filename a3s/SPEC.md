# A3S — the ARC-AGI-3 Standard, Version 1.0.0

> **Status:** Stable. This document is normative for A3S v1.x.
> The keywords **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
> **SHOULD**, **SHOULD NOT**, **MAY** are to be interpreted as described in
> RFC 2119.

---

## Table of contents

1. Scope and goals
2. Versioning
3. Conformance levels
4. Task format
5. Generator API
6. Agent interface
7. Audit protocol
8. Scoring protocol
9. Reporting protocol
10. Submission bundle
11. Reference implementations
12. Examples
13. Future work (v2 outlook)

---

## §1 Scope and goals

A3S standardises the **interfaces** between four classes of component used to
evaluate progress on ARC-style abstract-reasoning tasks:

| Component | Produces | Consumes |
|-----------|----------|----------|
| Generator | An A3S task (§4) | A pair of seeds + parameters |
| Agent | An A3S answer (§6) | An A3S task + memory + tools |
| Audit | An audit verdict (§7) | An A3S task |
| Scoring + Reporting | A scoring report (§8–§9) | An A3S answer, A3S ground truth |

A3S **does not** standardise:

- The internal representation used by any single agent (it only standardises
  the inputs/outputs of `solve()`).
- The neural architecture, training loop, or hyperparameters of an agent.
- The leaderboard, hosted evaluation infrastructure, or web UI.
- The specifics of how an audit heuristic works — only that it conforms to
  the heuristic signature and registry contract.

**Who A3S is for:**

- **Task-family authors** who want their generators to inter-operate with
  any A3S-compliant evaluation harness.
- **Agent builders** who want plug-in compatibility with any A3S task set
  without rewriting adapters.
- **Benchmark curators** who need a contract for what counts as a
  "non-trivial" task and what counts as a "correct" solution.
- **Tool builders** (e.g., a new IRT variant, a new grader tier) who want
  to publish a drop-in alternative under the same protocol.

**Non-goals:** A3S is **not** a learning algorithm, a model specification, or
a data format for raw grids outside the ARC colour-and-shape convention.

---

## §2 Versioning

A3S follows [Semantic Versioning 2.0.0](https://semver.org/).

- **MAJOR** version increments (e.g., `v1.x.x` → `v2.0.0`) **MUST** only be
  used for breaking changes to the interfaces defined in §4–§10. A breaking
  change is one that causes a previously conforming artefact to fail a
  conformance test in the corresponding major version of `conformance/`.
- **MINOR** version increments **MAY** add new interfaces, new optional
  fields, or new invariance classes, provided existing conforming
  artefacts continue to pass conformance unchanged.
- **PATCH** version increments **MUST** be limited to documentation,
  clarification, or non-substantive refactors of the reference
  implementations.

The current document **freezes** seven interfaces:

1. The A3S task JSON shape (§4).
2. The generator function signature (§5).
3. The agent `solve()` signature and trace schema (§6).
4. The audit verdict schema and heuristic registry contract (§7).
5. The grader return schema and invariance class taxonomy (§8).
6. The report schema (§9).
7. The submission bundle directory layout (§10).

A change to any of these is a MAJOR event and **MUST** go through the RFC
process described in `VERSIONING.md`.

---

## §3 Conformance levels

A3S defines three conformance levels. Implementations **MUST** declare the
level they target.

### Core (minimum viable)

A Core A3S implementation **MUST**:

1. Read and write tasks in the JSON shape of §4.
2. Expose a `generate(public_seed, private_seed, **params) -> Task` callable
   that is byte-deterministic across runs on the same OS / Python version
   (§5).
3. Expose an audit function that runs ≥5 heuristics from the A3S registry
   and returns a verdict matching §7 (`pass` / `quarantine`).
4. Compute a tier-1 exact-match score for each (predicted, ground truth)
   pair, returning the schema of §8.
5. Emit a `report.json` containing at least: `task_score`, `n_tasks`,
   `invariances_used`, and `per_example_tiers`.

### Extended

An Extended A3S implementation **MUST** satisfy all Core requirements
**and**:

6. Implement the full hierarchical 3-tier grader (exact, equivalence,
   structural) per §8.
7. Maintain per-task invariance declarations and honour them when scoring.
8. Run the audit on every generated task before scoring it, and refuse to
   score a task whose audit verdict is `quarantine` (it must instead be
   reported as `audit_failed` in the report).
9. Emit the full §9 report fields: IRT θ + 95 % CI, per-primitive
   accuracy, robustness curve, sample-efficiency curve, Brier score,
   and compute cost.

### Reference

A Reference implementation **MUST** satisfy all Extended requirements
**and**:

10. Use the canonical reference implementations in `reference/`.
11. Pass every test in `conformance/`.
12. Reproduce the bytewise task output of every example in `examples/`
    under the seeds declared in those examples.

Implementations targeting a higher level automatically qualify for all lower
levels.

---

## §4 Task format

An A3S task is a single JSON object with the **REQUIRED** top-level fields:

```json
{
  "generator":          "<string, e.g. 'fill_enclosed'>",
  "generator_signature": "<string, 64-char hex sha256 of generator source>",
  "public_seed":         "<string>",
  "private_seed":        "<string>",
  "parameters":          { ... arbitrary JSON object ... },
  "task": {
    "train": [
      { "input":  [[...grid...]], "output": [[...grid...]] },
      ...
    ],
    "test":  [
      { "input":  [[...grid...]], "output": [[...grid...]] }
    ]
  },
  "task_metadata": {
    "invariances":   ["id", "pal", "rot90", "rot180", "rot270", "fh", "fv", "tr"],
    "primitives":    ["color", "shape", "object", ...],
    "license":       "<spdx-expression>",
    "source_url":    "<url-or-empty>",
    "audit_version": "<sha256 of the audit heuristics that produced the last audit verdict>"
  }
}
```

### §4.1 Field rules

- `generator` **MUST** be a non-empty string and **MUST** match the name
  registered in the originating generator package.
- `generator_signature` **MUST** be the lowercase hex sha256 of the
  generator's `.py` source (or `.zip` for compiled bundles) at the moment
  the task was generated. This makes reproducibility auditable: a
  verifier can re-run the generator and assert bytewise equality.
- `public_seed` and `private_seed` **MUST** be strings (any UTF-8).
- `parameters` **MUST** be a JSON object whose schema is declared by the
  generator (see §5).
- `task.train` **MUST** be a non-empty list of `{input, output}` pairs.
- `task.test` **MUST** contain exactly one pair (A3S v1) with both input
  and output present. A3S v1 deliberately uses single-test tasks; see
  §13 for the v2 multi-test extension.
- Every grid **MUST** be a list of lists of integers in `[0, 9]`.
- The `input` and `output` of any single pair **MUST** have the same shape.
- `task_metadata` **MAY** be omitted for backward compatibility, but any
  task without it cannot be considered Extended-conformant.

### §4.2 JSON Schema snippet

The authoritative JSON Schema lives in `reference/task_format.py`
(`A3S_TASK_SCHEMA`). The minimum required subset:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["generator", "generator_signature", "public_seed",
               "private_seed", "parameters", "task"],
  "properties": {
    "generator":           { "type": "string", "minLength": 1 },
    "generator_signature": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
    "public_seed":         { "type": "string" },
    "private_seed":        { "type": "string" },
    "parameters":          { "type": "object" },
    "task": {
      "type": "object",
      "required": ["train", "test"],
      "properties": {
        "train": { "type": "array", "minItems": 1,
                   "items": { "type": "object",
                              "required": ["input", "output"] } },
        "test":  { "type": "array", "minItems": 1, "maxItems": 1,
                   "items": { "type": "object",
                              "required": ["input", "output"] } }
      }
    },
    "task_metadata": { "type": "object" }
  }
}
```

### §4.3 Validation

A conforming parser **MUST** reject any task whose JSON does not match
the schema above, with an error message identifying the offending field.

---

## §5 Generator API

A generator is any callable with the signature:

```python
def generate(public_seed: str,
             private_seed: str,
             **params: Any) -> dict:
    """Return an A3S task dict matching §4."""
```

### §5.1 Determinism

A generator **MUST** be byte-deterministic: for any fixed
`(public_seed, private_seed, **params)`, calling `generate` repeatedly
**MUST** produce a task whose JSON serialisation is identical (after
`json.dumps(..., sort_keys=True)`) across runs.

This **MUST** hold across:

- Multiple calls within the same Python process.
- Multiple processes on the same OS + Python version.
- Multiple processes on different OSes that share the same Python version
  (a generator **SHOULD NOT** rely on `os.urandom`, `time.time`, or
  unseeded global state).

A generator **MUST** use a private `random.Random` instance seeded
explicitly from the seed arguments; it **MUST NOT** touch the global
`random` module's state.

### §5.2 Parameter schema

A generator **MUST** publish a `parameters_schema.json` next to its source.
This is a JSON Schema (Draft-07 or later) describing every key it accepts
in `**params`, with `type`, `minimum`/`maximum`, and `description` for
each. The schema **SHOULD** declare a `required` array for mandatory
parameters.

### §5.3 Signature

A generator **MUST** publish a `signature.json` file with:

```json
{
  "name":            "<generator name, e.g. 'fill_enclosed'>",
  "version":         "<semver of the generator package>",
  "source_sha256":   "<hex sha256 of generator.py>",
  "parameters_schema": "<relative path to parameters_schema.json>"
}
```

### §5.4 Publishing

A generator bundle **MUST** contain at least:

```
my_generator/
  generator.py            # the callable named `generate`
  signature.json
  parameters_schema.json
  README.md
  tests/test_determinism.py
  examples/task_01.json   # ≥3 example outputs
  examples/task_02.json
  examples/task_03.json
```

The `tests/test_determinism.py` **MUST** assert that
`generate(seed, seed)` returns the same JSON twice. Conformance at the
Core level depends on this.

### §5.5 Dispatcher

A conforming package **MUST** provide a registry mapping name to callable,
so that an evaluator can resolve a task's `generator` field to the function
that produced it:

```python
GENERATORS: Dict[str, Callable[..., dict]] = {
    "fill_enclosed": fill_enclosed.generate,
    ...
}
```

---

## §6 Agent interface

### §6.1 `solve()` signature

```python
def solve(task: dict, memory: "Memory", tools: "ToolBridge") -> "Answer":
    """Return an A3S answer for the test pair of `task`."""
```

- `task` is a fully-conformant A3S task dict (§4). The agent **MUST NOT**
  use `task.test[*].output` — that is the held-out ground truth.
- `memory` exposes three stores (see §6.3). The agent **MAY** read or write
  any of them.
- `tools` exposes a sandboxed execution environment. A conforming tool
  bridge **MUST** support:
  - `tools.execute_python(code: str) -> str`
  - `tools.run_heuristic(name: str, task: dict) -> dict`
  - `tools.score(predicted, ground_truth) -> dict` (only allowed when an
    external ground truth is provided; the agent **MUST NOT** call this on
    the test pair during a real evaluation).

The agent **MUST** return an `Answer`:

```python
@dataclass
class Answer:
    test_predictions: List[List[List[int]]]   # one grid per test pair
    trace: dict                                # see §6.2
```

`test_predictions` **MUST** contain exactly `len(task["test"])` grids, each
of the same shape as the corresponding `task["test"][i]["input"]`.

### §6.2 Trace schema

A conforming agent **MUST** record a structured trace as it works:

```json
{
  "agent_version": "<semver>",
  "started_at":    "<ISO-8601 UTC>",
  "finished_at":   "<ISO-8601 UTC>",
  "steps": [
    {
      "step":     "<int, 0..>",
      "kind":     "propose_program" | "verify" | "tool_call" | "final_answer",
      "program":  "<source code or DSL>",
      "verified": { "n_train_correct": "<int>", "n_train_total": "<int>" },
      "tool":     { "name": "...", "args": {...}, "result": "..." },
      "rationale":"<free text>"
    }
  ],
  "memory_writes": [
    { "store": "episodic|semantic|procedural", "key": "...", "value": "..." }
  ]
}
```

The trace is the primary mechanism by which an evaluator reconstructs *what
an agent did*. Every program proposed **MUST** be verified on at least one
train pair before being used to produce a final answer.

### §6.3 Memory API

```python
class Memory:
    def read_episodic(self, key: str) -> Any: ...
    def write_episodic(self, key: str, value: Any) -> None: ...
    def read_semantic(self, key: str) -> Any: ...
    def write_semantic(self, key: str, value: Any) -> None: ...
    def read_procedural(self, key: str) -> Any: ...
    def write_procedural(self, key: str, value: Any) -> None: ...
```

- **Episodic** memory is per-task: keyed by the current `task_id`. Cleared
  between tasks.
- **Semantic** memory is cross-task, version-stable knowledge (e.g.,
  "ARC colour 0 is usually background"). Persists across the lifetime of
  the agent process.
- **Procedural** memory is reusable skills (e.g., a learned heuristic).
  May persist across processes.

A Core agent **MAY** ignore all three stores; an Extended agent **SHOULD**
use at least episodic memory to record failed proposals.

### §6.4 Time budget

An agent **SHOULD** accept a wall-clock budget (e.g., 30 s per task). It
**MUST** return an answer before the budget expires; if it has no answer,
it **MUST** return the best candidate it has so far, or a copy of the test
input as a last resort.

---

## §7 Audit protocol

Every A3S task **MUST** be audited before being released into an
evaluation pipeline.

### §7.1 Heuristic signature

A heuristic is a callable:

```python
def predict(train_pairs: Sequence[Tuple[Grid, Grid]],
            test_input: Grid) -> Grid: ...
```

Heuristics **MUST NOT** introspect the private test output. They **MAY**
read the training pairs.

### §7.2 Registry

A conforming audit implementation **MUST** register at least 5 heuristics
covering at least these categories:

| Category | What it tests |
|----------|---------------|
| **identity-style**  | does the task reward "do nothing"? |
| **palette-style**   | does the task reward recolouring the input? |
| **geometry-style**  | does the task reward a fixed flip / rotate / tile? |
| **object-style**    | does the task reward extracting one connected component? |
| **counting-style**  | does the task reward a global count (e.g., of colours)? |

### §7.3 Verdict

A verdict is:

```json
{
  "task_id":      "<id>",
  "audited_at":   "<ISO-8601 UTC>",
  "audit_version":"<sha256>",
  "heuristics_run":["identity", "palette_majority", "mirror", ...],
  "per_heuristic": { "<name>": { "hit": <bool>, "rationale": "<str>" } },
  "trivially_solvable": <bool>,
  "verdict":      "pass" | "quarantine"
}
```

`verdict = "quarantine"` **MUST** be set when `trivially_solvable` is
true. The audit **MUST** also record which heuristic(s) hit, so the task
author can patch the generator.

### §7.4 Quarantine workflow

A quarantined task:

1. **MUST NOT** be used for tier-1 scoring in any official leaderboard.
2. **MAY** be released as a "diagnostic" task, with the audit log attached.
3. **SHOULD** be re-generated with different parameters or returned to the
   task author for adjustment.

When a submission encounters a quarantined task during evaluation, it
**MUST** record `audit_failed: true` in the per-task report row rather
than silently dropping the task or scoring it as zero.

---

## §8 Scoring protocol

### §8.1 Hierarchical 3-tier grader

A3S v1 freezes the following scoring rule. The first tier that matches
determines the score for the pair:

| Tier | Name | Rule | Score |
|------|------|------|-------|
| 1 | exact match | `predicted == ground_truth` cell-by-cell | 1.0 |
| 2 | equivalence | ∃ invariance in `task_metadata.invariances` that maps `predicted` to `ground_truth` exactly | 0.7 |
| 3 | structural | shape parity, object-count parity (tolerance 1), cell-match rate ≥ 0.6 after best-effort palette alignment | 0.3 |
| 0 | no match | fall-through | 0.0 |

A3S v1 freezes these tier weights; **MUST NOT** be changed without a
MAJOR version bump.

### §8.2 Invariance classes

Invariances are transformations of the predicted grid that the grader
treats as equivalent to ground truth.

| Code | Meaning |
|------|---------|
| `id`     | identity (the cell-by-cell match itself) |
| `pal`    | palette permutation (bijection over colours) |
| `rot90`  | 90° clockwise rotation |
| `rot180` | 180° rotation |
| `rot270` | 270° clockwise rotation |
| `fh`     | horizontal flip |
| `fv`     | vertical flip |
| `tr`     | translation of non-background cells within bounds |

A task **MUST** declare which invariances apply in
`task_metadata.invariances`. The default if unset is the full set above.
A task **MAY** declare a subset to forbid palette permutations (e.g., a
"colour the shape with the dominant colour" task).

### §8.3 Per-task result schema

```json
{
  "task_id":          "<id>",
  "tier":             1 | 2 | 3 | 0,
  "score":            <float>,
  "matched_invariance":"id|pal|rot90|rot180|rot270|fh|fv|tr|null",
  "palette_mapping":  { "<src_color>": "<dst_color>", ... } | null,
  "cell_match":       <float in [0,1]>,
  "object_iou":       <float in [0,1]>,
  "audit_failed":     <bool>
}
```

### §8.4 Top-level score

The `task_score` for a task with `n_test` test pairs is the mean of the
per-pair scores. The aggregate `task_set_score` for a task set is the mean
of the per-task scores.

---

## §9 Reporting protocol

A conforming submission **MUST** emit a `report.json` with at least:

```json
{
  "schema_version":   "1.0.0",
  "agent":            { "name": "...", "version": "..." },
  "n_tasks":          <int>,
  "task_set_score":   <float>,
  "raw_tier_scores":  { "tier1": <float>, "tier2": <float>, "tier3": <float>, "tier0": <float> },
  "irt": {
    "theta":     <float>,
    "theta_ci95":[<float>, <float>],
    "model":     "2pl" | "3pl",
    "n_solvers": <int>,
    "n_items":   <int>
  },
  "per_primitive_accuracy": {
    "<primitive_code>": <float in [0,1]>
  },
  "robustness_curve": [
    { "n_distractors": <int>, "accuracy": <float> }
  ],
  "sample_efficiency_curve": [
    { "n_demos": <int>, "accuracy": <float> }
  ],
  "brier":                  <float>,
  "compute_cost": {
    "gpu_hours":  <float>,
    "usd_per_task":<float>
  }
}
```

Notes:

- `irt.theta` and `irt.theta_ci95` are computed from the per-task tier-1
  outcomes against a population of reference solvers, or self-fit if the
  submission only has one solver (a warning is then emitted).
- `robustness_curve` reports accuracy as the count of distractor objects
  added to the test input increases from 0 to N. A submission **SHOULD**
  report at least three points (e.g., 0, 2, 5 distractors).
- `sample_efficiency_curve` reports accuracy as the number of demonstration
  pairs the agent sees increases from 1 to 8. A submission **SHOULD**
  report every integer in `[1, 8]`.
- `brier` is the Brier score of the agent's per-task confidence
  (if reported) vs the 0/1 outcome.
- `compute_cost` is mandatory; if the submitter does not track GPU-hours,
  `null` **MAY** be reported, but a value of `0.0` is required for
  `usd_per_task` so leaderboards can rank by cost.

---

## §10 Submission bundle

A submission **MUST** be a directory with this layout:

```
submission/
  model/                    # weights, configs, code-required artefacts
  code/                     # the `solve()` implementation
    agent.py
    README.md
  seeds.json                # the seeds the evaluator must use
  audit_log.json            # the §7 audit verdicts
  compute_cost.json         # raw cost telemetry
  report.json               # the §9 report
  submission.json           # top-level metadata:
                            #   { "agent_name", "agent_version",
                            #     "submission_id", "submitted_at" }
```

### §10.1 `seeds.json`

```json
{
  "schema_version": "1.0.0",
  "public_seeds":   ["seed-1", "seed-2", ...],
  "private_seeds":  ["priv-1", "priv-2", ...],
  "parameters":     { "<generator_name>": { "...": "..." } }
}
```

The evaluator **MUST** verify that every `(generator, public_seed,
private_seed)` triple referenced in the supplied task set is reproducible
under the supplied seeds + parameters.

### §10.2 `audit_log.json`

A list of §7 verdicts, one per task. The `audit_version` field **MUST**
match the audit module's source sha256 at the time of submission.

### §10.3 `compute_cost.json`

```json
{
  "gpu_model":     "<string>",
  "gpu_hours":     <float>,
  "cpu_hours":     <float>,
  "memory_gb_hours":<float>,
  "usd_per_task":  <float>
}
```

### §10.4 `report.json`

The §9 report. **MUST** be byte-identical to whatever the agent would
produce at runtime given the same seeds — i.e., the report is reproducible,
not a hand-edited summary.

### §10.5 `submission.json`

```json
{
  "schema_version": "1.0.0",
  "agent_name":     "<string>",
  "agent_version":  "<semver>",
  "submission_id":  "<uuid-or-equivalent>",
  "submitted_at":   "<ISO-8601 UTC>"
}
```

---

## §11 Reference implementations

The directory `reference/` contains the canonical implementations of each
of the seven A3S interfaces:

| File | Implements |
|------|------------|
| `task_format.py` | §4 — JSON Schema, parser, serializer, validator |
| `generator.py`   | §5 — abstract `Generator` base class |
| `airt.py`        | §6 — `Agent` base class, `Memory`, `ToolBridge` |
| `audit.py`       | §7 — `audit_task()` over the heuristics registry |
| `grader.py`      | §8 — `grade()` wrapper with tier weights |
| `irt.py`         | §9 — `fit_irt()` + θ + CI computation |

Each reference file **SHOULD** be readable in one sitting (≤150 lines) and
**MUST** contain at least two usage examples as inline doctests or in a
`__main__` block.

---

## §12 Examples

The directory `examples/` contains ready-to-copy bundles:

- `examples/task_family/` — a full A3S generator bundle wrapping
  `01-task-generator/generators/fill_enclosed.py` as the canonical example.
- `examples/agent/` — a Core-conformant agent that proposes three programs
  and picks the one that survives the audit-style brute-force check.
- `examples/heuristic/` — a single new heuristic (`output_equals_majority_of_train_outputs`)
  registered into the audit registry.
- `examples/submission/` — a complete §10 submission bundle with
  `report.json` baked from a small run.

---

## §13 Future work (v2 outlook)

A3S v2 is not yet specified, but the following extensions are under
discussion and **SHOULD NOT** be retro-fitted into v1.x:

1. **Multimodal grids.** Cells that carry `(colour, channel, object_id)`
   tuples for tasks that mix texture and shape.
2. **Language-conditioned tasks.** Natural-language instructions paired
   with grids; would add a `task.instruction` field and require the agent
   to consume it.
3. **Multi-test tasks.** Tasks with `len(test) > 1`; the score would
   become the harmonic mean over test pairs (to penalise single-pair
   lucky hits).
4. **Continual-learning scoring.** A drift metric on IRT θ across
   successive task sets submitted by the same agent.
5. **A formal type system for programs.** Replace the
   `propose_program` trace with a typed-DSL step so the grader can
   symbolically verify compositional rules.

Until these are ratified as a v2 RFC, implementations **SHOULD NOT**
add undocumented extensions — add a `task_metadata.extensions` object
instead, with a clear version string, so that future v2 versions can
migrate them cleanly.

---

*End of A3S v1.0.0 specification.*
