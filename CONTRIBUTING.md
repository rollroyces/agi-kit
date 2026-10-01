# Contributing to agi-kit

Please keep changes minimal and well-scoped. Python 3.11+ is required; tests
use stdlib `unittest` (not pytest).

## Quick start

```bash
git clone https://github.com/rollroyces/agi-kit.git
cd agi-kit
python -m pip install -r infra/irt/requirements.txt   # only declared deps file
```

## Running all tests

The full local test suite is six commands, one per test directory. Each
exits 0 on success:

```bash
python -m unittest discover -s agent/tests
python -m unittest discover -s agent/reflector/tests
python -m unittest discover -s standard/conformance
python -m unittest discover -s domains/arc/audit      -p "test_*.py"
python -m unittest discover -s domains/arc/grading    -p "test_*.py"
python -m unittest discover -s infra/irt/tests        -p "test_*.py"
```

These commands run in CI on every push and pull request to `main`, across Python 3.11 and 3.12.

## Branch and PR conventions

- One feature or refactor per branch; keep the diff small and reviewable.
- Branch names: `feat/<topic>`, `chore/<topic>`, `fix/<topic>`.
- Reference the issue number in the PR description (e.g. `Closes #12`) when
  one exists; otherwise describe the motivation in one or two sentences.
- All six test commands must pass locally before opening a PR; CI mirrors
  them exactly and a green PR is the only acceptable merge state.

## Adding a new task generator

Templates live under `domains/arc/generators/`. Copy the closest existing
generator (e.g. `generators/symmetry_complete.py`), implement the required
interface, register it in `arc_gen/registry.py`, and add an example task JSON
under `domains/arc/generators/examples/<your_gen>/`. Ship with at least one
example that passes `validate.py`.

## Adding a new test

Tests live next to the code they cover under `agent/tests/`,
`agent/reflector/tests/`, `standard/conformance/`, `domains/arc/audit/`,
`domains/arc/grading/`, and `infra/irt/tests/`. Use stdlib `unittest`; name
files `test_<topic>.py`. The discover step picks up new files automatically.