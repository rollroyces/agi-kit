# A3S Versioning & RFC Process

This document defines the rules under which A3S evolves.

## 1. Semver rules

A3S follows [Semantic Versioning 2.0.0](https://semver.org/) strictly.

| Bump   | When | Example |
|--------|------|---------|
| MAJOR  | Breaking change to any interface in SPEC.md §4–§10. Concretely: a change that makes a previously conforming artefact fail a corresponding test in `conformance/` of the new major version. | `v1.5.2` → `v2.0.0` |
| MINOR  | Additive only. New optional field, new invariance class, new helper, or new example. Existing conforming artefacts **MUST** continue to pass `conformance/` unchanged. | `v1.4.1` → `v1.5.0` |
| PATCH  | Documentation, clarification, typo fix, or non-substantive refactor of the reference implementations. | `v1.5.0` → `v1.5.1` |

### 1.1 Hard rules

- A MAJOR bump **MUST** be accompanied by a new `conformance/` test that
  documents what changed.
- A MINOR bump **MUST NOT** add a field whose presence changes the meaning
  of an existing field.
- A PATCH bump **MUST NOT** alter the on-disk JSON shape of any of the
  artefacts listed in SPEC §10.

### 1.2 Identification

The current version **MUST** be discoverable from three sources, all of
which **MUST** agree:

1. `SPEC.md` front-matter line: `Version 1.0.0`.
2. `VERSION` file at the repo root, containing a single line `<semver>`.
3. The `schema_version` field embedded in every emitted JSON artefact.

If any of these disagree, the JSON artefact's `schema_version` is
authoritative.

## 2. Backward compatibility

The following BC guarantees hold across `v1.x.x`:

1. **A v1.0.0 generator MUST run on any v1.x.x system.** That is, any
   change to `reference/generator.py`, `reference/audit.py`, or
   `reference/grader.py` that breaks an existing generator is a MAJOR event.
2. **A v1.0.0 task JSON MUST parse cleanly on any v1.x.x validator.**
   New optional fields may appear in newer minor versions; older validators
   **MUST** ignore unknown fields rather than fail.
3. **A v1.0.0 report JSON MUST continue to load and yield the same
   `task_set_score`** under any v1.x.x reference implementation.

## 3. Deprecation policy

When an interface (a function, a JSON field, a class) is to be removed:

1. It **MUST** be marked deprecated for at least **one MINOR cycle** before
   removal. During the deprecation cycle:
   - The reference implementation **MUST** emit a `DeprecationWarning`
     at every call site.
   - The SPEC **MUST** mark the corresponding section as
     `> DEPRECATED: will be removed in vX.0.0; use Y instead.`
2. Removal happens at the next MAJOR bump, never inside a MINOR.
3. The deprecation notice **MUST** appear in `CHANGELOG.md` with the date
   it was first announced.

## 4. RFC process

A3S evolves through public RFCs.

### 4.1 Where proposals live

Every proposal is a Markdown file in the `rfcs/` directory, named
`NNNN-short-title.md` where `NNNN` is the next available zero-padded
sequence number.

### 4.2 Required structure

Each RFC **MUST** contain:

1. **Title and status** (`draft` / `accepted` / `rejected` / `withdrawn`).
2. **Author(s).**
3. **Motivation** — what is broken or missing.
4. **Proposal** — concrete spec-level changes, with before/after snippets.
5. **Drawbacks and alternatives.**
6. **Open questions.**
7. **Adoption plan** — how implementations migrate.

### 4.3 Acceptance criteria

An RFC is accepted when **all** of the following hold:

- **Two implementations.** At least two independent reference or third-party
  implementations demonstrate the proposed change against a real ARC task
  set. Each implementation **MUST** publish a `report.json` under the
  proposed schema.
- **One user.** At least one party not involved in authoring the proposal
  has run both implementations on the same task set and confirms the
  outputs are interchangeable for their use case.
- **Core-team review.** The A3S core team (initially the project authors)
  has signed off in the RFC file.

### 4.4 Decision timing

- RFCs are discussed openly for a minimum of **14 days** before a vote.
- Acceptance requires a simple majority of the core team plus the
  implementation + user criteria above.

### 4.5 What is *not* an RFC

The following do **not** require an RFC:

- Adding a new example under `examples/`.
- Adding a new test under `conformance/` that exercises an already-ratified
  clause.
- Fixing a typo in `SPEC.md`.

These changes **SHOULD** still go through a normal code review and **MUST**
appear in `CHANGELOG.md`.

## 5. Compatibility windows

| Change type | Window before enforcement |
|-------------|---------------------------|
| Removing a deprecated field | next MAJOR (after one MINOR of deprecation) |
| Tightening a regex on a JSON field | next MAJOR |
| Adding a new invariance class | next MINOR (with both `pal`-style and a non-`pal` example in `examples/`) |
| Renaming a reference file | next MAJOR |

## 6. Emergency fixes

A PATCH release **MAY** ship without an RFC if all three are true:

1. The change is documented as a security or correctness fix.
2. The change **MUST NOT** alter any JSON schema or any public function
   signature.
3. The change **MUST** be accompanied by a regression test in
   `conformance/` that fails on the unpatched code.

---

*End of A3S versioning & RFC process.*
