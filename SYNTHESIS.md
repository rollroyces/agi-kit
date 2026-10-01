# Enhancing ARC AGI — Synthesis

Five parallel sub-agents delivered concrete, runnable building blocks for the next-generation ARC benchmark. This doc summarises what each piece does, how they fit together, and the resulting ARC-AGI-3 architecture they enable.

## Root

```
F:\tmp\arc-enhance\
├── 01-task-generator\      Procedural ARC task generator framework
├── 02-irt\                  IRT calibration pipeline (2PL + 3PL)
├── 03-cognitive-taxonomy\   Cognitive-primitive taxonomy + coverage matrix
├── 04-grading\              Hierarchical 3-tier grader
└── 05-audit\                Adversarial audit heuristics harness
```

---

## 1. Procedural task generator (`01-task-generator\`)

**Purpose.** Fix ARC-AGI's contamination problem by replacing fixed public task lists with parametric generators that emit infinitely many novel tasks with held-out private seeds.

**What it produces.**
- 4 parametric generators: `fill_enclosed`, `rotate_largest`, `count_colors`, `symmetry_complete`.
- Unified `generate(public_seed, private_seed, **params)` signature.
- 16 example tasks (4 per generator) saved as standard ARC JSON.
- `validate.py` enforces schema validity, determinism (SHA-256 byte-identical across runs), and the public/private seed split.

**Status.** All 16 tasks pass validation; determinism verified.

**Limitations / extensions.**
- Pattern libraries are small (e.g., `rotate_largest` has only 4 shapes).
- No cross-seed deduplication or difficulty scoring yet.
- Generators are rectangular-only; non-rectangular shapes would broaden coverage.

---

## 2. IRT calibration (`02-irt\`)

**Purpose.** Replace raw "% correct" leaderboards with stable, comparable ability estimates via Item Response Theory.

**What it produces.**
- 2PL IRT (one discrimination `a_j`, one difficulty `b_j` per task; per-solver ability `θᵢ`). 3PL behind `--model 3pl`.
- Joint MAP estimation via L-BFGS-B with analytic gradient (2PL) and informative priors.
- Synthetic 30-solver × 50-item pipeline that recovers θ with r=0.91, b with r=0.92.
- 4 plots: ICCs, ability distribution, accuracy-vs-θ scatter, true-vs-estimated.
- Headline demo: solvers 7 and 18 both score 0.48–0.52 raw accuracy but differ by **0.39σ in latent ability**. The leaderboard calls them equal; IRT separates them.

**Status.** 22/22 tests pass. Pipeline runs end-to-end in <2s.

**Limitations / extensions.**
- 30 solvers × 50 items is small; `a` recovery is moderate (r=0.43). Real ARC deployment with hundreds of solvers will sharpen item estimates.
- Analytic 3PL gradient is the obvious next step before promoting 3PL to default.

---

## 3. Cognitive-primitive taxonomy (`03-cognitive-taxonomy\`)

**Purpose.** Replace ad-hoc task categorisation with a literature-grounded taxonomy that exposes *which* cognitive primitives a system handles vs which it lacks.

**What it produces.**
- **20 primitives** in 6 superordinate groups (Perceptual, Spatial, Numerical, Logical, Sequential/Planning, Causal, Analogical).
- Each primitive: definition + 1-3 cognitive-science references + 1-2 representative ARC task IDs.
- Coverage matrix: 21-row × 12-column table mapping primitives to ARC task families.
- Gap analysis with three classes of gaps (ARC-side, model-side, taxonomy-side).
- 44-entry bibliography grouped by topic.

**Top three gaps identified.**
1. **Structure-mapping analogy (A20)** — Gentner's canonical human-fluid-reasoning primitive; ARC tests only object-level similarity, not relational-structure transfer.
2. **Causal-chain reasoning (C18)** — Lake et al.'s "causal models" ingredient; ARC tests only surface-level "physics" (slide-until-blocked), not B→C→D chains.
3. **Long-horizon planning (T16)** — ARC caps at ≤3-step sequences; ≥5-step branching is where classical planners and chain-of-thought LLMs diverge most.

**Status.** Documents only, but ready to drive the next generation of procedural generators.

---

## 4. Hierarchical grading (`04-grading\`)

**Purpose.** Replace brittle exact-match grading with hierarchical scoring that credits structural understanding.

**What it produces.**
- **Tier 1 (weight 1.0)** — Exact cell-by-cell match.
- **Tier 2 (weight 0.7)** — Equivalence-class match under documented invariances: `pal` (bijective recolor), `rot90/180/270`, `fh/fv` (flips), `tr` (translation). Per-task selection via `task_metadata["invariances"]`.
- **Tier 3 (weight 0.3)** — Structural partial: same shape, connected-component count within tolerance, cell-match rate ≥ 0.6 after best palette alignment.
- `strict` flag disables tiers 2 and 3 for shape-completion tasks.
- 28 unit tests, 8-case demo, full spec document.

**Example of tier-3 partial credit.** A prediction with one cell wrong, one extra object, and a recoloured region scores `tier=3 score=0.30 cell_match=0.96 object_iou=0.80 objects=5/4`. Palette perm can't biject (different palette sizes) so this doesn't accidentally hit tier 2.

**Status.** 28/28 tests pass. Demo runs cleanly.

**Limitations / extensions.**
- Greedy alignment can mis-map on edge palette inputs (rare but worth a future bijective-search fallback).
- Tier-3 threshold (0.6 cell match) is heuristic; should be calibrated via IRT-style data.

---

## 5. Adversarial audit heuristics (`05-audit\`)

**Purpose.** Detect ARC tasks that are solvable by shallow heuristics, so they can be flagged or rejected before they enter a public/private split.

**What it produces.**
- 8 deterministic shallow solvers: `identity`, `palette_majority`, `mirror`, `largest_object`, `background_swap`, `diagonal_replicate`, `single_color_fill`, `palette_invert`. Each ignores `train_pairs` and runs in <1 ms.
- `audit.py` loads ARC tasks, runs every heuristic, compares to ground truth, reports per-heuristic accuracy and per-task "trivially-solvable" flag.
- 17 unit tests + 9 synthetic tasks (7 designed to be flagged, 2 deliberately hard).
- 17/17 tests pass; **7/9 synthetic tasks correctly flagged**, the 2 composite-rule tasks correctly not flagged.

**Status.** Working end-to-end; ready to be pointed at the public ARC-AGI corpus for a real audit run.

**Limitations / extensions.**
- All heuristics ignore `train_pairs`; for the next iteration add at least one "look at the demos" heuristic (e.g., output = first train's output).
- No principled coverage of compositional rules — the 2 unflagged tasks require rotate-then-recolor, which none of the 8 heuristics composes.

---

## How the five pieces fit together

The pieces are designed to compose into a single pipeline:

```
[03-taxonomy]  defines what cognitive primitives to test
       ↓
[01-generator]    produces parametric tasks targeting those primitives,
                   with public/private seed split
       ↓
[05-audit]         flags tasks solvable by shallow heuristics;
                   reject or quarantine flagged tasks
       ↓
[04-grading]       scores solver outputs with hierarchical partial credit
                   (instead of brittle cell-exact match)
       ↓
[02-IRT]           converts raw response matrices into comparable
                   ability estimates and item difficulties
       ↓
Leaderboard + per-primitive coverage matrix
```

Every stage outputs JSON / CSV / PNG artefacts that the next stage consumes. The audit and grading stages both work on the same ARC JSON format the generator emits. The IRT stage consumes the graded response matrix directly.

---

## Proposed ARC-AGI-3 architecture

Pulling all five together, this is what an ARC-AGI-3 release could look like:

1. **Task authoring** (taxonomy → generator).
   - Authors consult the cognitive-primitive taxonomy to identify under-served primitives.
   - Each new task is implemented as a parametric generator with `generate(public_seed, private_seed, **params)`.
   - Generators are open-sourced so the community can verify fairness; held-out private seeds are rotated quarterly.

2. **Quality gates before release** (audit).
   - Every generated task is run through the audit harness.
   - Tasks solved by any of 8 shallow heuristics are quarantined for human review or rejected.
   - Audit log is shipped with each release so transparency is auditable.

3. **Submission** (any solver stack).
   - Submitters output a predicted grid + optional natural-language explanation per test example.
   - Bundle: model weights, code, seeds, compute cost (GPU-hours, $/task).

4. **Scoring** (hierarchical grading).
   - `grade()` returns tier scores per example.
   - `task_score = mean(per-example scores)`.
   - Tier-2 invariances are derived from `task_metadata["invariances"]` and documented per task.

5. **Reporting** (IRT + coverage matrix).
   - Raw response matrix → IRT → per-solver θ, per-task a/b.
   - Per-primitive accuracy breakdown from the taxonomy's coverage matrix.
   - Headline metric: θ (with 95% CI), not raw %.
   - Secondary metrics: calibration (Brier), robustness curve under distractor objects, sample-efficiency curve over demo counts 1–8, compute cost per task.

6. **Ecosystem**.
   - Open leaderboards with reproducible artefacts (model + code + seeds + cost).
   - Community task contribution with quality gates (audit + human solvability + IRT calibration).
   - Age-stratified human baselines; cognitive-primitive decomposition of human performance.

---

## Cross-cutting insights

A few themes that emerged from doing all five in parallel:

- **Memorisation is the single biggest current threat to ARC-AGI's interpretability.** Everything else (grading, IRT, audit) is downstream of having a benchmark you can actually trust, which only procedural generation gives you.
- **Hierarchical grading + IRT compose multiplicatively.** Partial-credit scoring gives IRT more usable variance per solver-task pair; IRT gives partial-credit scoring a stable comparable signal. Doing only one leaves half the value on the table.
- **The taxonomy is the connective tissue.** The generator needs to know *what* to generate. The grading needs to know *what invariances* apply per primitive. The audit needs to know *what heuristic families* are dangerous. The IRT needs the coverage matrix to report per-primitive ability. Without the taxonomy, the other four are floating.
- **Audit + grading have a one-line integration: a task the audit flags is exactly a task whose `heuristic_solved_by` field becomes part of `task_metadata` for the grader.** The same task JSON can carry both signals without extra plumbing.

---

## Known gaps / next-step roadmap

1. **Real-data audit** — point `05-audit/audit.py` at the public ARC-AGI-1 corpus; quantify how many public tasks are exploitable.
2. **Per-primitive generator** — implement one generator per top-3 taxonomy gap (structure-mapping analogy, causal chains, long-horizon planning). These are the high-leverage additions for ARC-AGI-3.
3. **Real-data IRT** — run IRT on actual ARC-AGI submissions (or a Kaggle-style competition) to demonstrate θ on real solvers.
4. **Calibrated tier-3 threshold** — set the 0.6 cell-match cutoff from data rather than intuition.
5. **Compute-cost metric** — add `$/task` and `GPU-hours/task` columns to the leaderboard schema.
6. **Human baselines** — formalise age-stratified, time-limited, IRT-scored human runs for the new primitives.
7. **End-to-end pipeline glue** — a single `make_release.py` script that chains taxonomy → generator → audit → grading → IRT for a quarterly release cycle.

The five deliverables are real, runnable, and composeable. The roadmap above is the cheapest path from "five good pieces" to "one credible ARC-AGI-3."