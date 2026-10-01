# A3S — ARC-AGI-3 Standard

**Version 1.0.0** — see [`SPEC.md`](SPEC.md) for the normative protocol.

A3S is a versioned protocol that turns the agi-kit project's five
deliverables (`domains/arc/generators`, `infra/irt`,
`infra/taxonomy`, `domains/arc/grading`, `domains/arc/audit`) into an
adoptable community standard. It **wraps** the existing components — it
does not replace them. The current version is embedded in every emitted
JSON artefact's `schema_version` field; if that disagrees with SPEC.md,
the JSON is authoritative.

## What A3S standardises

A3S fixes seven interfaces:

| # | Interface | SPEC § | Reference |
|---|-----------|--------|-----------|
| 1 | A3S task JSON shape | §4 | `reference/task_format.py` |
| 2 | Generator API (`generate(public_seed, private_seed, **params)`) | §5 | `reference/generator.py` |
| 3 | Agent interface (`solve(task, memory, tools)`) | §6 | `reference/airt.py` |
| 4 | Audit verdict schema + heuristic registry | §7 | `reference/audit.py` |
| 5 | Hierarchical 3-tier grader + invariance classes | §8 | `reference/grader.py` |
| 6 | Reporting schema (IRT θ, robustness, sample-efficiency, Brier) | §9 | `reference/irt.py` |
| 7 | Submission bundle directory layout | §10 | (manifest only — see `examples/submission/`) |

Anything that conforms to those seven contracts can plug into any
A3S-compliant evaluation harness.

## What's in this repo

```
standard/
├── SPEC.md                   # The normative protocol (v1.0.0, ~470 lines)
├── VERSIONING.md             # Semver rules, BC, RFC process
├── README.md                 # This file
├── VERSION                   # Single-line: "1.0.0"
├── reference/                # Minimum-viable Python reference impls (6 files)
├── conformance/              # unittest suite that validates A3S compliance (6 files)
└── examples/                 # Four ready-to-copy bundles:
    ├── task_family/          #    A3S-conformant generator wrapper
    ├── agent/                #    A3S-conformant agent stub
    ├── heuristic/            #    A new shallow heuristic
    └── submission/           #    A complete submission bundle
```

## Conformance levels

A3S defines three levels (see SPEC §3):

| Level | What it requires |
|-------|------------------|
| **Core** | §4 task shape + §5 generator API + ≥5-heuristic §7 audit + tier-1 §8 score + minimal §9 report |
| **Extended** | Core + full 3-tier §8 grader + per-task invariance gating + complete §9 report (IRT, robustness, sample-efficiency, Brier, cost) |
| **Reference** | Extended + uses the canonical `reference/` implementations + passes every `conformance/` test |

Any implementation can declare its level in `submission.json`. A
Reference implementation that passes `python -m unittest discover` from
`conformance/` is known to satisfy the strongest contract.

### Running the conformance suite

```bash
cd F:\tmp\agi-kit\standard\conformance
python -m unittest discover
# Expected: Ran 45 tests in ~0.1s ... OK
```

## How to contribute

A3S evolves through public RFCs in the `rfcs/` directory. The full
process is in [`VERSIONING.md`](VERSIONING.md), but the short version is:

1. Read [`SPEC.md`](SPEC.md) end-to-end.
2. Decide which interface(s) you want to extend or modify.
3. Fork this repo, add an RFC under `rfcs/NNNN-short-title.md` using
   the template in `VERSIONING.md` §4.2.
4. Build **two independent implementations** and demonstrate that they
   inter-operate on a non-trivial task set.
5. Open a pull request.

For minor things (typo fixes, new examples, new conformance tests for
existing clauses), no RFC is needed — just a regular PR.

## Version

This document covers **A3S v1.0.0**.

## Acknowledgements

A3S wraps the work of the agi-kit sub-projects at `F:\tmp\agi-kit/`:

- **domains/arc/generators** — parametric ARC task generators.
- **infra/irt** — 2PL / 3PL item-response-theory modelling.
- **infra/taxonomy** — 20 cognitive primitives in 6 groups.
- **domains/arc/grading** — hierarchical 3-tier grader with invariance classes.
- **domains/arc/audit** — shallow-heuristic adversarial audit harness.

The audit-on-generated finding
(`domains/arc/audit-on-generated/FINDINGS.md`) confirms 0/16 generated
tasks are trivially solvable — the reason A3S can safely mandate the §7
audit.
