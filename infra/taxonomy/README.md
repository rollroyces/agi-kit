# infra/taxonomy — Cognitive-Primitive Taxonomy for ARC Tasks

This directory contains a research-grounded **taxonomy of cognitive
primitives** that the ARC (Abstraction and Reasoning Corpus) benchmark draws
on, plus a coverage matrix over ARC-AGI-1 / ARC-AGI-2 task families and a
gap-analysis suggesting primitives to add to ARC-AGI-3.

This deliverable is the "taxonomy side" of the larger agi-kit project. It is
a **document**, not a code module; no classifier or model is built here.

---

## Files

```
infra/taxonomy/
├── README.md            ← this file
├── taxonomy.md          ← main research document (the deliverable)
└── bibliography.md      ← complete citation list for taxonomy.md
```

* **`taxonomy.md`** — main document. Contains:
  1. motivation (§1),
  2. taxonomy tree (§2),
  3. one section per primitive with definition + references + ARC task IDs (§3),
  4. coverage matrix (§4),
  5. gap analysis — three sub-sections covering ARC gaps, model gaps,
     and taxonomy gaps (§5),
  6. six suggested new primitives for ARC-AGI-3 (§6),
  7. how to use the taxonomy (§7),
  8. limitations (§8),
  9. cross-references (§9).

* **`bibliography.md`** — every source cited in `taxonomy.md`, organised by
  topic (ARC papers, cognitive science, ARC datasets, etc.) and summarised
  in a citation table at the end.

---

## What you get in one minute

* **20 primitives** in 6 superordinate groups (Perceptual, Spatial,
  Numerical, Logical, Sequential/Planning, Causal, Analogical).
* **≥1 cognitive-science reference per primitive** (often 2–3), drawn from
  Spelke, Piaget, Gentner, Lake et al., Dehaene, Kahneman, Hofstadter, etc.
* **≥1 public ARC task ID per primitive**, drawn from `arc-agi-1` and
  `arc-agi-2` (community-documented in the ARC Prize GitHub Discussions and
  Kaggle 2024 write-ups).
* **Coverage matrix** mapping primitives → ARC task families → representative
  task IDs.
* **Three classes of gap**: under-represented primitives in ARC, primitives
  current AI fails on, and cross-cutting taxonomy debts.
* **Six proposed new primitives** for ARC-AGI-3 (multi-step relational
  causal induction, long-horizon planning, structure-mapping analogy,
  causal-chain reasoning, instruction-following under ambiguity, recursive
  composition).

---

## How the deliverable is structured (quick map)

| Section | What it answers |
|---|---|
| §1 Why a taxonomy? | Why a shared vocabulary is needed before reporting model coverage. |
| §2 Taxonomy tree | The grouping into P / S / N / L / T / C / A. |
| §3 Primitives, one by one | Atomic definition, references, ARC task IDs. |
| §4 Coverage matrix | Cross-tab primitive × ARC task family. |
| §5 Gap analysis | Under-served primitives, model-side blind spots, taxonomy debts. |
| §6 New primitives for ARC-AGI-3 | N-α, T-α, A-α, C-α, I-α, R-α. |
| §7 How to use | Coverage reporting, task design, evaluation, generation loop. |

---

## How to use this deliverable

For sibling sub-agents (and humans):

1. **Task generator (`domains/arc/generators`)** — when generating a new
   ARC puzzle, tag it with the primitive set it loads
   (e.g. `{S6, L13, N10}` = "rotate, then conditional-fill, using the
   count"). Use §3 of `taxonomy.md` to pick the tags; use §4 to ensure the
   generator is not over-sampling a primitive.

2. **IRT / grading sub-agent (`domains/arc/grading`)** — for per-primitive
   item difficulty, use the §4 coverage matrix as the canonical primitive ↔
   task family mapping. For per-model coverage reporting, use §7 of
   `taxonomy.md`.

3. **Audit sub-agent (`domains/arc/audit`)** — the gap-analysis in §5 is
   the input for any audit that asks "what primitive is this benchmark
   under-sampling?" The §6 primitives are the suggested remedies.

4. **Human readers** — §2 (taxonomy tree) is the right entry point; §3 is
   read primitive-by-primitive; §4 is the headline artefact; §5 is the
   implications.

---

## Acceptance criteria (per the project spec)

* [x] **12–20 primitives** — 20 (exactly at the upper bound; see §2 of
  `taxonomy.md` for the grouping rationale and §8 for the limit-justification).
* [x] Each primitive has **definition + ≥1 reference + ≥1 ARC example**.
* [x] Primitives are **grouped into clear categories** (six groups).
* [x] **Coverage matrix** is concrete (markdown table with named task
  families and public task IDs).
* [x] **Gap analysis** identifies specific under-served primitives (six
  proposed new primitives, plus model-side blind spots).
* [x] **Bibliography complete** and properly cited (see `bibliography.md`).
* [x] **README** explains how to use the taxonomy (this file).

---

## Limitations

* The taxonomy is **research-grounded but illustrative**, not exhaustive.
  Not every ARC task has been hand-tagged; the matrix uses 10–20 representative
  task IDs per primitive, all publicly verifiable.
* ARC-AGI-2 task IDs are drawn from public Kaggle / forum discussions; the
  official ARC-AGI-2 held-out set is not annotated here.
* The taxonomy labels what *humans* do, not what particular *architectures*
  do. A second-pass annotation could add a module dimension (CNN,
  transformer, symbolic search) to each primitive.

---

## Provenance

This document was produced as part of the agi-kit project, in the working
directory `F:\tmp\agi-kit\infra\taxonomy\`. No collaboration with sibling
sub-agents was performed; the work is self-contained. External sources used
are listed in `bibliography.md`.