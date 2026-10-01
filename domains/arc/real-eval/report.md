# domains/arc/real-eval — CLAgent on the public ARC-AGI-1 corpus

**Snapshot of the agent under test:** `snapshot/agent/` (frozen at the
time of the original evaluation; SHA-256 / copy-time captured in
`snapshot_timestamp.txt`). The snapshot was captured under the previous
`psf-clagent/` directory name and intentionally keeps that internal layout
so it can re-run on the same code that produced the original numbers.
**Corpus:** public ARC-AGI-1, 800 tasks (400 training + 400 evaluation),
downloaded from `github.com/fchollet/ARC-AGI`. License: Apache-2.0.
**Default subset evaluated:** first 100 training + first 50 evaluation = 150
tasks (configurable via `--limit`).
**Reasoner:** template (no `OPENAI_API_KEY` required). The LLM path is wired
through `--reasoner llm` and was not exercised here.

---

## 1. Headline numbers

| metric                                        | value         |
| --------------------------------------------- | ------------: |
| tasks downloaded                              | 800 (400+400) |
| tasks evaluated by CLAgent                    | 150           |
| tasks audited (8 shallow heuristics)          | 150           |
| tasks graded (A3S grader)                     | 150           |
| **shallow-exploitable rate (THE headline)**   | **0.00 %**    |
| tier-1 solve rate (agent)                     | 0.00 %        |
| tier-2 solve rate (agent, palette-invariant)  | 0.67 %        |
| tier-3 solve rate (agent, structural)         | 58.00 %       |
| tier-1 solve rate (baseline echo)             | 0.00 %        |
| tier-1 rate on the 16 generated tasks         | 75.00 %       |
| IRT 2PL — family difficulty range (b)         | −1.30 … +1.81 |
| IRT 2PL — solver ability θ (mean)             | ≈ +0.01       |
| total wall-clock for the 150-task eval        | ≈ 1.0 s       |

**Interpretation.** The 0 % shallow-exploitable rate validates the ARC-AGI-1
corpus as a real reasoning test: not a single task on this 150-task slice was
solved exactly by any of the 8 trivial heuristics (identity, palette-majority,
mirror, largest-object, background-swap, diagonal-replicate, single-color-fill,
palette-invert). That is exactly the property the corpus is supposed to have.

The 0 % tier-1 solve rate, in contrast, is a *negative* signal for the agent:
on the *generated* 16-task benchmark we ship with the agent (which was used to
write the README's "75 % tier-1" claim), three of four synthetic families
(`count_colors`, `rotate_largest`, `symmetry_complete`) are solved perfectly.
On the public corpus, **none of the 150 tasks is solved exactly**, and every
single run falls back to the identity program after exhausting 15 candidate
templates. The 58 % tier-3 partial-credit rate is mostly an artefact of the
fallback: returning the test input verbatim scores ≥ 0.6 cell-match on any
task whose output is "mostly the same as the input" — and many ARC tasks are
exactly that. The grader confirms the agent offers **no lift over the
echo-input baseline** (0.000 average score delta).

---

## 2. Comparison vs the 16 generated tasks

| metric                         | 16 generated tasks | 150 real ARC-AGI-1 tasks |
| ------------------------------ | ------------------ | ----------------------- |
| tier-1 solve rate               | **75.0 %**         | **0.0 %**              |
| tier-2 solve rate              | 75.0 %             | 0.67 %                 |
| tier-3 partial rate            | 100.0 %            | 58.0 %                 |
| shallow-exploitable rate (aud) | 0 / 16             | 0 / 150                |
| avg attempts per task          | 15                 | 15                     |
| agent committed "unknown"      | 0 / 16             | **150 / 150**          |

By-family on the generated tasks:

```
  count_colors             n=4  t1=4 (100%)   ← template exists
  fill_enclosed            n=4  t1=0 (  0%)   ← no template (intentional gap)
  rotate_largest           n=4  t1=4 (100%)   ← template exists
  symmetry_complete        n=4  t1=4 (100%)   ← template exists
```

**The key insight.** The 75 % headline on the generated corpus was not a
general ARC result — it was "the agent already has a hand-written template for
3 of 4 families we hand-built". The fourth family (`fill_enclosed`) was
deliberately left uncovered to motivate v2 work, and is exactly where the
agent already collapsed to identity on the *generated* corpus as well. On
ARC-AGI-1 there are no "designed-for-the-templates" tasks at all, so the agent
falls back to identity on every single one.

The gap between 75 % and 0 % is therefore not a bug — it is the **template
library's coverage gap**, exposed for the first time on a corpus the templates
were not designed for. This is the headline finding for the v2 worker.

---

## 3. Per-task-family breakdown (real ARC-AGI-1)

The 150-task subset partitions cleanly into 4 coarse families by
`input_shape == output_shape` × palette size (see `run_real_eval._infer_family`):

| family                          | n   | t1 | t2 | t3  | t1_rate | t3_rate |
| ------------------------------- | --: | -: | -: | --: | ------: | ------: |
| `same_shape_mid_palette`         |  17 |  0 |  0 |  14 |  0.00 % | 82.4 %  |
| `same_shape_rich_palette`       |  75 |  0 |  1 |  60 |  0.00 % | 80.0 %  |
| `same_shape_small_palette`      |  16 |  0 |  0 |  13 |  0.00 % | 81.2 %  |
| `size_change`                   |  42 |  0 |  0 |   0 |  0.00 % |  0.0 %  |
| **total**                       | 150 |  0 |  1 |  87 |  0.00 % | 58.0 %  |

IRT 2PL (response = tier-3, 6 synthetic replicates of the single solver):

| family                          | difficulty b | discrimination a |
| ------------------------------- | -----------: | ----------------: |
| `same_shape_mid_palette`        | −1.30        | 1.01              |
| `same_shape_rich_palette`       | −0.32        | 2.58              |
| `same_shape_small_palette`      | −0.32        | 2.58              |
| `size_change`                   | +1.81        | 1.97              |

* IRT is degenerate on `tier1` (no family has any pass), so we used
  `tier3` as the binary response. The fit is honest about being a single-solver
  bootstrap; see `run_irt.py:_build_response_matrix`.
* `size_change` is unambiguously the hardest family (b = +1.81) — it requires
  picking output dimensions, which the template proposer cannot do.
* `same_shape_mid_palette` is the easiest (b = −1.30) — small enough palette and
  preserved shape that identity-fallback often overlaps the truth by chance.
* Discrimination `a` is high (> 2.5) for two of the families, indicating the
  ICC slope is steep: a small bump in ability would swing pass rate a lot.
  The agent's θ is centred near 0, so it sits on the lower part of those ICCs.

---

## 4. Failure modes (qualitative)

Looking at the per-task traces in `outputs/real_eval_log.json`, three
qualitative failure patterns dominate. Each is a concrete, fixable deficiency
in the current DSL/template library.

### 4.1 The "output shape is different from input" gap (42 / 150 tasks)

Every `size_change` task ends with the agent returning the test input
unchanged, which immediately fails the tier-3 cell-match check because the
output grid has different dimensions. The current DSL has no primitives for
*resize*, *tile*, *crop*, *interleave* — all of which are routine ARC
operations.

Concrete examples in our subset:
`00576224`, `007bbfb7`, `017c7c7b`, `0520fde7`, `0692e18c`, `0934a4d8`,
`0a1d4ef5`, `0b148d64`, `0bb8deee`, `0c786b71`. Most of these require the
output to be a function of the *count*, *bounding box*, or *spatial layout*
of objects in the input.

### 4.2 The "object count" gap

ARC-AGI-1 leans heavily on tasks where the rule is "draw N copies of the
input object" or "draw a line of length N", where N is the number of distinct
non-background cells. The DSL has no `count_objects` primitive, no `line_of`,
no `tile_n`. The template proposer's `count_objects`-style templates don't
exist for the public corpus's distribution.

### 4.3 The "colour permutation + recolour by region" gap

Many ARC-AGI-1 tasks recolour input cells based on their position (e.g. "the
topmost row becomes red"). The current `recolor` primitive is
position-agnostic; there is no `recolor_by_row`, `recolor_by_col`,
`recolor_by_distance_from_*`, etc.

### 4.4 The "rule uses *all* demonstration pairs simultaneously" gap

ARC tasks almost always require the agent to infer a rule that is *consistent
across every demonstration pair*. The template proposer proposes K programs,
keeps the ones that pass all pairs, then picks one — but its K=20 set is too
small and too narrow (it draws from a fixed library). On 16 generated tasks
the library happened to include the right templates for 3/4 families; on the
real corpus it does not. The fix is either (a) a much larger / learned
template library or (b) the LLM reasoner that can synthesise novel programs
on the fly (only the latter scales to open-ended ARC).

### 4.5 Audit-flag side-effect

A secondary finding: on every real-ARC run, `audit_flagged = true` because the
agent's identity fallback coincides with the `identity_heuristic` from
`domains/arc/audit/heuristics.py`. This is by design (the audit gate is supposed to
catch "the agent did nothing useful"), but it has the side effect of zeroing
the agent's reported `confidence` on every real-ARC task — making the
confidence trace uninformative as a calibration signal. v2 should decouple
"matches a trivial heuristic" from "low confidence": the two are not the
same thing.

---

## 5. Recommendations for next-iteration (CLAgent v2)

In priority order, each mapped to the failure mode it addresses:

1. **Add a `count_objects` primitive and a small `tile_n` / `line_of_n`
   template family.** This unlocks an estimated 15–25 % of ARC-AGI-1
   (`size_change` plus many same-shape tasks whose rule is "repeat the
   object N times"). Failure modes §4.1 and §4.2.
2. **Add `recolor_by_row`, `recolor_by_col`, `recolor_by_distance_from_*`.**
   Covers the colour-by-position family. Failure mode §4.3.
3. **Replace the static-template library with a learned / neural program
   synthesis step.** Failure mode §4.4. Even a small code-LM in the loop
   would let the agent propose programs that aren't in the hand-written
   library; the wiring already exists in `LLMProposer` (gated on
   `OPENAI_API_KEY`).
4. **Decouple the audit-flag check from the confidence computation.** A
   flagged prediction should *demote* the committed answer, not zero out the
   confidence trace. Failure mode §4.5.
5. **Increase K and add an "exhaustive library of compositions" reflex.**
   The current `_reflect` step only doubles K and adds ~6 composites.
   A wider search would help when the rule is in the long tail of the
   template space.

Items (1) and (2) are pure-DSL additions and could be shipped in v2.1
without LLM dependency. Items (3) and (5) require either a working code-LM
client or a substantially larger hand-written library. Item (4) is a
diagnostic improvement.

---

## 6. Reproducibility

* Snapshot: `snapshot/agent/` (frozen at start; do not edit; the
  internal `snapshot/` tree still uses the original `psf-clagent/`
  directory name so re-running the historical commands yields the same
  output).
* Data: `data/arc-agi-1/` (Apache-2.0; SHA-256 in `data/README.md`).
* Outputs:
    * `outputs/real_eval_log.json` — per-task agent results (150 records)
    * `outputs/audit_log.json`     — per-task shallow-audit results
    * `outputs/grading_log.json`   — per-task A3S grader results
    * `outputs/irt_report.json`    — IRT 2PL parameters + per-family curves
    * `outputs/plots/irt_families.png` — IRT figure (per-family ICCs +
      family-difficulty scatter)
* Driver scripts:
    * `run_real_eval.py --limit N` (default 150; `--reasoner llm` for LLM)
    * `run_audit.py --n-train X --n-eval Y`
    * `run_grading.py`
    * `run_irt.py --response-field tier1|tier2|tier3` (default tier3)

All four scripts are idempotent and tolerant of malformed tasks (they skip +
log; they do not crash). Re-running the pipeline with `--limit 800` covers
the entire public corpus without code changes.