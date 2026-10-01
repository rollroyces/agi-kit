"""PSF-CLAgent — closed-loop cognitive agent.

Implements the A3S ``solve()`` contract from
``a3s/SPEC.md`` §6 and adds the OBSERVE→HYPOTHESIZE→EXECUTE→VERIFY→COMMIT
loop on top. Key features:

* ``OBSERVE``   extract task features (delegates to ``reasoner.features``).
* ``HYPOTHESIZE`` propose K candidate programs (default K=20) via
  :class:`TemplateProposer`. v2 — accepts natural-language and episodic
  hints via the proposer's ``hints`` argument.
* ``EXECUTE``  run each candidate on every train pair; collect verdicts.
* ``VERIFY``   keep only programs that match every train pair.
* ``REFLECT``  if zero candidates survive, expand K, retry (LLM-style fallback
  is wired but the stub raises ``NotImplementedError``).
* ``COMMIT``   apply the best survivor to the test input.
* ``COMPRESS`` store the winning program in procedural memory and trigger
  the lift heuristic.
* ``Trace``    structured trace per §6.2.
* ``Episodic`` v2 — query the :class:`EpisodicMemory` for the top-K most
  similar prior traces and pass their labels as hints to the proposer.

Imports the A3S ``reference/airt.py`` to satisfy conformance
(``Agent``, ``Answer``, ``InMemoryStore``, ``ToolBridge``) and reuses the
audit module via :mod:`audit_gate`.
"""
from __future__ import annotations

import copy
import datetime as _dt
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

# Import the A3S reference interface to satisfy §6 conformance.
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "a3s"))

from reference.airt import Agent, Answer, InMemoryStore, ToolBridge  # noqa: E402

from memory import ProceduralMemory, LiftError, EpisodicMemory, Trace  # noqa: E402
from reasoner import (  # noqa: E402
    TemplateProposer,
    LLMProposer,
    LLMClient,
    LLMUnavailable,
    extract_features,
)
from audit_gate import is_audit_flagged_for_answer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(epoch_seconds: float) -> str:
    return _dt.datetime.fromtimestamp(epoch_seconds, tz=_dt.timezone.utc).isoformat()


def _now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def _deep_copy(grid: Any) -> Any:
    return copy.deepcopy(grid)


@dataclass
class SolveConfig:
    k_initial: int = 20
    max_attempts: int = 200
    wallclock_budget_s: float = 30.0
    audit_flag_demote: bool = True
    reasoner_type: str = "template"   # "template" | "llm"
    llm_client: Optional[Any] = None   # an LLMClient (or None → from env)


class CLAgent(Agent):
    """Closed-loop PSF agent that proposes, verifies, commits programs."""

    name = "psf_clagent"
    version = "0.1.0"

    def __init__(self, config: Optional[SolveConfig] = None) -> None:
        super().__init__()
        self.config = config or SolveConfig()
        # Always keep a TemplateProposer around — it's the fallback.
        self.template_proposer = TemplateProposer()
        # Build the requested reasoner; resolve LLM availability now.
        self.proposer = self._build_proposer(self.config)
        # Track which reasoner actually ran each task (template/llm) and
        # whether a fallback was triggered.
        self.last_reasoner_used: str = "template"
        self.last_reasoner_fallback: bool = False

    # ------------------------------------------------------------------
    # Reasoner selection + fallback
    # ------------------------------------------------------------------

    def _build_proposer(self, cfg: SolveConfig):
        """Resolve the configured reasoner with graceful LLM→template fallback.
        """
        if cfg.reasoner_type == "llm":
            client = cfg.llm_client
            if client is None:
                client = LLMClient.from_env()
            proposer = LLMProposer(client=client)
            if proposer.is_available():
                return proposer
            # Fallback: log once at agent construction time.
            print(
                "WARNING: --reasoner llm requested but no OPENAI_API_KEY "
                "is set; falling back to TemplateProposer.",
                file=sys.stderr,
            )
            return self.template_proposer
        return self.template_proposer

    # -----------------------------------------------------------------
    # Core A3S entry point
    # -----------------------------------------------------------------

    def solve(self, task: dict, memory, tools: ToolBridge) -> Answer:
        """Run the OBSERVE→HYPOTHESIZE→EXECUTE→VERIFY→COMMIT loop."""
        started_at = time.time()
        steps: List[Dict[str, Any]] = []
        memory_writes: List[Dict[str, Any]] = []

        # ----- OBSERVE --------------------------------------------------
        feats = extract_features(task)
        steps.append({
            "step": len(steps),
            "kind": "observe",
            "rationale": f"features={feats.__dict__}",
        })

        # ----- EPISODIC MEMORY (v2) -----------------------------------
        # Build the combined hints list: task["hints"] + labels of top-K
        # similar prior traces from episodic memory. Wire it through to the
        # proposer; no API change for callers — episodic memory is purely
        # agent-side state.
        episodic_hints: List[str] = []
        task_id = self._compute_task_id(task)
        emem = self._unwrap_episodic(memory)
        if emem is not None and task_id not in emem:
            similar = emem.retrieve_similar(feats, k=3, exclude=[task_id])
            for tr in similar:
                episodic_hints.append(
                    f"past task {tr.task_id} solved with "
                    f"{tr.winning_program_label}"
                )
        task_hints: List[str] = list(feats.hints)
        combined_hints: List[str] = task_hints + episodic_hints
        steps.append({
            "step": len(steps),
            "kind": "retrieve_episodic",
            "rationale": (
                f"hints={len(combined_hints)} "
                f"(task={len(task_hints)} episodic={len(episodic_hints)})"
            ),
            "hints": combined_hints,
        })

        # ----- HYPOTHESIZE ----------------------------------------------
        # Reset per-task reasoner accounting.
        self.last_reasoner_used = "template"
        self.last_reasoner_fallback = False
        proposer = self.proposer
        requested = self.config.reasoner_type
        try:
            proposals = proposer.propose(
                task, k=self.config.k_initial, hints=combined_hints or None,
            )
            self.last_reasoner_used = (
                "llm" if isinstance(proposer, LLMProposer) else "template"
            )
        except LLMUnavailable as exc:
            # Mid-task fallback: switch to template proposer and retry once.
            print(
                f"WARNING: LLM proposer unavailable mid-task "
                f"({exc}); falling back to TemplateProposer.",
                file=sys.stderr,
            )
            self.last_reasoner_fallback = True
            self.last_reasoner_used = "template"
            proposer = self.template_proposer
            proposals = proposer.propose(
                task, k=self.config.k_initial, hints=combined_hints or None,
            )

        # If the user requested llm but we never got an LLMProposer at
        # construction time, flag the fallback in the trace.
        if requested == "llm" and not isinstance(self.proposer, LLMProposer):
            self.last_reasoner_fallback = True

        steps.append({
            "step": len(steps),
            "kind": "propose_program",
            "proposals": [p.label for p in proposals],
            "verified": {"n_train_correct": 0, "n_train_total": len(task["task"]["train"])},
            "rationale": (
                f"proposed {len(proposals)} candidates via "
                f"{self.last_reasoner_used} reasoner"
                + (" (fallback from llm)" if self.last_reasoner_fallback else "")
            ),
        })

        # ----- EXECUTE + VERIFY ---------------------------------------
        survivors: List[Tuple[Any, int]] = []    # (program, n_train_correct)
        attempts = 0
        test_in = _deep_copy(task["task"]["test"][0]["input"])
        expected_shape = task["task"]["test"][0]["input"]
        for cand in proposals:
            if time.time() - started_at > self.config.wallclock_budget_s:
                break
            attempts += 1
            ok, total, err = self._verify(cand.program, task)
            if err:
                steps.append({
                    "step": len(steps),
                    "kind": "verify",
                    "program": cand.label,
                    "verified": {"n_train_correct": 0, "n_train_total": total},
                    "rationale": f"raised {err}",
                })
                continue
            steps.append({
                "step": len(steps),
                "kind": "verify",
                "program": cand.label,
                "verified": {"n_train_correct": ok, "n_train_total": total},
            })
            if ok == total and total > 0:
                survivors.append((cand.program, ok))

        # ----- REFLECT (simple) ---------------------------------------
        if not survivors and attempts < self.config.max_attempts:
            survivors, extras = self._reflect(
                task, started_at, attempts, hints=combined_hints or None,
            )
            steps.extend(extras)

        # ----- COMMIT --------------------------------------------------
        if survivors:
            # Pick the survivor that scanned the most cells correctly (tie → first).
            survivors.sort(key=lambda t: t[1], reverse=True)
            chosen_prog, chosen_score = survivors[0]
        else:
            chosen_prog = lambda g, _gi=_deep_copy(test_in): _deep_copy(_gi)
            chosen_score = 0

        try:
            prediction = _deep_copy(chosen_prog(_deep_copy(test_in)))
        except Exception:
            prediction = _deep_copy(test_in)
        # Spec requires output shape == input shape.
        if not _same_shape(prediction, expected_shape):
            prediction = _deep_copy(test_in)

        # ----- COMPRESS -----------------------------------------------
        committed_label = self._compress(
            task, chosen_prog, prediction, memory, memory_writes
        )

        # ----- AUDIT GATE ---------------------------------------------
        audit_flagged = is_audit_flagged_for_answer(task, prediction)
        confidence = self._compute_confidence(
            survivors, attempts, audit_flagged
        )

        steps.append({
            "step": len(steps),
            "kind": "final_answer",
            "program": committed_label,
            "verified": {"n_train_correct": chosen_score,
                          "n_train_total": len(task["task"]["train"])},
            "tool": {
                "name": "audit_gate",
                "args": {},
                "result": "flagged" if audit_flagged else "pass",
            },
            "rationale": (
                f"audit={'flagged' if audit_flagged else 'pass'}, "
                f"confidence={confidence:.2f}"
            ),
        })

        # ----- EPISODIC STORE (v2) ------------------------------------
        # Persist this trace so the next solve can retrieve similar ones.
        # We do this AFTER final_answer so the trace mirrors what is
        # actually returned to the caller (committed label + confidence).
        if emem is not None:
            emem.store_trace(Trace(
                task_id=task_id,
                family=str(task.get("generator", "")),
                features=feats,
                winning_program_label=committed_label,
                winning_program_repr=repr(chosen_prog),
                confidence=float(confidence),
                hints=list(feats.hints),
            ))

        trace = {
            "agent_version": self.version,
            "started_at": _iso(started_at),
            "finished_at": _iso(time.time()),
            "steps": steps,
            "memory_writes": memory_writes,
            "committed_program": committed_label,
            "audit_flagged": bool(audit_flagged),
            "confidence": float(confidence),
            "attempts": int(attempts),
            "reasoner_used": self.last_reasoner_used,
            "reasoner_fallback": bool(self.last_reasoner_fallback),
        }
        return Answer(test_predictions=[prediction], trace=trace)

    # -----------------------------------------------------------------
    # Hooks for subclasses / tests
    # -----------------------------------------------------------------

    def propose_programs(self, task: dict) -> List[Callable[[Any], Any]]:
        """Expose the top-K programs as plain callables for the parent class."""
        return [p.program for p in self.proposer.propose(task, k=self.config.k_initial)]

    def verify(self, prog: Callable, task: dict) -> Tuple[int, int]:
        ok, total, _ = self._verify(prog, task)
        return ok, total

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

    def _verify(self, prog: Callable, task: dict) -> Tuple[int, int, Optional[str]]:
        """Run ``prog`` on every train pair; return (correct, total, error_str)."""
        n_correct = 0
        train = task["task"]["train"]
        for ex in train:
            try:
                pred = prog(_deep_copy(ex["input"]))
            except Exception as exc:
                return 0, len(train), repr(exc)
            if pred == ex["output"]:
                n_correct += 1
        return n_correct, len(train), None

    def _reflect(
        self,
        task: dict,
        started_at: float,
        attempts_so_far: int,
        *,
        hints: Optional[List[str]] = None,
    ) -> Tuple[List[Tuple[Any, int]], List[Dict[str, Any]]]:
        """Simple fallback: try a wider set of templates + manual composites.

        The MVP does not invoke an LLM. The intent is to expand K up to the
        budget and try a small library of composed programs as well.
        """
        extras: List[Dict[str, Any]] = []
        survivors: List[Tuple[Any, int]] = []
        test_in = _deep_copy(task["task"]["test"][0]["input"])

        # Re-propose with k_initial * 2 and also include some composites.
        proposer = TemplateProposer()
        big = proposer.propose(task, k=self.config.k_initial * 2, hints=hints)
        from dsl.primitives import (
            identity, flip_h, flip_v, rotate, recolor, background_color as bg
        )

        composites = [
            ("composite::rotate_mirror", lambda g: rotate(flip_h(g), 1)),
            ("composite::recolor_majority",
                lambda g: recolor(g, {bg(g): 0})),
        ]
        all_cands = list(big) + [
            type("X", (), {"program": p, "label": n, "score": 0.0})()
            for n, p in composites
        ]
        extras.append({
            "step": 0,        # patched in agent.solve; this is informational
            "kind": "reflect",
            "rationale": f"expanded candidates to {len(all_cands)} (K*2 + composites)",
        })
        for cand in all_cands:
            if attempts_so_far + len(survivors) >= self.config.max_attempts:
                break
            if time.time() - started_at > self.config.wallclock_budget_s:
                break
            ok, total, err = self._verify(cand.program, task)
            if err:
                continue
            if ok == total and total > 0:
                survivors.append((cand.program, ok))
        return survivors, extras

    def _compress(
        self,
        task: dict,
        prog: Callable,
        prediction: Any,
        memory: Any,
        memory_writes: List[Dict[str, Any]],
    ) -> str:
        """Store the winning program in procedural memory and try to lift.

        Accepts either a :class:`ProceduralMemory` directly or a wrapper that
        exposes one via ``memory._procedural`` (the
        :class:`MemoryFacade` does this so it can satisfy both the A3S
        ``Memory`` API and the lift interface).
        """
        pmem = self._unwrap_procedural(memory)
        if pmem is None:
            return "fallback_input"
        gen = task.get("generator", "unknown")
        n = len(pmem.list_all())
        label = f"task_{gen}_{n}"
        try:
            pmem.add(label, prog)
            memory_writes.append({"store": "procedural", "key": label, "value": "w"})
        except KeyError:
            pass
        try:
            lifted = pmem.lift()
            memory_writes.append({"store": "procedural", "key": lifted, "value": "lifted"})
        except LiftError:
            pass
        return label

    @staticmethod
    def _compute_task_id(task: dict) -> str:
        """Build a deterministic, content-aware task id.

        Preference order:
        1. ``task["task_id"]`` (if the caller already provided one).
        2. ``<generator>:<n_train>:<sha1_of_first_train_input[:8]>``.

        The fingerprint ensures distinct examples of the same family get
        distinct episodic-memory slots.
        """
        if isinstance(task, dict):
            tid = task.get("task_id")
            if isinstance(tid, str) and tid:
                return tid
        try:
            import hashlib
            gen = (task.get("generator", "unknown")
                   if isinstance(task, dict) else "unknown")
            n_train = len(task.get("task", {}).get("train", []))
            first_in = task.get("task", {}).get("train", [{}])[0].get(
                "input", [])
            fp = hashlib.sha1(repr(first_in).encode("utf-8")).hexdigest()[:8]
            return f"{gen}:{n_train}:{fp}"
        except Exception:
            return "unknown:0:0"

    @staticmethod
    def _unwrap_procedural(memory: Any) -> Optional[ProceduralMemory]:
        """Return the underlying :class:`ProceduralMemory`, if available."""
        if isinstance(memory, ProceduralMemory):
            return memory
        pmem = getattr(memory, "_procedural", None)
        if isinstance(pmem, ProceduralMemory):
            return pmem
        return None

    @staticmethod
    def _unwrap_episodic(memory: Any) -> Optional[EpisodicMemory]:
        """Return the underlying :class:`EpisodicMemory`, if available.

        Accepts either a bare :class:`EpisodicMemory` or a wrapper with an
        ``_episodic`` attribute (the :class:`MemoryFacade` pattern).
        """
        if isinstance(memory, EpisodicMemory):
            return memory
        emem = getattr(memory, "_episodic_mem", None)
        if isinstance(emem, EpisodicMemory):
            return emem
        return None

    def _compute_confidence(
        self,
        survivors: List[Tuple[Any, int]],
        attempts: int,
        audit_flagged: bool,
    ) -> float:
        """Confidence ∈ [0, 1]. Halved if audit-flagged."""
        if not survivors:
            base = 0.0
        else:
            base = min(1.0, len(survivors) / max(1, attempts))
        if audit_flagged and self.config.audit_flag_demote:
            base *= 0.5
        return base


# ---------------------------------------------------------------------------
# Local fallback memory (in case the harness doesn't pass one)
# ---------------------------------------------------------------------------

class MemoryFacade:
    """Pass this instead of ``InMemoryStore`` to get procedural memory."""

    def __init__(self) -> None:
        self._episodic: Dict[str, Any] = {}
        self._semantic: Dict[str, Any] = {}
        self._procedural = ProceduralMemory.preset()
        # v2 — agent-side episodic memory store; the agent wraps this into
        # task traces so the next solve can retrieve similar traces.
        self._episodic_mem = EpisodicMemory.preset()

    def read_episodic(self, key): return self._episodic.get(key)
    def write_episodic(self, key, value): self._episodic[key] = value
    def read_semantic(self, key): return self._semantic.get(key)
    def write_semantic(self, key, value): self._semantic[key] = value
    def read_procedural(self, key): return self._procedural.get(key) if self._procedural.has(key) else None
    def write_procedural(self, key, value):
        if not self._procedural.has(key):
            self._procedural.add(key, value)


def _same_shape(a: Any, b: Any) -> bool:
    try:
        return (len(a), len(a[0])) == (len(b), len(b[0]))
    except Exception:
        return False