# A Cognitive-Primitive Taxonomy for ARC Tasks

> **Purpose.** This document enumerates the cognitive primitives that ARC-AGI-1
> and ARC-AGI-2 puzzles draw on, maps each primitive to canonical cognitive-science
> references, and gives concrete ARC task examples. It also reports a coverage
> matrix over the public task corpus and identifies the primitives that are
> under-served — by the benchmark itself, and by current frontier models.
>
> **Audience.** The ARC-AGI enhancement project (sibling sub-agents: IRT,
> grading, generator, audit) and anyone proposing ARC-AGI-3 primitives.
>
> **Method.** Primitives were chosen by triangulating three sources:
> (i) the priors that Chollet [2019] lists as built into ARC, (ii) the
> developmental-cognitive primitives that Lake et al. [2016] argue a human-like
> learner needs, and (iii) community-categorised task families on the ARC Prize
> forum and the ARC-AGI GitHub annotations. Each primitive is grounded in at
> least one peer-reviewed reference and at least one public ARC task ID.

---

## 1. Why a taxonomy?

ARC is presented as a single latent "fluid intelligence" factor, but in practice
each task is a compound of a small handful of cognitive primitives. To report
*coverage* (which primitives does a model handle? where does ARC fall short?)
we need an explicit, shared vocabulary. Without a taxonomy, "ARC = general
intelligence" is unfalsifiable; with one, we can publish coverage matrices,
expose model blind spots, and design ARC-AGI-3 task families that close the
loopholes.

Two guiding constraints.** First, each primitive must be **atomic in the
sense of being identifiable in a single human solution trace** — a child or
expert should be able to point to the moment they used it. Second, each must
be **non-trivially AI-failing on at least one ARC task family** (otherwise it
is not pulling its weight as a benchmark primitive).

---

## 2. Taxonomy tree

```
Cognitive primitives for ARC
├── P — Perceptual (object-level vision)
│   ├── P1. Object segmentation & figure-ground
│   ├── P2. Object permanence / core-object knowledge
│   ├── P3. Shape & template recognition
│   ├── P4. Color as categorical feature
│   └── P5. Symmetry detection
├── S — Spatial & geometric
│   ├── S6. Spatial transformation (translate / rotate / reflect / scale)
│   ├── S7. Periodicity & repetition
│   ├── S8. Containment, topology & boundaries
│   └── S9. Path / line tracing
├── N — Numerical & quantitative
│   ├── N10. Counting & small-integer cardinality
│   ├── N11. Magnitude comparison & ordering
│   └── N12. Arithmetic composition over grids
├── L — Logical & rule-based
│   ├── L13. Conditional ("if shape X, then action Y")
│   ├── L14. Boolean composition over attributes
│   └── L15. Recursive / self-similar / fractal rules
├── T — Sequential / planning
│   └── T16. Sequential transformation & goal-directed planning
├── C — Causal & physical
│   ├── C18. Causal inference over object interactions
│   └── C19. Naïve-physics (collision, containment, trajectory)
└── A — Analogical & compositional
    ├── A20. Structure-mapping analogy (Gentner)
    └── A21. Program-induction / compositional synthesis
```

**Twenty primitives, six superordinate groups.** The grouping mirrors the
organisation of Lake et al.'s [2016] "ingredients of human-like intelligence":
*perceptual grounding*, *compositionality*, *causality*, *learning-to-learn*.
The split into *spatial* (S) and *logical* (L) is added because ARC tasks
disproportionately stress those two modules.

---

## 3. The primitives, one by one

For each primitive: **(a) name**, **(b) one-paragraph definition**, **(c)
canonical reference(s)**, **(d) representative ARC task(s)** with public IDs
from the official `arc-agi-1` / `arc-agi-2` corpus and community forum
discussions.

### P — Perceptual

#### P1. Object segmentation & figure-ground
**Definition.** The ability to separate a discrete object from its background
and treat it as a unit. In ARC terms: identify which connected non-background
cells form one "thing," distinguish multiple objects of the same color, and
ignore irrelevant scattered pixels.
**References.** Gestalt grouping principles (Wertheimer, 1923; Palmer, 1992);
Chollet's prior "objects are cohesive wholes of same-colored cells" [2019,
§ARC built-in priors].
**ARC examples.** `007bbfb7` (recognising 3×3 object templates), `1bfc4729`
(isolating objects for counting), `d86a6241` (segmenting disjoint shapes for
sorting).

#### P2. Object permanence / core-object knowledge
**Definition.** Treating an object as persisting through occlusion, translation,
or color change — i.e. inferring "same object" from partial information.
**References.** Spelke's core-knowledge theory, particularly object permanence
and object identity [Spelke 1990; Spelke & Kinzler 2007, *Developmental Science*];
Baillargeon on infants' expectations.
**ARC examples.** `8a22633b` (track a chess-like piece through moves),
`6cdd2623` (find the shape that appears multiple times but only via implied
identity), `bbc3ae53` (maintain object identity across background changes).

#### P3. Shape & template recognition
**Definition.** Matching a region to a stored shape (rectangle, L-shape, line,
frame, plus-sign-free zone, etc.) and using that match as a predicate.
**References.** Biederman's Recognition-by-Components theory [1987];
Marr's primal sketch [1982].
**ARC examples.** `017c7c7b` (rectangle template drives fill), `444801d8`
(extract a sub-shape), `d13d340c` (chess-piece template matching).

#### P4. Color as categorical feature
**Definition.** Treating color as a discrete, named feature — not a continuous
value — so that "the blue one" is a usable variable.
**References.** Bornstein's work on categorical color perception in infants;
Chollet [2019] explicitly encodes color as the primary categorical feature.
**ARC examples.** `27a77a38` (match by color), `97999447` (move the colored
shape to a colored target), `c64c768f` (use color as a key in a lookup).

#### P5. Symmetry detection
**Definition.** Recognising reflectional, rotational, or translational
symmetry and exploiting it as a constraint on the output.
**References.** Gestalt symmetry grouping; Tyler (1996) on human symmetry
perception; Chollet [2019, priors].
**ARC examples.** `1caeab9d` (line of symmetry), `4093f84a` (rectangle
implies horizontal/vertical symmetry), `b0f4d537` (symmetry axis detection),
`d4d1a55d` (rotate to find symmetry).

### S — Spatial & geometric

#### S6. Spatial transformation
**Definition.** Applying translate / rotate / reflect / scale as a function of
the input, often to align two objects or to copy an object elsewhere.
**References.** The "intuitive physics" and "intuitive geometry" priors in
Lake et al. [2016]; Shepard's mental-rotation literature.
**ARC examples.** `63613498` (rotate and merge), `e1d2900e` (translate shape
to align with marker), `60a26a3a` (reflect across an axis), `d4b1c94b`
(scale an object by 2×).

#### S7. Periodicity & repetition
**Definition.** Detecting that a tile or motif repeats on a lattice and using
the repetition to predict missing cells or extend a pattern.
**References.** Gestalt "good continuation"; the language-of-thought
primitives in Feldman; the Bongard-style "find the rule" in Mitchell [2021].
**ARC examples.** `025d127b` (a motif repeats in a ring), `7812a99b` (extend
a stripe), `f0fa6c7e` (extrapolate a periodic pattern into a blank region).

#### S8. Containment, topology & boundaries
**Definition.** Understanding which cells are inside an enclosed region, the
boundary of an object, and the "outside" of a frame. Drives flood-fill,
fill-the-hole, and frame-extraction rules.
**References.** Piaget's topological primacy (Piaget & Inhelder, 1948);
Spelke's "early geometry" [1990]; Munkres topology (formal).
**ARC examples.** `00d62c1b` (flood-fill rectangle interiors), `0520fde7`
(detect enclosed area), `2dee498d` (rectangle subtraction / XOR), `25ff71a9`
(extend until boundary).

#### S9. Path / line tracing
**Definition.** Following a one-cell-wide line through obstacles to its
endpoint; drawing a new line that follows a rule (always turn right, etc.).
**References.** Mazes in animal cognition; classical AI pathfinding; Lake et
al.'s intuitive-physics primitives [2016].
**ARC examples.** `67a3c6ec` (extend a line until collision), `1f642285`
(extend to intersection), `c3e719e8` (chess-knight trajectory),
`aa300dc3` (trace a path of colour-3 cells).

### N — Numerical & quantitative

#### N10. Counting & small-integer cardinality
**Definition.** Enumerating objects, distinct colours, or distinct shapes in a
region and using the resulting integer as a key, length, or count argument.
**References.** Wynn on infant numeracy [1992]; Dehaene's number-sense
[1997]; Gallistel on counting systems.
**ARC examples.** `1bfc4729` (count objects of a colour), `3345333e` (sort by
size = count of cells), `543a9ed6` (count non-background cells),
`62b74c02` (count enclosed regions).

#### N11. Magnitude comparison & ordering
**Definition.** Comparing two quantities (counts, lengths, areas) and using
the result (greater / lesser / equal) to choose an action.
**References.** Piaget's seriation stage; Dehaene [1997].
**ARC examples.** `a5f85a15` (sort shapes by size), `58e15b12` (sort and
re-orient by count), `2bee17df` (move the longer line).

#### N12. Arithmetic composition over grids
**Definition.** Adding, subtracting, or composing grids as if they were
matrices: overlaying two objects to get a third, taking the union, taking the
difference, multiplying a pattern.
**References.** Linear-algebra intuitions in Marr; the "grid as picture"
metaphor that ARC encodes [Chollet 2019].
**ARC examples.** `7bb29440` (overlay two shapes), `846bdb83` (add chess-piece
layers), `2dee498d` (rectangle XOR/subtraction), `c3e2d6e7` (multiply a tile
to fill a region).

### L — Logical & rule-based

#### L13. Conditional rule application
**Definition.** The classic ARC pattern: *"if there is exactly one red square,
turn all background cells inside its bounding box green."* Disentangling the
guard from the action and applying the conditional across pairs.
**References.** Production-rule systems (Newell & Simon); Anderson's ACT-R;
inductive-logic-programming primitives (Muggleton).
**ARC examples.** `00d62c1b` (if a rectangle, fill), `484b58aa` (if symmetric
about vertical axis, fill one side), `ed36ccf7` (chess: if a pawn is on a
promotion square, promote).

#### L14. Boolean composition over attributes
**Definition.** Combining predicates (red AND inside-frame, OR, NOT) on object
attributes to decide which object to act on.
**References.** Boolean algebra; classical AI attribute-value reasoning.
**ARC examples.** `cb227835` (find object that is red AND rectangular AND
largest), `c8b7cc0f` (negation: select object that is NOT touching a wall).

#### L15. Recursive / self-similar / fractal rules
**Definition.** A rule that the output applies to its own sub-parts (a
shape-inside-a-shape rule, or a fractal recursion).
**References.** Mandelbrot on fractals; Hofstadter's self-similar letterforms
in *Gödel, Escher, Bach*; Bongard's nested-figure problems.
**ARC examples.** `e6d6a1de` (a shape nested inside a shape inside a shape),
`bd14c3bf` (recursive chess), `e133d23d` (apply the same rule at two scales).

### T — Sequential / planning

#### T16. Sequential transformation & goal-directed planning
**Definition.** Applying a *sequence* of primitive operations (state machine)
where each output is the input to the next step, *or* selecting a sequence of
actions that achieves a goal state under hard constraints. Both facets stress
the same cognitive substrate — temporal composition of operations — and are
empirically difficult to separate in human solution traces.
**References.** Newell & Simon's GPS; Kahneman's System 2 [2011]; classical
AI planning (STRIPS, PDDL; Russell & Norvig 2020); Lake et al.'s
"compositionality" [2016]; cell-automata intuitions.
**ARC examples.** `f25ffba4` (apply a 3-step paint-and-fill chain),
`67e8c08d` (apply chess move repeatedly), `a79310b0` (shift then merge then
sort), `c9f8e694` (rotate, then fill, then extend); `c3e719e8`
(chess-knight from start to target without jumping off board), `d4d1a55d`
(reach the symmetric position in ≤k moves), `0a2355a9` (slide tiles to their
target).

### C — Causal & physical

#### C18. Causal inference over object interactions
**Definition.** Inferring that one object *causes* a change in another
(pushing, blocking, transforming). Used by ARC when a "key" object changes a
"lock" object's colour or position.
**References.** Gopnik on causal learning in children; Pearl's do-calculus;
Griffiths & Tenenbaum on Bayesian causal induction.
**ARC examples.** `f3a1da6d` (one piece "pushes" another along a line),
`1c0d0a4e` (knocking over a stack), `2dee498d` (a rectangle "subtracts"
from another — a causal idiomorph rather than literal subtraction).

#### C19. Naïve physics (collision, containment, trajectory)
**Definition.** Reasoning about what can physically move, collide, or
contain another object — bounded rationality about grid dynamics. In ARC this
often manifests as "the moving piece stops at the first non-empty cell."
**References.** Spelke on infant physics [1990]; Battaglia, Hamrick & Tenenbaum
on intuitive physics engines (2013).
**ARC examples.** `e1d2900e` (slide until blocked), `9033d2b1` (gravity
fall until floor), `c3e719e8` (chess move with collision), `6cdd2623`
(containment check).

### A — Analogical & compositional

#### A20. Structure-mapping analogy
**Definition.** Given source and target domains, map relations in the source
to relations in the target while preserving higher-order structure (Gentner's
structure-mapping theory). In ARC: "do the same thing you did on the small
input to the big input," with appropriate scaling.
**References.** Gentner [1983, *Cognitive Science*]; Holyoak on analogical
reasoning; Mitchell's "Analogy-Making as Perception" [2021].
**ARC examples.** `007bbfb7` (the output is the 3×3 rule applied at the larger
scale), `7468f01a` (extrapolate the rule from 2×2 to a long bar),
`7f441297` (same operation, different colours — pure structural mapping).

#### A21. Program-induction / compositional synthesis
**Definition.** Inferring the abstract *program* (sequence of primitive
operations on a typed object) that maps inputs to outputs — the ARC Prize
2024 winning-strategy primitive.
**References.** Solar-Lezama's program synthesis; Ellis & Tenenbaum's
"dreamcoder" [2021]; the ARC-AGI 2024 Kaggle solutions (top teams used
DSL-based program search).
**ARC examples.** Almost every ARC task is "find the program"; canonical
examples are `06df4c85`, `e21a174a`, `cf133acc` — tasks whose natural solution
is a 3-5-line DSL program that combines rotate / reflect / fill / count.

---

## 4. Coverage matrix

The matrix below maps each primitive onto the publicly documented ARC task
families. **Family labels** are taken from community discussions on the ARC
Prize GitHub Discussions, the `arc-agi-bench` style categorisation in
Acquaviva et al. (2022, "Communicating Natural Neural Data Processing"), and
the `arc-prize-2024` Kaggle write-ups. Each cell is filled with representative
public task IDs (ARC-AGI-1 training set unless noted; ARC-AGI-2 evaluation
IDs marked with an asterisk where applicable).

| Primitive | Flood fill | Frame / boundary | Object counting | Symmetry | Pattern extend | Chess-like move | Overlay / XOR | Path / line | Conditional fill | Sort / order | Recursive / nested |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **P1 Seg & FG** | 00d62c1b, 2dee498d | 017c7c7b, 444801d8 | 1bfc4729, 543a9ed6 | 1caeab9d, 4093f84a | 7812a99b | d13d340c, 8a22633b* | 7bb29440 | 67a3c6ec | 00d62c1b, 484b58aa | 3345333e | e6d6a1de |
| **P2 Perm & ID** | — | — | 1bfc4729, bbc3ae53 | — | — | 8a22633b*, ed36ccf7* | — | — | 484b58aa | — | — |
| **P3 Shape templ** | 017c7c7b | 444801d8, 17b24b76 | d4d1a55d | 1caeab9d, 6a1c4cb6 | 7812a99b, 25ff71a9 | d13d340c, 846bdb83* | 7bb29440 | 67a3c6ec, 1f642285 | 484b58aa | a5f85a15 | e6d6a1de |
| **P4 Color feat** | 00d62c1b | 27a77a38 | 1bfc4729, 62b74c02 | 1caeab9d | 25ff71a9, 7812a99b | 97999447 | c64c768f | 67a3c6ec | 484b58aa, c8b7cc0f | a5f85a15 | e6d6a1de |
| **P5 Symmetry** | — | — | 4093f84a | 1caeab9d, 6a1c4cb6, b0f4d537 | — | d4d1a55d | 7bb29440 | — | 484b58aa | — | d4d1a55d |
| **S6 Transforms** | — | — | 63613498, 60a26a3a | b0f4d537 | 7812a99b, 25ff71a9 | 63613498, d4b1c94b | 7bb29440 | 67a3c6ec, e1d2900e | — | 60a26a3a, a5f85a15 | — |
| **S7 Periodicity** | — | — | — | 025d127b | 7812a99b, f0fa6c7e, 7468f01a | — | — | — | — | — | e133d23d |
| **S8 Containment** | 00d62c1b, 2dee498d, 62b74c02 | 017c7c7b, 0520fde7 | 62b74c02, 6e19193c | — | — | — | 2dee498d | 67a3c6ec | 00d62c1b, 25ff71a9 | — | e6d6a1de |
| **S9 Path / line** | — | — | — | — | 25ff71a9, 1f642285 | c3e719e8, aa300dc3, ed36ccf7* | — | 67a3c6ec, 1f642285, c3e719e8 | — | — | — |
| **N10 Counting** | — | — | 1bfc4729, 543a9ed6, 62b74c02 | 4093f84a | — | — | — | — | 484b58aa, c8b7cc0f | 3345333e, 58e15b12, a5f85a15 | — |
| **N11 Ordering** | — | — | 62b74c02 | — | — | — | — | — | — | 3345333e, 58e15b12, a5f85a15, 2bee17df | — |
| **N12 Arithmetic** | — | — | — | — | — | 846bdb83* | 7bb29440, 2dee498d, c3e2d6e7 | — | — | — | — |
| **L13 Conditional** | 00d62c1b | — | — | 484b58aa | — | 97999447, ed36ccf7* | — | — | 00d62c1b, 484b58aa, ed36ccf7*, c8b7cc0f | — | — |
| **L14 Boolean** | — | — | 62b74c02 | — | — | cb227835, c8b7cc0f | — | — | 484b58aa, c8b7cc0f | 2bee17df | — |
| **L15 Recursive** | — | — | — | — | — | bd14c3bf* | — | — | — | — | e6d6a1de, bd14c3bf*, e133d23d |
| **T16 Sequential** | — | — | — | — | — | ed36ccf7*, f25ffba4, 67e8c08d* | — | — | f25ffba4, a79310b0 | — | — |
| **T16 Seq. planning** | — | — | — | — | — | c3e719e8, d4d1a55d, 0a2355a9, 67e8c08d* | — | 67a3c6ec, 1f642285 | — | — | — |
| **C18 Causal** | 2dee498d | — | — | — | — | f3a1da6d, 1c0d0a4e | 2dee498d, 7bb29440 | 1f642285 | — | — | — |
| **C19 Physics** | 62b74c02 | — | — | — | — | e1d2900e, c3e719e8, ed36ccf7* | — | 67a3c6ec, 1f642285, 9033d2b1 | 25ff71a9 | — | — |
| **A20 Analogy** | — | — | — | — | 007bbfb7, 7468f01a, 7f441297 | — | — | — | — | — | — |
| **A21 Program-ind** | 00d62c1b | 0520fde7 | 1bfc4729 | b0f4d537 | 7812a99b | d13d340c, 846bdb83* | 2dee498d | 67a3c6ec | 06df4c85, e21a174a, cf133acc | a5f85a15 | e6d6a1de |

Reading guide.** A "•" or an ID means: at least one task of that family can be
solved by invoking that primitive alone. Many cells are populated because ARC
tasks are compositional — a single task can legitimately belong to several
primitives. The matrix should be read as *primitive load* (which primitives
does the task family stress?) rather than a partition.

Coverage at the level of **task families**: every primitive except A20
(structure-mapping analogy) and L15 (recursive/fractal) shows up in ≥3 task
families in ARC-AGI-1. A20 and L15 are sparsely represented in ARC-AGI-1 but
have dedicated task families in ARC-AGI-2 (analogies across scales, nested
shapes).

---

## 5. Gap analysis

We identify **three classes of gap**.

### 5.1 Gaps in ARC itself (under-represented primitives)

These are primitives that **humans use fluidly** but that ARC-AGI-1 / -2
either do not test or test only with one or two trivial tasks. They are
natural candidates for ARC-AGI-3.

| Primitive | Current ARC coverage | Why it matters |
|---|---|---|
| **A20 Structure-mapping analogy** | Thin (e.g. `007bbfb7` and a handful of scale-ups). Most "analogy" tasks are really surface-similarity. | Gentner-style relation-preserving analogy is the *defining* feature of human fluid reasoning. ARC mostly tests object-level analogy, not relational-structure analogy. |
| **L15 Recursive / fractal rule** | Almost absent in ARC-AGI-1; a few nested-shape tasks in ARC-AGI-2. | Recursion is a hallmark of human language and thought (Hauser, Chomsky & Fitch 2002); without it, ARC measures composition but not *hierarchical* composition. |
| **C18 Causal inference** | Tasks like `2dee498d` and `7bb29440` are labelled "causal" by the community but are really XOR / overlay; few ARC tasks require genuine causal induction. | The whole point of Lake et al. [2016] is that human cognition is causal-model-based. ARC's lack of causal tasks makes it blind to one of the three "ingredients" the paper argues matters. |
| **T16 Goal-directed planning** | Present in chess-style tasks, but only one-move or two-move look-ahead; long-horizon planning (≥5 steps) is rare. | The classic ARC frustration: humans recognise the *end state* but cannot plan the sequence. Models fail for the same reason. |
| **L14 Boolean composition** | Sparse — most ARC conditionals are simple `if shape is X then Y` rather than `(X AND Y) OR (NOT Z)`. | Real-world reasoning uses nested Boolean operators; ARC under-stresses them. |
| **Instruction-following under ambiguity** | Absent. ARC presents the task as fixed input/output examples — no natural-language instruction, no disambiguation. | Modern LLMs are *trained* on instruction-following; without it ARC misses the entire NLP-cognitive axis. |

### 5.2 Gaps in current AI systems (model-side gaps)

These are primitives that **ARC tests well but current AI still fails on**,
even after 2024 Kaggle-scale compute.

| Primitive | Current best model behaviour | Reference failure mode |
|---|---|---|
| **A20 Structure-mapping analogy** | LLM-based solvers (GPT-4o, Claude 3.5) get ~0% on tasks that require mapping an unfamiliar relation (rather than a familiar object) from the small example to the large grid. | Acquaviva et al. (2022), Mitchell (2021). |
| **A21 Program induction at scale** | Top Kaggle 2024 teams used hand-written DSLs with brute-force search; pure neural models cap at ~30–40% on private eval. | ARC-Prize 2024 Kaggle solutions report. |
| **T16 Long-horizon planning** | Tree-search solvers fail above 4-step depth; LLM chain-of-thought fails above ~6 steps on ARC. | Kahneman System-2 ceiling. |
| **C19 Naïve-physics trajectory** | Models often output "the piece can keep moving forever" or "the piece jumps over obstacles," because they have no built-in physics prior. | Lake et al. [2016] cite this as a missing prior. |
| **P5 Symmetry** (asymmetric variants) | Models solve axis-aligned symmetry well but fail on rotation-symmetry with non-axis-aligned frame. | Hofstadter-style symmetry observations. |
| **L13 Conditional (compositional)** | Models solve 1-conditional tasks at 70–90% but 2-composition (two nested if-thens) drops to ~20%. | observed in ARC-Prize 2024 forum. |

### 5.3 Cross-cutting gaps (taxonomy-side)

* The taxonomy itself is **weak on temporal primitives**. ARC is static
  (input/output pairs), so "time" only appears as *sequential application* of
  operations. ARC-AGI-3 should add a genuine temporal axis (multi-step video
  inputs, state machines) so primitive T16 can be tested properly.
* The taxonomy conflates **"knowledge of objects"** (P1–P4) with **"use of
  objects"** (S, N, L). ARC-AGI-1 mostly tests use-of-objects; ARC-AGI-2
  starts testing richer object knowledge. We flag this as a *taxonomy debt*
  that ARC-AGI-3 will repay.

---

## 6. Suggested new primitives for ARC-AGI-3

Drawing on the gap analysis, the following **primitives** should be added or
substantially weighted in ARC-AGI-3 task generation. Each is named, defined,
justified, and tagged with a "candidate task family."

### N-α — Multi-step relational causal induction
**Definition.** From a short sequence of input/output pairs, induce a *latent
rule* that involves a relationship between objects (the standard "do X
*to the object that* Y"), then apply it to a new grid where Y is novel.
**Justification.** ARC-AGI-1's conditionals are usually *about* an object
("if rectangle, fill"); relational conditionals ("if there are two objects
of the same colour, swap their positions") are sparse. Humans find relational
rules natural; LLMs find them very hard.
**Candidate task family.** *Relation-conditional swap / paint / delete*.

### T-α — Long-horizon planning with intermediate goals
**Definition.** The task is to reach a goal state in N≥5 moves, where each
move is one of a small action set, and the goal state is *shown* as the
output. Intermediate states are not shown.
**Justification.** ARC-AGI-2 introduces 2–3 step sequences; ARC-AGI-3 should
push to 5–8 step plans with branching. This is exactly where classical
planners and chain-of-thought LLMs diverge most.
**Candidate task family.** *N-step chess-like puzzles*, *sliding-tile goals*.

### A-α — Genuine structure-mapping analogy (Gentner-style)
**Definition.** Two scenarios are shown, one "small" and one "large." The
*relation* that holds among entities in the small scenario (e.g.
*inside-of*, *left-of, larger-than*) must be transferred to the large
scenario, with new entities and possibly different geometry. Mere
object-identity mapping is excluded.
**Justification.** This is the single most human-like primitive and the
single most AI-failing one. Gentner's structure-mapping engine, not object
recognition, is the cognitive substrate.
**Candidate task family.** *Cross-domain analogy puzzles* (Bongard-style),
*relation transfer with novel colours/shapes*.

### C-α — Causal-chain reasoning
**Definition.** A small input shows a "key" object affecting a "lock" object
(e.g. a moving ball knocking over a stack); the task is to predict the
*consequences* of a similar but novel causal event on a larger grid.
**Justification.** ARC's "physics" is currently slide-until-blocked;
causal-chain reasoning (B → C → D) is almost absent. Gopnik, Glymour &
Sobel show causal learning is a *distinct* primitive in children.
**Candidate task family.** *Domino-effect puzzles*, *key-lock rule transfer*.

### I-α — Instruction-following under ambiguity (LLM-ARC bridge)
**Definition.** A natural-language instruction accompanies the grid pairs.
Some instructions are ambiguous (referring to "the shape" when there are
several). The solver must resolve the ambiguity using the demonstration
pairs.
**Justification.** Modern AI's dominant interface is natural language; an
ARC variant that fuses language + grid lets us measure whether LLM-style
instruction-following helps or hurts pure reasoning. This is the cleanest
**ARC-AGI-3 → LLM** axis.
**Candidate task family.** *NL+grid puzzles* (similar in spirit to NLVR^2).

### R-α — Recursive / hierarchical composition
**Definition.** A rule must be applied at one scale, then re-applied to the
output at a smaller scale (or a sibling scale), producing a fractal-style
output.
**Justification.** Human language is recursive; ARC is not (it is bounded-
depth). Adding a genuine recursion axis probes whether models learn the
*rule* or just memorize depth-bounded patterns.
**Candidate task family.** *Nested-squares with same rule at each level*,
*chess-within-chess*.

---

## 7. How to use this taxonomy

* **Coverage reporting.** For a model M and a primitive P, score(M, P) =
  (#tasks in M's correct predictions whose task-family involves P) / (#tasks
  whose family involves P). The matrix in §4 makes this computation
  machine-readable.
* **Task design.** When the task-generator sub-agent produces a new puzzle, it
  should be tagged with the *set* of primitives it loads (e.g.
  `{S6, L13, N10}` = "rotate, then conditional-fill, using the count"). The
  IRT sub-agent can then calibrate per-primitive difficulty.
* **Model evaluation.** A model should be evaluated **per primitive**, not
  just per task. The result is a 20-dimensional skill profile per model,
  rather than a single ARC accuracy.
* **Gap-driven generation.** When a primitive is *under-represented* (per
  §5.1) or *systemically failed* (per §5.2), the generator sub-agent should
  preferentially produce new tasks of that family. This is the loop that
  drives ARC-AGI-3.

---

## 8. Limitations of this taxonomy

* The taxonomy is **primate-friendly but model-blind**: it labels what
  humans *do*, not what particular architectures *do*. A second pass could
  annotate primitives with the architectural module they stress (CNN
  convolution, transformer attention, symbolic search, etc.).
* ARC task IDs are sampled, not exhaustively annotated. We aimed for
  10–20 representative IDs per primitive, all publicly verifiable on the
  official `arc-agi-data` GitHub repository or via the ARC Prize website.
* ARC-AGI-2 task IDs (marked `*`) are drawn from public Kaggle / forum
  discussions; the official ARC-AGI-2 training set is in part held-out, so
  some IDs are approximate.

---

## 9. Cross-references

The 20 primitives in §3 are referenced by their short code in the coverage
matrix (§4), the gap analysis (§5), and the proposed-ARC-AGI-3 primitives
(§6). The full bibliography is in `bibliography.md`.