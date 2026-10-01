# agi-kit — Synthesis

Five parallel sub-agents delivered concrete, runnable building blocks for
the next-generation ARC benchmark. This doc summarises what each piece does,
how they fit together, and the resulting ARC-AGI-3 architecture they enable.

The **Phase 1+2 pivot** (agi-kit rename + Reflector addition) is described
in the dedicated section at the end of this file.

## Root

```
F:\tmp\agi-kit\
├── domains\arc\generators\       Procedural ARC task generator framework
├── domains\arc\grading\          Hierarchical 3-tier grader
├── domains\arc\audit\             Adversarial audit heuristics harness
├── domains\arc\audit-on-generated\  0/16 trivially-solvable finding
├── domains\arc\real-eval\        Real ARC-AGI-1 driver + snapshot
├── infra\irt\                     IRT calibration pipeline (2PL + 3PL)
├── infra\taxonomy\                Cognitive-primitive taxonomy + coverage matrix
├── agent\                         CLAgent — 6-module cognitive-loop agent (incl. Reflector)
└── standard\                      A3S v1.0.0 — versioned protocol wrapping the above
```

---

## 1. Procedural task generator (`domains/arc/generators/`)

**Purpose.** Fix ARC-AGI's contamination problem by replacing fixed public
task lists with parametric generators that emit infinitely many novel tasks
with held-out private seeds.

**What it produces.**
- 4 parametric generators: `fill_enclosed`, `rotate_largest`,
  `count_colors`, `symmetry_complete`.
- Unified `generate(public_seed, private_seed, **params)` signature.
- 16 example tasks (4 per generator) saved as standard ARC JSON.
- `validate.py` enforces schema validity, determinism (SHA-256
  byte-identical across runs), and the public/private seed split.

**Status.** All 16 tasks pass validation; determinism verified.

**Limitations / extensions.**
- Pattern libraries are small (e.g. `rotate_largest` has only 4 shapes).
- No cross-seed deduplication or difficulty scoring yet.
- Generators are rectangular-only; non-rectangular shapes would broaden
  coverage.

---

## 2. IRT calibration (`infra/irt/`)

**Purpose.** Replace raw "% correct" leaderboards with stable, comparable
ability estimates via Item Response Theory.

**What it produces.**
- 2PL IRT (one discrimination `a_j`, one difficulty `b_j` per task;
  per-solver ability `θᵢ`). 3PL behind `--model 3pl`.
- Joint MAP estimation via L-BFGS-B with analytic gradient (2PL) and
  informative priors.
- Synthetic 30-solver × 50-item pipeline that recovers θ with r=0.91,
  b with r=0.92.
- 4 plots: ICCs, ability distribution, accuracy-vs-θ scatter,
  true-vs-estimated.
- Headline demo: solvers 7 and 18 both score 0.48–0.52 raw accuracy but
  differ by **0.39σ in latent ability**. The leaderboard calls them equal;
  IRT separates them.

**Status.** 22/22 tests pass. Pipeline runs end-to-end in <2s.

**Limitations / extensions.**
- 30 solvers × 50 items is small; `a` recovery is moderate (r=0.43). Real
  ARC deployment with hundreds of solvers will sharpen item estimates.
- Analytic 3PL gradient is the obvious next step before promoting 3PL to
  default.

---

## 3. Cognitive-primitive taxonomy (`infra/taxonomy/`)

**Purpose.** Replace ad-hoc task categorisation with a literature-grounded
taxonomy that exposes *which* cognitive primitives a system handles vs which
it lacks.

**What it produces.**
- **20 primitives** in 6 superordinate groups (Perceptual, Spatial,
  Numerical, Logical, Sequential/Planning, Causal, Analogical).
- Each primitive: definition + 1-3 cognitive-science references + 1-2
  representative ARC task IDs.
- Coverage matrix: 21-row × 12-column table mapping primitives to ARC
  task families.
- Gap analysis with three classes of gaps (ARC-side, model-side,
  taxonomy-side).
- 44-entry bibliography grouped by topic.

**Top three gaps identified.**
1. **Structure-mapping analogy (A20)** — Gentner's canonical
   human-fluid-reasoning primitive; ARC tests only object-level similarity,
   not relational-structure transfer.
2. **Causal-chain reasoning (C18)** — Lake et al.'s "causal models"
   ingredient; ARC tests only surface-level "physics" (slide-until-blocked),
   not B→C→D chains.
3. **Long-horizon planning (T16)** — ARC caps at ≤3-step sequences;
   ≥5-step branching is where classical planners and chain-of-thought LLMs
   diverge most.

**Status.** Documents only, but ready to drive the next generation of
procedural generators.

---

## 4. Hierarchical grading (`domains/arc/grading/`)

**Purpose.** Replace brittle exact-match grading with hierarchical scoring
that credits structural understanding.

**What it produces.**
- **Tier 1 (weight 1.0)** — Exact cell-by-cell match.
- **Tier 2 (weight 0.7)** — Equivalence-class match under documented
  invariances: `pal` (bijective recolor), `rot90/180/270`, `fh/fv` (flips),
  `tr` (translation). Per-task selection via
  `task_metadata["invariances"]`.
- **Tier 3 (weight 0.3)** — Structural partial: same shape,
  connected-component count within tolerance, cell-match rate ≥ 0.6 after
  best palette alignment.
- `strict` flag disables tiers 2 and 3 for shape-completion tasks.
- 28 unit tests, 8-case demo, full spec document.

**Example of tier-3 partial credit.** A prediction with one cell wrong, one
extra object, and a recoloured region scores `tier=3 score=0.30
cell_match=0.96 object_iou=0.80 objects=5/4`. Palette perm can't biject
(different palette sizes) so this doesn't accidentally hit tier 2.

**Status.** 28/28 tests pass. Demo runs cleanly.

**Limitations / extensions.**
- Greedy alignment can mis-map on edge palette inputs (rare but worth a
  future bijective-search fallback).
- Tier-3 threshold (0.6 cell match) is heuristic; should be calibrated via
  IRT-style data.

---

## 5. Adversarial audit heuristics (`domains/arc/audit/`)

**Purpose.** Detect ARC tasks that are solvable by shallow heuristics, so
they can be flagged or rejected before they enter a public/private split.

**What it produces.**
- 8 deterministic shallow solvers: `identity`, `palette_majority`,
  `mirror`, `largest_object`, `background_swap`, `diagonal_replicate`,
  `single_color_fill`, `palette_invert`. Each ignores `train_pairs` and runs
  in <1 ms.
- `audit.py` loads ARC tasks, runs every heuristic, compares to ground
  truth, reports per-heuristic accuracy and per-task "trivially-solvable"
  flag.
- 17 unit tests + 9 synthetic tasks (7 designed to be flagged, 2
  deliberately hard).
- 17/17 tests pass; **7/9 synthetic tasks correctly flagged**, the 2
  composite-rule tasks correctly not flagged.

**Status.** Working end-to-end; ready to be pointed at the public ARC-AGI
corpus for a real audit run.

**Limitations / extensions.**
- All heuristics ignore `train_pairs`; for the next iteration add at least
  one "look at the demos" heuristic (e.g. output = first train's output).
- No principled coverage of compositional rules — the 2 unflagged tasks
  require rotate-then-recolor, which none of the 8 heuristics composes.

---

## How the pieces fit together

The pieces are designed to compose into a single pipeline:

```
[infra/taxonomy]  defines what cognitive primitives to test
       ↓
[domains/arc/generators]    produces parametric tasks targeting those primitives,
                             with public/private seed split
       ↓
[domains/arc/audit]          flags tasks solvable by shallow heuristics;
                             reject or quarantine flagged tasks
       ↓
[domains/arc/grading]        scores solver outputs with hierarchical partial credit
                             (instead of brittle cell-exact match)
       ↓
[infra/irt]                  converts raw response matrices into comparable
                             ability estimates and item difficulties
       ↓
Leaderboard + per-primitive coverage matrix
```

Every stage outputs JSON / CSV / PNG artefacts that the next stage consumes.
The audit and grading stages both work on the same ARC JSON format the
generator emits. The IRT stage consumes the graded response matrix directly.

---

## Proposed ARC-AGI-3 architecture

Pulling all five together, this is what an ARC-AGI-3 release could look
like:

1. **Task authoring** (taxonomy → generator).
   - Authors consult the cognitive-primitive taxonomy to identify
     under-served primitives.
   - Each new task is implemented as a parametric generator with
     `generate(public_seed, private_seed, **params)`.
   - Generators are open-sourced so the community can verify fairness;
     held-out private seeds are rotated quarterly.

2. **Quality gates before release** (audit).
   - Every generated task is run through the audit harness.
   - Tasks solved by any of 8 shallow heuristics are quarantined for
     human review or rejected.
   - Audit log is shipped with each release so transparency is auditable.

3. **Submission** (any solver stack).
   - Submitters output a predicted grid + optional natural-language
     explanation per test example.
   - Bundle: model weights, code, seeds, compute cost (GPU-hours,
     $/task).

4. **Scoring** (hierarchical grading).
   - `grade()` returns tier scores per example.
   - `task_score = mean(per-example scores)`.
   - Tier-2 invariances are derived from
     `task_metadata["invariances"]` and documented per task.

5. **Reporting** (IRT + coverage matrix).
   - Raw response matrix → IRT → per-solver θ, per-task a/b.
   - Per-primitive accuracy breakdown from the taxonomy's coverage matrix.
   - Headline metric: θ (with 95% CI), not raw %.
   - Secondary metrics: calibration (Brier), robustness curve under
     distractor objects, sample-efficiency curve over demo counts 1–8,
     compute cost per task.

6. **Ecosystem**.
   - Open leaderboards with reproducible artefacts (model + code + seeds +
     cost).
   - Community task contribution with quality gates (audit + human
     solvability + IRT calibration).
   - Age-stratified human baselines; cognitive-primitive decomposition of
     human performance.

---

## Cross-cutting insights

A few themes that emerged from doing all five in parallel:

- **Memorisation is the single biggest current threat to ARC-AGI's
  interpretability.** Everything else (grading, IRT, audit) is downstream
  of having a benchmark you can actually trust, which only procedural
  generation gives you.
- **Hierarchical grading + IRT compose multiplicatively.** Partial-credit
  scoring gives IRT more usable variance per solver-task pair; IRT gives
  partial-credit scoring a stable comparable signal. Doing only one leaves
  half the value on the table.
- **The taxonomy is the connective tissue.** The generator needs to know
  *what* to generate. The grading needs to know *what invariances* apply
  per primitive. The audit needs to know *what heuristic families* are
  dangerous. The IRT needs the coverage matrix to report per-primitive
  ability. Without the taxonomy, the other four are floating.
- **Audit + grading have a one-line integration: a task the audit flags
  is exactly a task whose `heuristic_solved_by` field becomes part of
  `task_metadata` for the grader.** The same task JSON can carry both
  signals without extra plumbing.

---

## Known gaps / next-step roadmap

1. **Real-data audit** — point `domains/arc/audit/audit.py` at the public
   ARC-AGI-1 corpus; quantify how many public tasks are exploitable.
2. **Per-primitive generator** — implement one generator per top-3 taxonomy
   gap (structure-mapping analogy, causal chains, long-horizon planning).
   These are the high-leverage additions for ARC-AGI-3.
3. **Real-data IRT** — run IRT on actual ARC-AGI submissions (or a
   Kaggle-style competition) to demonstrate θ on real solvers.
4. **Calibrated tier-3 threshold** — set the 0.6 cell-match cutoff from
   data rather than intuition.
5. **Compute-cost metric** — add `$/task` and `GPU-hours/task` columns to
   the leaderboard schema.
6. **Human baselines** — formalise age-stratified, time-limited, IRT-scored
   human runs for the new primitives.
7. **End-to-end pipeline glue** — a single `make_release.py` script that
   chains taxonomy → generator → audit → grading → IRT for a quarterly
   release cycle.
8. **Multi-domain split** — once the CLAgent's six-module architecture is
   solid, lift it onto a second domain (chess, arithmetic, language) to
   stress-test the AGI-ready claim. The pieces that are *not* under
   `domains/arc/` (the agent, the standard, the IRT) are already
   domain-agnostic.

---

## Phase 1+2 pivot (agi-kit)

The kit went through two coordinated pivots in this phase.

### Phase 1 — Rename + restructure

The repository was renamed from `arc-enhance` to `agi-kit` and the layout
was refactored from a flat numbered list to a domain-layered tree:

```
arc-enhance/                       →    agi-kit/
01-task-generator/                        domains/arc/generators/
02-irt/                                   infra/irt/
03-cognitive-taxonomy/                    infra/taxonomy/
04-grading/                               domains/arc/grading/
05-audit/                                 domains/arc/audit/
06-audit-on-generated/                    domains/arc/audit-on-generated/
07-real-arc-eval/                         domains/arc/real-eval/
a3s/                                      standard/
psf-clagent/                              agent/
                                          agent/reflector/   (new in Phase 2)
```

The `psf-clagent/agent.py` file became `agent/clagent.py` (so `from agent
import CLAgent` works under the new layout), and `psf-clagent/dsl/`,
`reasoner/`, `memory/`, `outputs/`, `tests/` were all promoted into
top-level siblings of `clagent.py` inside `agent/`.

All old path references (`01-…`, `a3s`, `psf-clagent`, `arc-enhance`)
inside `.py` and `.md` files were updated; the snapshot at
`domains/arc/real-eval/snapshot/` was intentionally left as a frozen
historical reference and still references the old layout it was captured
under.

The one-off glue script `audit_generated_tasks.py` at the root was deleted;
its logic is captured in the agent README and the audit/audit-report
text output.

### Phase 2 — Reflector (CLAgent module 5)

The CLAgent architecture has 6 modules:

1. **Perception** — the DSL (already shipped)
2. **Memory** — procedural + episodic (already shipped)
3. **Reasoner** — template + LLM proposers (already shipped)
4. **Tool Bridge** — audit gate + standard reference (already shipped)
5. **Reflector** — **NEW**, this phase
6. **Self-Improver** — procedural-memory lifting (partially shipped)

The Reflector is the missing metacognition module. After VERIFY and before
COMMIT, the agent instantiates a `Reflector(audit_harness=...)` and asks
it to score how confident the agent should be in its winner and which of
four actions to take next:

| action          | trigger                                         | effect |
|-----------------|-------------------------------------------------|--------|
| `commit`        | confidence ≥ 0.85 and not audit-flagged         | existing COMMIT logic |
| `refine`        | confidence in the middle band                   | loop back to HYPOTHESIZE |
| `ask_for_help`  | very low confidence + ≥2 contradictions         | log + best-effort commit |
| `fallback`      | only the identity heuristic survived           | existing identity-fallback path |

The Reflector's `ReflectionReport` is attached to the agent's trace under
`trace["reflection"]`. See `agent/README.md` §"Reflector" and
`agent/reflector/reflector.py` for the full API.

The headline use case (per the audit-on-generated FINDINGS) is to *fix*
the "audit-flag fires on every ARC-AGI-1 run because identity-fallback
matches identity_heuristic" issue: the Reflector's `audit_flagged` check
demotes confidence and routes through `refine` instead of `commit`,
turning a binary gate into a graded signal.

#### Acceptance verified at the time of this SYNTHESIS

* All 136 prior tests still pass (agent/, infra/irt/, standard/conformance/,
  domains/arc/audit/, domains/arc/grading/).
* Tier-1 solve rate on the 16 generated tasks is **12/16** (unchanged from
  before Phase 2; the Reflector is informational in the MVP, not a
  re-router).
* 19 Reflector unit tests pass; integration test prints a sensible
  `ReflectionReport` (confidence ≥ 0.5, contradiction 0.0, action ∈
  {commit, refine, ask_for_help, fallback}).
* Top-level README rewritten to AGI-ready framing (links into each
  subdir, lists the 6-module architecture).

#### What's next (Phase 3+)

* **Phase 3 — multi-domain**: add a second domain (chess, arithmetic,
  language) under `domains/` to validate the AGI-ready claim.
* **Phase 4 — cross-domain transfer**: use the CLAgent's episodic memory
  to retrieve cross-domain hints.
* **Self-Improver (module 6) — research**: programmatic generation of new
  templates from solved traces; meta-learning the lift threshold; per-
  primitive difficulty-aware reflection.

The five original deliverables are real, runnable, and composable. With
the Reflector in place, the agent now has all six modules in spirit (the
Self-Improver is partial, but the loop is closed end-to-end). The
roadmap above is the cheapest path from "one good ARC kit" to "one
credible AGI kit."
