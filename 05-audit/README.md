# 05-audit — adversarial audit harness for ARC tasks

This module is a small, bounded adversarial audit for ARC tasks. It implements a
battery of *shallow* heuristics — solvers that ignore the training pairs and
just produce a guess from the test input alone — and asks:

> Does **any** shallow heuristic exactly match the published test output?

If yes, the task is *trivially solvable*: it does not really test abstract
reasoning. The harness flags such tasks so downstream stages (generator,
grading, leaderboard) can deprioritize or remove them.

## Layout

    F:\tmp\arc-enhance\05-audit\
    ├── heuristics.py          # 8 shallow heuristics + registry
    ├── audit.py               # harness: load -> run -> compare -> report
    ├── synthetic_tasks.py     # 9 hand-rolled ARC-style tasks
    ├── test_heuristics.py     # unit tests (17 tests, all green)
    └── README.md              # this file

## Heuristics

All heuristics share the signature `predict(train_pairs, test_input) -> grid`.
They deliberately ignore `train_pairs` so they cannot infer the real rule —
that is the whole point: if the test output is reachable from the test input
by any of these blind maps, it is shallow.

| name                    | what it does                                                   | rationale                                                  |
| ----------------------- | -------------------------------------------------------------- | ---------------------------------------------------------- |
| `identity`              | returns the input unchanged                                    | catches tasks that publish the input as output             |
| `palette_majority`      | fills the output with the most common color                    | catches uniform-fill / majority-color tasks                |
| `mirror`                | flips the input horizontally                                   | catches left-right symmetry tasks                         |
| `largest_object`        | keeps only the biggest connected non-background component      | catches blob-extraction tasks                              |
| `background_swap`       | swaps background color with the rarest non-background color     | catches simple two-color role swaps                        |
| `diagonal_replicate`    | tiles the input into a 2×2 block grid                          | catches repetition / tiling tasks                          |
| `single_color_fill`     | fills the output with the count of distinct colors              | catches count -> color tasks                               |
| `palette_invert`        | maps `c -> 10 - c` (with `0 <-> 9` boundary)                   | catches global palette inversion                           |

Each heuristic is deterministic, raises no exceptions on the bundled tasks,
and runs in well under a millisecond per call.

## Audit harness

`audit.py` exposes two functions:

* `audit_task(task)` — run all heuristics against one task, return
  `{task_id, trivially_solvable, solvers_hit, per_heuristic}`.
* `audit_tasks(tasks)` — aggregate over many tasks; return per-heuristic
  accuracy, total hit counts, and the per-task results.

Run on the bundled synthetic tasks:

    $ python audit.py

Expected output (truncated):

    Audit summary across 9 task(s)
    Trivially-solvable tasks: 7 / 9

    Per-heuristic accuracy:
      identity                 1/9    ( 11.1%)
      palette_majority         1/9    ( 11.1%)
      mirror                   1/9    ( 11.1%)
      largest_object           1/9    ( 11.1%)
      background_swap          1/9    ( 11.1%)
      diagonal_replicate       1/9    ( 11.1%)
      single_color_fill        0/9    (  0.0%)
      palette_invert           1/9    ( 11.1%)

    Per-task results:
      mirror_lr              True     mirror
      identity               True     identity
      fill_majority          True     palette_majority
      bg_swap                True     background_swap
      diag_replicate         True     diagonal_replicate
      palette_invert         True     palette_invert
      largest_object         True     largest_object
      rotate_then_shift      False    -
      row_xor_mirror         False    -

To run on a JSON file in standard ARC shape (list of `{train, test}` objects):

    $ python audit.py path/to/tasks.json

## Synthetic tasks

`synthetic_tasks.TASKS` contains 9 tasks:

* **7 trivially solvable** — one per shallow heuristic (`single_color_fill` is
  not exercised by any of the 9 because none of them reduce to a uniform
  fill-by-distinct-count pattern; it remains available for real-data audits).
* **2 intentionally non-trivial composite rules** (`rotate_then_shift` and
  `row_xor_mirror`) that no shallow heuristic reproduces — these confirm the
  flagging is not over-eager.

## Tests

    $ python -m unittest test_heuristics.py -v

17 tests cover each heuristic, the exact-match comparator, and the audit
aggregation logic. They all pass.

## Out of scope (deliberate)

* Running on real ARC-AGI-1 data.
* Automatic task rejection or leaderboard integration.
* Coordination with the other sub-agents (taxonomy, IRT, generator,
  grading).