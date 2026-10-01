"""A3S §6 — Agent interface: solve(), Memory, ToolBridge.

This module provides a *minimum-viable* stub. A real agent (the future
PSF-CLAgent MVP) plugs in by subclassing :class:`Agent` and overriding
:meth:`solve`. The default :meth:`solve` here demonstrates the
"propose 3 candidates, verify each, return the survivor" pattern that
the conformance test exercises.

Usage::

    from reference.airt import Agent, InMemoryStore, ToolBridge

    class MyAgent(Agent):
        name = "my_agent"
        version = "1.0.0"
        def propose_programs(self, task):
            return [...]   # list of callables
        def verify(self, prog, task):
            return n_correct, n_total

    agent = MyAgent()
    answer = agent.solve(task, InMemoryStore(), ToolBridge())
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

Grid = List[List[int]]
Program = Callable[[Grid], Grid]


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class InMemoryStore:
    """Trivial three-store memory (episodic / semantic / procedural)."""

    def __init__(self) -> None:
        self._episodic: Dict[str, Any] = {}
        self._semantic: Dict[str, Any] = {}
        self._procedural: Dict[str, Any] = {}

    def read_episodic(self, key: str) -> Any:           return self._episodic.get(key)
    def write_episodic(self, key: str, value: Any) -> None: self._episodic[key] = value
    def read_semantic(self, key: str) -> Any:           return self._semantic.get(key)
    def write_semantic(self, key: str, value: Any) -> None: self._semantic[key] = value
    def read_procedural(self, key: str) -> Any:           return self._procedural.get(key)
    def write_procedural(self, key: str, value: Any) -> None: self._procedural[key] = value


# ---------------------------------------------------------------------------
# Tool bridge
# ---------------------------------------------------------------------------

class ToolBridge:
    """Sandboxed tool surface. All three methods are no-ops by default."""

    def execute_python(self, code: str) -> str:
        raise PermissionError("execute_python disabled in this stub")

    def run_heuristic(self, name: str, task: Dict[str, Any]) -> Dict[str, Any]:
        # The real implementation would dispatch to the audit registry.
        return {"name": name, "ran": True, "hit": False}

    def score(self, predicted: Grid, ground_truth: Grid) -> Dict[str, Any]:
        # Agents **MUST NOT** call this on the held-out test pair.
        return {"tier": 1 if predicted == ground_truth else 0, "score": 1.0 if predicted == ground_truth else 0.0}


# ---------------------------------------------------------------------------
# Agent base
# ---------------------------------------------------------------------------

@dataclass
class Answer:
    test_predictions: List[Grid] = field(default_factory=list)
    trace: Dict[str, Any] = field(default_factory=dict)


class Agent:
    """Base class for A3S agents.

    Subclasses **MUST** override :meth:`solve`. The default implementation
    here runs a tiny "verify-three-candidates" loop and is sufficient for
    the conformance test.
    """

    name: str = "stub_agent"
    version: str = "1.0.0"

    def propose_programs(self, task: Dict[str, Any]) -> List[Program]:
        """Return 1+ candidate programs for this task.

        The default returns three trivial programs: identity, all-zero,
        and all-zero again. A real agent would inspect ``task['train']``
        to propose rule-shaped programs.
        """
        return [self._identity, self._all_zero, self._all_zero]

    def verify(self, prog: Program, task: Dict[str, Any]) -> Tuple[int, int]:
        """Run ``prog`` on every train pair; return (n_correct, n_total)."""
        n_correct = 0
        train = task["task"]["train"]
        for ex in train:
            try:
                pred = prog(copy.deepcopy(ex["input"]))
            except Exception:
                continue
            if pred == ex["output"]:
                n_correct += 1
        return n_correct, len(train)

    def solve(self,
              task: Dict[str, Any],
              memory: InMemoryStore,
              tools: ToolBridge,
              *,
              wallclock_budget_s: float = 30.0) -> Answer:
        """Default solver: verify each proposed program, return the survivor."""
        started = time.time()
        steps: List[Dict[str, Any]] = []

        # Always propose a copy of the input as the last-resort answer.
        test_input = copy.deepcopy(task["task"]["test"][0]["input"])
        fallback: Program = lambda g, _gi=test_input: copy.deepcopy(_gi)
        programs = list(self.propose_programs(task)) + [fallback]

        chosen_pred: Grid = copy.deepcopy(test_input)
        chosen_idx = len(programs) - 1

        for idx, prog in enumerate(programs):
            if time.time() - started > wallclock_budget_s:
                break
            n_correct, n_total = self.verify(prog, task)
            steps.append({
                "step": idx,
                "kind": "verify",
                "verified": {"n_train_correct": n_correct, "n_train_total": n_total},
            })
            if n_correct == n_total and n_total > 0:
                chosen_idx = idx
                chosen_pred = prog(copy.deepcopy(test_input))
                break

        trace = {
            "agent_version": self.version,
            "started_at":    _iso(started),
            "finished_at":   _iso(time.time()),
            "steps":         steps,
            "chosen_program_index": chosen_idx,
            "memory_writes": [],
        }
        return Answer(test_predictions=[chosen_pred], trace=trace)

    @staticmethod
    def _identity(g: Grid) -> Grid:
        return copy.deepcopy(g)

    @staticmethod
    def _all_zero(g: Grid) -> Grid:
        return [[0 for _ in row] for row in g]


def _iso(epoch_seconds: float) -> str:
    import datetime as _dt
    return _dt.datetime.fromtimestamp(epoch_seconds, tz=_dt.timezone.utc).isoformat()


# --- usage example -----------------------------------------------------------

if __name__ == "__main__":
    sample_task = {
        "task": {
            "train": [{"input": [[0, 1], [1, 0]], "output": [[0, 1], [1, 0]]}],
            "test":  [{"input": [[0, 1], [1, 0]], "output": [[0, 1], [1, 0]]}],
        }
    }
    ans = Agent().solve(sample_task, InMemoryStore(), ToolBridge())
    assert ans.test_predictions[0] == sample_task["task"]["test"][0]["input"]
    assert any(s["kind"] == "verify" for s in ans.trace["steps"])
    print("airt.py: self-test passed")
