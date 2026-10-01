# ARC-AGI-1 Corpus (snapshot used by domains/arc/real-eval)

This directory contains the public **ARC-AGI-1** corpus, downloaded to support
the first external benchmark of the CLAgent (snapshot v0.1.0).

## Source

* **Repository**: https://github.com/fchollet/ARC-AGI (branch `master`)
* **Download URL**: `https://github.com/fchollet/ARC-AGI/archive/refs/heads/master.zip`
* **Download date (UTC)**: 2026-10-01
* **Archive SHA-256**: `41d34778e944fe3a6e8192a6b3777d0c78818839b4fb6db98526f129781b2c58`
* **Archive size**: 466,800 bytes (the ARC task JSONs are individually small; the
  full repo archive is < 1 MB. The "~100 MB" estimate in the task brief was an
  over-estimate — the public ARC-AGI-1 release is intentionally tiny.)

## License

The ARC-AGI public data and the surrounding repository are released under the
**Apache License 2.0** by François Chollet. A copy of the upstream `LICENSE`
file is preserved at `ARC-AGI-master/LICENSE` after extraction.

## Layout after extraction

```
data/
├── arc-agi-master.zip          # original downloaded archive (kept for provenance)
├── ARC-AGI-master/             # raw upstream checkout (kept as ground-truth reference)
├── arc-agi-1/                  # canonical layout used by the eval scripts
│   ├── training/   (400 tasks, *.json)
│   └── evaluation/ (400 tasks, *.json)
└── README.md   (this file)
```

Total tasks available: **400 training + 400 evaluation = 800 public tasks.**
(ARC-AGI-1's official split is 400/400; the brief's "800 training + 400 eval"
criterion was based on an over-count. Our scripts work on the full 400+400
and apply a configurable `--limit` for the 150-task default subset.)

## Task file format

Each JSON file matches the canonical ARC format documented in
`ARC-AGI-master/README.md` §"Task file format":

```json
{
  "train": [
    {"input": [[...]], "output": [[...]]},   // 2-4 demonstration pairs
    ...
  ],
  "test": [
    {"input": [[...]], "output": [[...]]}    // 1-3 hidden test pairs
  ]
}
```

Colours are integers in `[0, 9]`. The grid dimensions of `test[*].output` can
differ from `test[*].input`; solvers must predict the output shape as well.

## How the eval scripts consume this data

* `run_real_eval.py` and `run_grading.py` load each task and wrap it as
  `{"task_id": ..., "task": {"train": ..., "test": ...}}` before handing it to
  the CLAgent (which expects that wrapped envelope).
* `run_audit.py` operates directly on the bare ARC task dict (matching the
  contract of `domains/arc/audit/audit.audit_tasks`).

The scripts are robust to malformed JSON / missing fields — they skip + log,
never crash the driver.