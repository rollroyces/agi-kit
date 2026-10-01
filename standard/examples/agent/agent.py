"""Standard-conformant example agent: propose 3 candidates, pick the survivor.

This is the SPEC §6 reference shape: a small `Agent` subclass that:

* exposes `name`, `version`,
* overrides `propose_programs(task)` to return 3 candidate programs,
* relies on the inherited `verify()` to score each on the train pairs,
* returns an `Answer` whose `trace` has the §6.2 schema.

One of the three proposals IS the `fill_enclosed` rule — this is the
"cheat by knowing the task family" pattern, valid for the conformance
demo. A real agent would discover the rule from the train pairs.

Usage::

    from agent import ExampleAgent
    from reference.airt import InMemoryStore, ToolBridge

    agent = ExampleAgent()
    task = ...   # any standard task
    answer = agent.solve(task, InMemoryStore(), ToolBridge())
"""
from __future__ import annotations

import copy
import importlib.util
import os
import sys
from typing import Callable, List

_THIS = os.path.dirname(os.path.abspath(__file__))
_STANDARD = os.path.abspath(os.path.join(_THIS, "..", ".."))
sys.path.insert(0, _STANDARD)
sys.path.insert(0, os.path.join(_STANDARD, "reference"))

from airt import Agent, InMemoryStore, ToolBridge  # noqa: E402

Grid = List[List[int]]
Program = Callable[[Grid], Grid]


def _fill_enclosed_rule(input_grid: Grid) -> Grid:
    """Reference rule: fill every enclosed background region with colour 9."""
    # We re-use the original generator's solver to keep behaviour identical.
    project_root = os.path.abspath(os.path.join(_STANDARD, ".."))
    generator_path = os.path.join(
        project_root, "domains", "arc", "generators",
        "generators", "fill_enclosed.py",
    )
    if project_root not in sys.path:
        sys.path.insert(0, os.path.join(
            project_root, "domains", "arc", "generators",
        ))
    spec = importlib.util.spec_from_file_location(
        "generators.fill_enclosed", generator_path,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # The generator exposes `_solve_holes` only as a private helper.
    return mod._solve_holes(input_grid, fill_color=9)  # noqa: SLF001


class ExampleAgent(Agent):
    """A Core-conformant agent that proposes three programs."""

    name = "example_agent"
    version = "1.0.0"

    def __init__(self, fill_color: int = 9) -> None:
        self.fill_color = fill_color

    def propose_programs(self, task):
        """Return three candidates: identity, all-zero, fill_enclosed rule."""
        return [
            self._identity,
            self._all_zero,
            lambda g, _c=self.fill_color: _fill_enclosed_rule(g),
        ]

    @staticmethod
    def _identity(g: Grid) -> Grid:
        return [row[:] for row in g]

    @staticmethod
    def _all_zero(g: Grid) -> Grid:
        return [[0 for _ in row] for row in g]


# --- usage ------------------------------------------------------------------

if __name__ == "__main__":
    sample_task = {
        "task": {
            "train": [{"input": [[0, 1], [1, 0]], "output": [[0, 1], [1, 0]]}],
            "test":  [{"input": [[0, 1], [1, 0]], "output": [[0, 1], [1, 0]]}],
        }
    }
    ans = ExampleAgent().solve(sample_task, InMemoryStore(), ToolBridge())
    print(f"agent.py: produced {len(ans.test_predictions)} prediction(s); "
          f"trace steps: {len(ans.trace['steps'])}")
