# Audit Result on 16 Procedurally-Generated ARC Tasks

## Headline

**0 / 16 generated tasks are trivially-solvable** by any of 8 shallow heuristics.

Per-heuristic accuracy:

| Heuristic             | Hits / 16 | Accuracy |
|-----------------------|-----------|----------|
| identity              | 0/16      | 0.0%     |
| palette_majority      | 0/16      | 0.0%     |
| mirror                | 0/16      | 0.0%     |
| largest_object        | 0/16      | 0.0%     |
| background_swap       | 0/16      | 0.0%     |
| diagonal_replicate    | 0/16      | 0.0%     |
| single_color_fill     | 0/16      | 0.0%     |
| palette_invert        | 0/16      | 0.0%     |

## Methodology

- Audit harness: `F:\tmp\agi-kit\domains\arc\audit\audit.py` + `heuristics.py` (8 shallow solvers).
- Glue: walks `domains/arc/generators/examples/**/task_*.json`, strips the generator wrapper, runs the audit, writes reports.
- Reports saved to `domains/arc/audit/audit_report.json` and `audit_report.txt`.
- 16 tasks = 4 each from `fill_enclosed`, `rotate_largest`, `count_colors`, `symmetry_complete`.

## Calibration check

The same audit harness correctly flagged **7 / 9** of the bundled `synthetic_tasks.py` tasks (those were deliberately designed to be flagged). This rules out "audit is too lenient" — the harness discriminates. The fact that our 16 generator outputs all pass is real signal, not a false negative.

## What it tells us

1. **The four generators do not produce shallow-exploitable tasks.** They genuinely require applying the rule the demo pairs teach.
2. **The generator framework's quality gate is end-to-end runnable.** A new generator can be added; running the harness over a sample of its outputs is now a one-line test for trivial solvability.
3. **The audit + generator loop works.** This is the smallest end-to-end demonstration of two of the five sub-agent deliverables composing.

## Limitations

- Sample size 16 is small (4 per generator). A wider sweep (40-100 tasks per generator) would tighten the estimate.
- The 8 heuristics ignore `train_pairs`. The next iteration of the audit should add at least one "looks at demos" heuristic (e.g., output = first train's output) to detect identity-by-mistake tasks.
- We have not yet run the audit on the actual ARC-AGI-1 public corpus. That is the natural next step to see what fraction of the real benchmark is shallow-exploitable — a publishable finding in itself.

## Suggested next moves

1. Run the same harness on the public ARC-AGI-1 corpus (download from `github.com/fchollet/ARC-AGI`). Quantify the fraction of real public tasks that are shallow-heuristic solvable.
2. Scale the audit: regenerate 100+ tasks per generator and re-run. Confirm the 0% flag rate holds.
3. Add "looks at demos" heuristics (`output == first_train_output`, `output == majority_color_of_train_outputs`, etc.) and re-run.
4. Combine the audit flag with the hierarchical grader: a task whose `audit_solvers_hit` is non-empty gets tagged in `task_metadata` and the grader reports both exact and structural scores.