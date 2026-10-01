# agi-kit

> An **AGI-ready kit**: a benchmark enhancement, an open standard, and a
> **6-module cognitive-loop agent** designed to take us from ARC-AGI-1 to
> ARC-AGI-3 and beyond.

This repository packages seven concrete deliverables that, together, propose a
credible architecture for the next ARC release: parametric task generators,
adversarial audit, hierarchical grading, IRT calibration, a cognitive-primitive
taxonomy, a versioned standard (`A3S`), and a program-synthesis-first
**Cognitive-Loop Agent (CLAgent)** that satisfies the standard's `solve()`
interface.

The headline pivot in this phase: the project used to be ARC-specific. It is
now an **AGI-ready kit** whose first domain is ARC, but whose architecture is
designed to host additional reasoning domains without forking the agent.

---

## Status at a glance

| # | Deliverable | Headline metric |
|---|---|---|
| 1 | Procedural task generators — [`domains/arc/generators/`](./domains/arc/generators/) | 4 generators · 16 example tasks · byte-deterministic |
| 2 | IRT calibration — [`infra/irt/`](./infra/irt/) | 22/22 tests · 2PL + 3PL · θ with 95% CI |
| 3 | Cognitive-primitive taxonomy — [`infra/taxonomy/`](./infra/taxonomy/) | 20 primitives · 6 groups · 44 references |
| 4 | Hierarchical 3-tier grader — [`domains/arc/grading/`](./domains/arc/grading/) | 28/28 tests · tiers 1 / 2 / 3 |
| 5 | Adversarial audit harness — [`domains/arc/audit/`](./domains/arc/audit/) | 17/17 tests · 8 shallow heuristics |
| 6 | A3S standard — [`standard/`](./standard/) | v1.0.0 · 6 reference impls · 45 conformance tests |
| 7 | CLAgent (program-synthesis cognitive-loop agent) — [`agent/`](./agent/) | 136/136 tests · 12/16 tier-1 · Reflector wired |

Cross-deliverable headline: **0 / 16** procedurally-generated tasks are
trivially-solvable by any of the 8 shallow heuristics (see
[`domains/arc/audit-on-generated/FINDINGS.md`](./domains/arc/audit-on-generated/FINDINGS.md)).

---

## What is this?

**An AGI-ready kit, illustrated on ARC.** The CLAgent inside `agent/` is a
6-module cognitive-loop architecture that can — in principle — host any
reasoning domain whose tasks can be expressed as input/output pairs with a
held-out test. ARC is the first domain. The kit's per-domain slices
(`domains/arc/`) carry the ARC-specific generators, audit, grading, and
real-eval; everything else (`agent/`, `infra/`, `standard/`) is
domain-agnostic.

**A benchmark enhancement.** ARC-AGI's public task corpus is finite and
increasingly leaks into training data; the
[`domains/arc/generators/`](./domains/arc/generators/) sub-project fixes this
by replacing fixed task lists with parametric generators that emit
infinitely many novel tasks with a held-out **private seed**. Every emitted
task is byte-deterministic across runs and carries a SHA-256
`generator_signature` so a verifier can re-derive it. The
[`domains/arc/audit/`](./domains/arc/audit/) module then plays the role of a
quality gate: any task solved by one of 8 shallow heuristics is flagged
before scoring.

**A measurement upgrade.** The [`infra/irt/`](./infra/irt/) sub-project
replaces raw "%-correct" leaderboards with Item Response Theory (2PL and
3PL). Joint MAP via L-BFGS-B recovers latent ability θ and item
difficulty/discrimination jointly. Two solvers within ±0.04 raw accuracy on
50 items can differ by ≈ 0.4σ in latent ability — exactly the signal that the
leaderboard washes out.

**A standard.** [`standard/`](./standard/) freezes seven interfaces (task
JSON, generator API, agent `solve()`, audit verdict, 3-tier grader, IRT
reporting, submission bundle) into a versioned protocol at v1.0.0 — A3S, the
ARC-AGI-3 Standard. Implementations can declare Core / Extended / Reference
conformance; the bundled
[`standard/conformance/`](./standard/conformance/) suite validates the
strongest contract.

**An agent.** [`agent/`](./agent/) is the **CLAgent** — a Program-Synthesis
Cognitive-Loop Agent that satisfies the A3S `solve()` interface. It proposes
executable programs in a small functional DSL, executes them on train pairs,
keeps exact matches, lifts reused subroutines into procedural memory, and
commits the winner to the test input. The Phase 2 update adds the missing
**Reflector** module (CLAgent module 5), which sits between VERIFY and COMMIT
to score how confident the agent should be in its winner and which of four
actions to take next (`commit`, `refine`, `ask_for_help`, `fallback`). A real
LLM reasoner (any OpenAI-compatible endpoint) is wired in with a graceful
template-only fallback.

The cross-deliverable integration story is in
[`SYNTHESIS.md`](./SYNTHESIS.md); the per-component design docs live inside
each sub-directory.

---

## Architecture

End-to-end data flow from raw seeds to a scored submission:

```
                        ┌─────────────────────────────────────────────┐
                        │  infra/taxonomy                            │
                        │  20 primitives · coverage matrix            │
                        └────────────────────┬────────────────────────┘
                                             │ (which primitive to target)
                                             ▼
   public_seed + private_seed ──►  ┌────────────────────────────────────┐
                                    │  domains/arc/generators           │
                                    │  fill_enclosed / rotate_largest /  │
                                    │  count_colors / symmetry_complete  │
                                    │  → 4 × N ARC-JSON tasks             │
                                    └───────────────┬────────────────────┘
                                                    │ 16 wrapped tasks
                                                    ▼
                                    ┌────────────────────────────────────┐
                                    │  domains/arc/audit (8 heuristics)  │
                                    │  → audit_report.json / .txt         │
                                    └───────────────┬────────────────────┘
                                                    │ 0 / 16 flagged
                                                    ▼
                       A3S task JSON ──► ┌────────────────────────────────┐
                                          │  agent/  (CLAgent)             │
                                          │  OBSERVE → HYPOTHESIZE         │
                                          │  EXECUTE → VERIFY → REFLECT    │
                                          │  COMPRESS → COMMIT             │
                                          │  (+ Reflector metacognition)   │
                                          │  (+ LLMProposer fallback)      │
                                          └──────────────┬─────────────────┘
                                                         │ A3S answer + trace
                                                         ▼
                                          ┌────────────────────────────────┐
                                          │  domains/arc/grading (3 tiers) │
                                          │  tier-1 = 1.0 · tier-2 = 0.7   │
                                          │  tier-3 = 0.3 · else 0.0       │
                                          └──────────────┬─────────────────┘
                                                         │ response matrix
                                                         ▼
                                          ┌────────────────────────────────┐
                                          │  infra/irt (2PL / 3PL MAP)     │
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
A new release is `taxonomy → generate → audit → solve → grade → IRT →
bundle`.

---

## CLAgent's 6-module architecture

The CLAgent inside `agent/` follows a 6-module cognitive-loop pattern that
maps cleanly to AGI concerns:

| # | Module           | Path / concept                                |
|---|------------------|-----------------------------------------------|
| 1 | **Perception**   | `agent/dsl/` — grid DSL, types, interpreter   |
| 2 | **Memory**       | `agent/memory/` — procedural + episodic       |
| 3 | **Reasoner**     | `agent/reasoner/` — template + LLM proposers  |
| 4 | **Tool Bridge**  | `agent/audit_gate.py` + `standard/reference/` |
| 5 | **Reflector**    | `agent/reflector/` — confidence + action      |
| 6 | **Self-Improver**| Procedural-memory lifting (in `memory/`)      |

Modules 1–4 + part of 6 were shipped before Phase 2. **Module 5 (the
Reflector)** is the focus of this phase and is described in detail in
[`agent/README.md`](./agent/README.md#reflector-module-5).

---

## The 7 deliverables (now arranged by layer)

| Layer        | Path                                       | Status | Key metric |
|--------------|--------------------------------------------|--------|------------|
| Standard     | [`standard/`](./standard/)                 | v1.0.0 | 45 conformance tests |
| Agent        | [`agent/`](./agent/)                       | ✅     | 136 tests · 12/16 tier-1 |
| Infra        | [`infra/irt/`](./infra/irt/)               | ✅     | 22 IRT tests |
| Infra        | [`infra/taxonomy/`](./infra/taxonomy/)     | ✅     | 20 primitives · 44 refs |
| ARC domain   | [`domains/arc/generators/`](./domains/arc/generators/) | ✅ | 4 generators · 16 tasks |
| ARC domain   | [`domains/arc/grading/`](./domains/arc/grading/)       | ✅ | 28 tests |
| ARC domain   | [`domains/arc/audit/`](./domains/arc/audit/)           | ✅ | 17 tests · 8 heuristics |
| ARC domain   | [`domains/arc/audit-on-generated/`](./domains/arc/audit-on-generated/) | ✅ | 0/16 trivially-solvable finding |
| ARC domain   | [`domains/arc/real-eval/`](./domains/arc/real-eval/)   | ✅ | Real ARC-AGI-1 driver |

Two support artefacts complete the kit:

- [`SYNTHESIS.md`](./SYNTHESIS.md) — cross-deliverable integration narrative,
  including the **Phase 1+2 pivot** (agi-kit rename + Reflector addition).
- [`domains/arc/audit-on-generated/FINDINGS.md`](./domains/arc/audit-on-generated/FINDINGS.md)
  — empirical evidence that the 16 generated tasks pass the audit gate.

---

## Reflector (CLAgent module 5)

After VERIFY and before COMMIT, the agent instantiates a
`Reflector(audit_harness=...)` and asks it to score the candidate set. The
Reflector returns a `ReflectionReport`:

```python
@dataclass
class ReflectionReport:
    confidence: float          # ∈ [0, 1]
    contradiction: float       # ∈ [0, 1]
    audit_flagged: bool
    action: str                # "commit" | "refine" | "ask_for_help" | "fallback"
    reasoning_text: str
    winner_label: str
```

Action gates the COMMIT step:

* `commit`         — confidence ≥ 0.85 and not audit-flagged → existing COMMIT
* `refine`         — confidence in the middle band → loop back to HYPOTHESIZE
* `ask_for_help`   — very low confidence + ≥2 contradictions → log + best-effort
* `fallback`       — only the identity heuristic survives → identity-fallback path

See `agent/reflector/README_API.md` (rendered from
`agent/reflector/reflector.py`) for the full API and decision rules.

---

## Quick start

All commands are run from the repository root, `F:\tmp\agi-kit\`, on Python
3.13 with the standard library plus `numpy`, `scipy`, `pandas`, `matplotlib`,
and `pytest` where noted.

```bash
# 1. Regenerate the 16 example tasks (4 per generator × 4 generators).
cd domains/arc/generators && python generate_examples.py && python validate.py

# 2. Audit the 16 generated tasks with the 8-heuristic battery.
#    Writes domains/arc/audit/audit_report.json and audit_report.txt.
cd ../../../ && python -c "import sys; sys.path.insert(0, 'domains/arc/audit'); \
                          from audit import audit_tasks; \
                          import json; \
                          tasks = [json.load(open(p)) for p in __import__('pathlib').Path('domains/arc/generators/examples').rglob('task_*.json')]; \
                          print(audit_tasks(tasks))"

# 3. Run the agent on the 16 tasks (template proposer, no LLM needed).
cd agent && python run_mvp.py --reasoner template

# 4. Run the Reflector integration test on a fresh task.
cd .. && python -m agent.reflector.integration_test

# 5. Run all agent tests (136 + 19 Reflector).
cd agent && python -m unittest discover -s tests && python -m unittest agent.reflector.tests.test_reflector

# 6. Run the A3S conformance suite (45 tests).
cd ../standard/conformance && python -m unittest discover
```

Expected outputs (verified at the time of this README):

* step 1 → 16 tasks regenerated deterministically
* step 3 → `12 / 16` tier-1, `16 / 16` tier-3 ([agent/README.md](./agent/README.md))
* step 4 → `Reflector integration test PASSED`
* step 5 → `Ran 136 + 19 tests ... OK`
* step 6 → `Ran 45 tests ... OK`

---

## The A3S standard

The A3S protocol ([`standard/SPEC.md`](./standard/SPEC.md), v1.0.0) freezes
seven interfaces that the rest of the project consumes:

| # | Interface | SPEC § |
|---|-----------|--------|
| 1 | A3S task JSON shape | §4 |
| 2 | Generator API (`generate(public_seed, private_seed, **params)`) | §5 |
| 3 | Agent interface (`solve(task, memory, tools)`) | §6 |
| 4 | Audit verdict schema + heuristic registry | §7 |
| 5 | Hierarchical 3-tier grader + invariance classes | §8 |
| 6 | Reporting schema (IRT θ, robustness, sample-efficiency, Brier) | §9 |
| 7 | Submission bundle directory layout | §10 |

Three conformance levels are defined ([§3](./standard/SPEC.md)): **Core**
(minimal contract), **Extended** (full 3-tier grader + complete §9 report +
audit gate on scoring), and **Reference** (uses `standard/reference/` and
passes every `conformance/` test).

### Contributing

- **New generator / heuristic / agent** — implement the matching A3S
  interface and add at least one conformance test in
  [`standard/conformance/`](./standard/conformance/). See
  [`standard/README.md`](./standard/README.md) and the four
  [`standard/examples/`](./standard/examples/) bundles (`task_family/`,
  `agent/`, `heuristic/`, `submission/`) for drop-in templates.
- **Interface changes** — must go through the public-RFC process described
  in [`standard/VERSIONING.md`](./standard/VERSIONING.md). A change is
  MAJOR iff it causes a previously conforming artefact to fail a
  corresponding `conformance/` test in the new major version.

---

## Results

All numbers below are taken directly from each deliverable's documentation
(see per-row citations). They reflect a single in-repo run at the time of
this README.

### Generator × Audit loop

| Metric | Value |
|---|---|
| Tasks generated | 16 (4 × 4 generators) |
| Tasks flagged as trivially-solvable | **0 / 16** |
| Per-heuristic hit rate (best) | 0 / 16 |
| Calibration check on `synthetic_tasks.py` | 7 / 9 correctly flagged |

### Agent on the 16 generated tasks

| Family | n | tier-1 | tier-2 | tier-3 | avg attempts / solve |
|---|---|---|---|---|---|
| `fill_enclosed` | 4 | 0 | 0 | 4 | — |
| `rotate_largest` | 4 | 4 | 4 | 4 | 18.0 |
| `count_colors` | 4 | 4 | 4 | 4 | 18.0 |
| `symmetry_complete` | 4 | 4 | 4 | 4 | 18.0 |
| **TOTAL** | **16** | **12** | **12** | **16** | **rate = 75.00%** |

* **Tier-1 partial**: 12 / 16 = 75% (canonical solver rate, preserved
  after Phase 2 Reflector wiring).
* **Tier-3 partial**: 16 / 16 = 100% (every task gets structural credit).
* **Procedural memory**: 20 entries after a full sweep — `identity_program`,
  `mirror_program`, `flip_v_program` + 16 winning programs + 1 auto-lifted
  subroutine.
* **Reflector (Phase 2)**: confidence ∈ [0.5, 1.0] on solved tasks,
  action = `commit` or `refine`; identity-only audits demote to
  `refine`; no-survivor path falls through to `ask_for_help`.
* **LLM reasoner**: real OpenAI-compatible client; falls back to the
  template proposer when `OPENAI_API_KEY` is unset or the endpoint errors.

### IRT headline

* θ recovery on synthetic 30 × 50 data: `r ≈ 0.91`.
* Difficulty recovery: `r ≈ 0.92`.
* Solver pairs at 0.48 vs 0.52 raw accuracy: **Δθ = 0.39σ**.

### Test counts (verified at README time)

| Suite | Command | Result |
|---|---|---|
| infra/irt | `cd infra/irt && python -m pytest tests/` | 22 passed |
| domains/arc/grading | `cd domains/arc/grading && python -m unittest test_grader` | 28 passed |
| domains/arc/audit | `cd domains/arc/audit && python -m unittest test_heuristics` | 17 passed |
| standard (A3S) | `cd standard/conformance && python -m unittest discover` | 45 passed |
| agent (CLAgent) | `cd agent && python -m unittest discover -s tests` | 136 passed |
| agent (Reflector) | `python -m unittest agent.reflector.tests.test_reflector` | 19 passed |
| **Total** | | **267 passed** |

---

## Citations

- **Cross-deliverable integration** — see [`SYNTHESIS.md`](./SYNTHESIS.md)
  for the full narrative: how each piece consumes the previous piece's
  artefacts, the proposed ARC-AGI-3 release cycle, the **Phase 1+2 pivot
  (agi-kit rename + Reflector addition)**, and the cross-cutting insights
  that emerged (memorisation as the biggest threat to ARC interpretability;
  hierarchical grading and IRT composing multiplicatively; taxonomy as the
  connective tissue).
- **Cognitive-science references** — see
  [`infra/taxonomy/bibliography.md`](./infra/taxonomy/bibliography.md) for
  the 44-entry citation list backing the 20 cognitive primitives (Chollet
  2019, Mitchell 2021, Acquaviva et al. 2022, Lake et al. 2017, Spelke,
  Gentner, Dehaene, Kahneman, Hofstadter, …).
- **Per-component design docs** — each sub-directory's own `README.md`
  carries the methodology, limitations, and known gaps for that piece.

---

## License & contributing

- **License**: Apache-2.0 (`LICENSE`); the internal
  `standard/examples/task_family/` declares generated content as `CC0-1.0`
  for downstream reuse — see
  [standard/examples/task_family/generator.py](./standard/examples/task_family/generator.py)
  `task_metadata.license`).
- **Standard version**: this README documents the project against
  **A3S v1.0.0** ([`standard/SPEC.md`](./standard/SPEC.md)).
- **Contributing**: open a pull request. New generators, heuristics, or
  agents MUST conform to the matching A3S interface and add at least one
  conformance test under [`standard/conformance/`](./standard/conformance/).
  Interface changes go through the RFC process in
  [`standard/VERSIONING.md`](./standard/VERSIONING.md).
- **Known gaps / next steps** — see
  [`SYNTHESIS.md` §"Known gaps / next-step roadmap"](./SYNTHESIS.md);
  the cheapest path to "one credible ARC-AGI-3" runs through a real-ARC
  audit, per-primitive generators for the top-3 taxonomy gaps
  (structure-mapping analogy, causal chains, long-horizon planning),
  IRT on actual ARC submissions, and a Phase 3 multi-domain split
  (e.g. chess / arithmetic / language) on top of the CLAgent.
