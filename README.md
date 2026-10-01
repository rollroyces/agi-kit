# arc-enhance

> A benchmark enhancement, an open standard, and an agent that solves it —
> designed for ARC-AGI-3 and beyond.

This repository packages seven concrete deliverables that, together, propose a
credible architecture for the next ARC release: parametric task generators,
adversarial audit, hierarchical grading, IRT calibration, a cognitive-primitive
taxonomy, a versioned standard (A3S) that wraps all of the above, and a
program-synthesis-first agent that satisfies the standard's `solve()`
interface.

---

## Status at a glance

| # | Deliverable | Headline metric |
|---|---|---|
| 1 | [Procedural task generators](./01-task-generator/) | ✅ 4 generators · 16 example tasks · byte-deterministic |
| 2 | [IRT calibration](./02-irt/) | ✅ 22/22 tests pass · 2PL + 3PL · θ-with-95% CI |
| 3 | [Cognitive-primitive taxonomy](./03-cognitive-taxonomy/) | ✅ 20 primitives · 6 groups · 44 references |
| 4 | [Hierarchical 3-tier grader](./04-grading/) | ✅ 28/28 tests pass · tiers 1 / 2 / 3 |
| 5 | [Adversarial audit harness](./05-audit/) | ✅ 17/17 tests pass · 8 shallow heuristics |
| 6 | [A3S standard](./a3s/) | ✅ v1.0.0 · 6 reference impls · 45 conformance tests |
| 7 | [PSF-CLAgent](./psf-clagent/) | ✅ 105/105 tests pass · 75% tier-1 on 16 tasks · LLM reasoner wired |

Cross-deliverable headline: **0 / 16** procedurally-generated tasks are
trivially-solvable by any of the 8 shallow heuristics (see
[`06-audit-on-generated/FINDINGS.md`](./06-audit-on-generated/FINDINGS.md)).

---

## What is this?

**A benchmark enhancement.** ARC-AGI's public task corpus is finite and
increasingly leaks into training data; the
[01-task-generator](./01-task-generator/) sub-project fixes this by replacing
fixed task lists with parametric generators that emit infinitely many novel
tasks with a held-out **private seed**. Every emitted task is byte-deterministic
across runs and carries a SHA-256 `generator_signature` so a verifier can
re-derive it. The
[05-audit](./05-audit/) module then plays the role of a quality gate: any task
solved by one of 8 shallow heuristics is flagged before scoring.

**A measurement upgrade.** The [02-irt](./02-irt/) sub-project replaces raw
"%-correct" leaderboards with Item Response Theory (2PL and 3PL). Joint MAP
via L-BFGS-B recovers latent ability θ and item difficulty/discrimination
jointly. Two solvers within ±0.04 raw accuracy on 50 items can differ by
≈ 0.4σ in latent ability — exactly the signal that the leaderboard washes out.

**A standard.** [a3s/](./a3s/) freezes seven interfaces (task JSON, generator
API, agent `solve()`, audit verdict, 3-tier grader, IRT reporting, submission
bundle) into a versioned protocol at v1.0.0. Implementations can declare
Core / Extended / Reference conformance; the bundled
[`conformance/`](./a3s/conformance/) suite validates the strongest contract.

**An agent.** [psf-clagent/](./psf-clagent/) is a Program-Synthesis-First
Cognitive Loop Agent that satisfies the A3S `solve()` interface. It proposes
executable programs in a small functional DSL, executes them on the train
pairs, keeps exact matches, lifts reused subroutines into procedural memory,
and commits the winner to the test input. A real LLM reasoner (any
OpenAI-compatible endpoint) is wired in with a graceful template-only
fallback.

The cross-deliverable integration story is in
[`SYNTHESIS.md`](./SYNTHESIS.md); the per-component design docs live inside
each sub-directory.

---

## Architecture

End-to-end data flow from raw seeds to a scored submission:

```
                        ┌─────────────────────────────────────────────┐
                        │  03-cognitive-taxonomy                     │
                        │  20 primitives · coverage matrix            │
                        └────────────────────┬────────────────────────┘
                                             │ (which primitive to target)
                                             ▼
   public_seed + private_seed ──►  ┌────────────────────────────────────┐
                                    │  01-task-generator                 │
                                    │  fill_enclosed / rotate_largest /  │
                                    │  count_colors / symmetry_complete  │
                                    │  → 4 × N ARC-JSON tasks             │
                                    └───────────────┬────────────────────┘
                                                    │ 16 wrapped tasks
                                                    ▼
                                    ┌────────────────────────────────────┐
                                    │  05-audit  (8 shallow heuristics)   │
                                    │  audit_generated_tasks.py (glue)    │
                                    │  → audit_report.json / .txt         │
                                    └───────────────┬────────────────────┘
                                                    │ 0 / 16 flagged
                                                    ▼
                       A3S task JSON ──► ┌────────────────────────────────┐
                                          │  psf-clagent                   │
                                          │  OBSERVE → HYPOTHESIZE         │
                                          │  EXECUTE → VERIFY → REFLECT    │
                                          │  COMPRESS → COMMIT             │
                                          │  (+ LLMProposer fallback)      │
                                          └──────────────┬─────────────────┘
                                                         │ A3S answer + trace
                                                         ▼
                                          ┌────────────────────────────────┐
                                          │  04-grading (3 tiers)          │
                                          │  tier-1 = 1.0 · tier-2 = 0.7   │
                                          │  tier-3 = 0.3 · else 0.0       │
                                          └──────────────┬─────────────────┘
                                                         │ response matrix
                                                         ▼
                                          ┌────────────────────────────────┐
                                          │  02-irt (2PL / 3PL MAP)        │
                                          │  → θ per solver · (a,b[,c])     │
                                          │    per task · 95% CIs           │
                                          └──────────────┬─────────────────┘
                                                         │
                                                         ▼
                                          ┌────────────────────────────────┐
                                          │  Submission bundle (SPEC §10)  │
                                          │  model + code + seeds + cost    │
                                          │  → leaderboard + θ-rank        │
                                          └────────────────────────────────┘
```

Every arrow is a concrete file on disk: tasks are JSON, the audit report is
JSON + text, the agent trace is JSON, the IRT output is CSV + JSON + PNGs.
A new release is `taxonomy → generate → audit → solve → grade → IRT → bundle`.

---

## The 7 deliverables

| # | Name | Path | Status | Key metric | One-line description |
|---|---|---|---|---|---|
| 1 | Procedural task generators | [`01-task-generator/`](./01-task-generator/) | ✅ | 4 generators · 16 tasks | Parametric ARC task generators with held-out private seeds and byte-deterministic output. |
| 2 | IRT calibration | [`02-irt/`](./02-irt/) | ✅ | 22/22 tests | 2PL / 3PL IRT fitting via joint MAP; recovers θ, a, b from a response matrix. |
| 3 | Cognitive-primitive taxonomy | [`03-cognitive-taxonomy/`](./03-cognitive-taxonomy/) | ✅ | 20 primitives · 44 refs | Literature-grounded taxonomy with coverage matrix and gap analysis for ARC-AGI-3. |
| 4 | Hierarchical 3-tier grader | [`04-grading/`](./04-grading/) | ✅ | 28/28 tests | Exact / equivalence-class / structural partial credit with per-task invariances. |
| 5 | Adversarial audit harness | [`05-audit/`](./05-audit/) | ✅ | 17/17 tests · 8 heuristics | Detects tasks solvable by shallow blind maps before they enter scoring. |
| 6 | A3S standard | [`a3s/`](./a3s/) | ✅ | v1.0.0 · 45 conformance tests | Versioned protocol wrapping the five deliverables into seven frozen interfaces. |
| 7 | PSF-CLAgent | [`psf-clagent/`](./psf-clagent/) | ✅ | 105/105 tests · 12/16 tier-1 | Program-synthesis-first cognitive-loop agent satisfying the A3S `solve()` interface. |

Two support artefacts complete the project:

- [`SYNTHESIS.md`](./SYNTHESIS.md) — cross-deliverable integration narrative.
- [`06-audit-on-generated/FINDINGS.md`](./06-audit-on-generated/FINDINGS.md) — empirical evidence that the 16 generated tasks pass the audit gate.
- [`audit_generated_tasks.py`](./audit_generated_tasks.py) — the glue script that walks the generator output and runs the audit harness.

---

## Quick start

All commands are run from the repository root, `F:\tmp\arc-enhance\`, on
Python 3.13 with the standard library plus `numpy`, `scipy`, `pandas`,
`matplotlib`, and `pytest` where noted.

```bash
# 1. Regenerate the 16 example tasks (4 per generator × 4 generators).
cd 01-task-generator && python generate_examples.py && python validate.py

# 2. Audit the 16 generated tasks with the 8-heuristic battery.
#    Writes 05-audit/audit_report.json and audit_report.txt.
cd .. && python audit_generated_tasks.py

# 3. Run the agent on the 16 tasks (template proposer, no LLM needed).
cd psf-clagent && python run_mvp.py

# 4. Fit the IRT pipeline on synthetic 30-solvers × 50-items data.
#    Writes CSVs + JSON + PNGs under 02-irt/outputs/.
cd .. && python 02-irt/run_pipeline.py

# 5. Run the A3S conformance suite (45 tests, ~0.1s).
cd a3s/conformance && python -m unittest discover
```

Expected outputs (verified at the time of this README):

- step 2 → `0 / 16` flagged ([FINDINGS.md](./06-audit-on-generated/FINDINGS.md))
- step 3 → `12 / 16` tier-1, `16 / 16` tier-3 ([psf-clagent/README.md](./psf-clagent/README.md))
- step 4 → θ recovery `r ≈ 0.91` ([02-irt/README.md §1](./02-irt/README.md))
- step 5 → `Ran 45 tests ... OK`

---

## The A3S standard

The A3S protocol ([`a3s/SPEC.md`](./a3s/SPEC.md), v1.0.0) freezes seven
interfaces that the rest of the project consumes:

| # | Interface | SPEC § |
|---|---|---|
| 1 | A3S task JSON shape | §4 |
| 2 | Generator API (`generate(public_seed, private_seed, **params)`) | §5 |
| 3 | Agent interface (`solve(task, memory, tools)`) | §6 |
| 4 | Audit verdict schema + heuristic registry | §7 |
| 5 | Hierarchical 3-tier grader + invariance classes | §8 |
| 6 | Reporting schema (IRT θ, robustness, sample-efficiency, Brier) | §9 |
| 7 | Submission bundle directory layout | §10 |

Three conformance levels are defined ([§3](./a3s/SPEC.md)): **Core** (minimal
contract), **Extended** (full 3-tier grader + complete §9 report + audit gate
on scoring), and **Reference** (uses `a3s/reference/` and passes every
`conformance/` test).

### A generator implementing the A3S API

This snippet is from
[`a3s/examples/task_family/generator.py`](./a3s/examples/task_family/generator.py)
and shows the contract every A3S-conformant generator must honour:

```python
import hashlib, os, sys, importlib.util
from typing import Any, Dict

_GEN_PATH = os.path.join(
    "01-task-generator", "generators", "fill_enclosed.py"
)

def _source_signature(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()

class FillEnclosedGenerator:
    name = "fill_enclosed"
    version = "1.0.0"

    def __init__(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "fill_enclosed", _GEN_PATH
        )
        self._mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(self._mod)
        self.signature = _source_signature(_GEN_PATH)

    def generate(self, public_seed: str, private_seed: str, **params: Any) -> Dict[str, Any]:
        body = self._mod.generate(public_seed, private_seed, **params)  # {"train":[...], "test":[...]}
        return {
            "generator":           self.name,
            "generator_signature": self.signature,                       # sha256 hex
            "public_seed":         public_seed,
            "private_seed":        private_seed,
            "parameters":          dict(params),
            "task":                body,
            "task_metadata": {                                            # §4
                "invariances":   ["id", "pal", "rot90", "rot180",
                                   "rot270", "fh", "fv", "tr"],
                "primitives":    ["color", "shape", "object"],
                "license":       "CC0-1.0",
                "source_url":    "",
                "audit_version": "",
            },
        }
```

The four top-level fields `generator`, `generator_signature`, `public_seed`,
and `private_seed` are what make a JSON artefact identifiable and
re-derivable; the `task_metadata` block is what makes it scoreable by the
Extended grader.

### Contributing

- **New generator / heuristic / agent** — implement the matching A3S
  interface and add at least one conformance test in
  [`a3s/conformance/`](./a3s/conformance/). See
  [`a3s/README.md`](./a3s/README.md) and the four
  [`a3s/examples/`](./a3s/examples/) bundles (`task_family/`, `agent/`,
  `heuristic/`, `submission/`) for drop-in templates.
- **Interface changes** — must go through the public-RFC process described
  in [`a3s/VERSIONING.md`](./a3s/VERSIONING.md). A change is MAJOR iff it
  causes a previously conforming artefact to fail a corresponding
  `conformance/` test in the new major version.

---

## Results

All numbers below are taken directly from each deliverable's documentation
(see per-row citations). They reflect a single in-repo run at the time of
this README.

### Generator × Audit loop ([FINDINGS.md](./06-audit-on-generated/FINDINGS.md))

| Metric | Value |
|---|---|
| Tasks generated | 16 (4 × 4 generators) |
| Tasks flagged as trivially-solvable | **0 / 16** |
| Per-heuristic hit rate (best) | 0 / 16 |
| Calibration check on `synthetic_tasks.py` | 7 / 9 correctly flagged |

### Agent on the 16 generated tasks ([psf-clagent/README.md](./psf-clagent/README.md))

| Family | n | tier-1 | tier-2 | tier-3 | avg attempts / solve |
|---|---|---|---|---|---|
| `fill_enclosed` | 4 | 0 | 0 | 4 | — |
| `rotate_largest` | 4 | 4 | 4 | 4 | 15.0 |
| `count_colors` | 4 | 4 | 4 | 4 | 15.0 |
| `symmetry_complete` | 4 | 4 | 4 | 4 | 15.0 |
| **TOTAL** | **16** | **12** | **12** | **16** | **rate = 75.00%** |

- **Tier-1 partial**: 12 / 16 = 75% (canonical solver rate).
- **Tier-3 partial**: 16 / 16 = 100% (every task gets structural credit).
- **Procedural memory**: 20 entries after a full sweep — `identity_program`,
  `mirror_program`, `flip_v_program` + 16 winning programs + **1
  auto-lifted subroutine** (the shared fill-enclosed template body).
- **LLM reasoner**: real OpenAI-compatible client; falls back to the
  template proposer when `OPENAI_API_KEY` is unset or the endpoint errors.

### IRT headline ([02-irt/README.md §6](./02-irt/README.md))

- θ recovery on synthetic 30 × 50 data: `r ≈ 0.91`.
- Difficulty recovery: `r ≈ 0.92`.
- Solver pairs at 0.48 vs 0.52 raw accuracy: **Δθ = 0.39σ**.

### Test counts (verified at README time)

| Suite | Command | Result |
|---|---|---|
| 02-irt | `cd 02-irt && python -m pytest tests/` | 22 passed |
| 04-grading | `cd 04-grading && python -m unittest test_grader` | 28 passed |
| 05-audit | `cd 05-audit && python -m unittest test_heuristics` | 17 passed |
| a3s | `cd a3s/conformance && python -m unittest discover` | 45 passed |
| psf-clagent | `cd psf-clagent && python -m unittest discover -s tests` | 105 passed |
| **Total** | | **217 passed** |

---

## Citations

- **Cross-deliverable integration** — see [`SYNTHESIS.md`](./SYNTHESIS.md)
  for the full narrative: how each piece consumes the previous piece's
  artefacts, the proposed ARC-AGI-3 release cycle, and the cross-cutting
  insights that emerged (memorisation as the biggest threat to ARC
  interpretability; hierarchical grading and IRT composing multiplicatively;
  taxonomy as the connective tissue).
- **Cognitive-science references** — see
  [`03-cognitive-taxonomy/bibliography.md`](./03-cognitive-taxonomy/bibliography.md)
  for the 44-entry citation list backing the 20 cognitive primitives
  (Chollet 2019, Mitchell 2021, Acquaviva et al. 2022, Lake et al. 2017,
  Spelke, Gentner, Dehaene, Kahneman, Hofstadter, …).
- **Per-component design docs** — each sub-directory's own `README.md`
  carries the methodology, limitations, and known gaps for that piece.

---

## License & contributing

- **License**: Apache-2.0 (`LICENSE` to be added at the repository root; the
  internal `examples/task_family/` declares generated content as `CC0-1.0`
  for downstream reuse — see
  [a3s/examples/task_family/generator.py](./a3s/examples/task_family/generator.py)
  `task_metadata.license`).
- **Standard version**: this README documents the project against
  **A3S v1.0.0** ([`a3s/SPEC.md`](./a3s/SPEC.md)).
- **Contributing**: open a pull request. New generators, heuristics, or
  agents MUST conform to the matching A3S interface and add at least one
  conformance test under [`a3s/conformance/`](./a3s/conformance/).
  Interface changes go through the RFC process in
  [`a3s/VERSIONING.md`](./a3s/VERSIONING.md).
- **Known gaps / next steps** — see
  [`SYNTHESIS.md` §"Known gaps / next-step roadmap"](./SYNTHESIS.md);
  the cheapest path to "one credible ARC-AGI-3" runs through a real-ARC
  audit, per-primitive generators for the top-3 taxonomy gaps
  (structure-mapping analogy, causal chains, long-horizon planning), and
  IRT on actual ARC submissions.
