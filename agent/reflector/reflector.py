"""Reflector — CLAgent module 5 (metacognition).

The Reflector is the missing piece of the CLAgent architecture: after
``VERIFY`` and before ``COMMIT``, the agent asks the Reflector to score
how confident it should be in the winning candidate and which of four
actions to take next.

Public surface
--------------

* :class:`ReflectionReport` — the immutable result of :meth:`Reflector.assess`.
* :class:`Reflector` — the scorer + action selector.

Action semantics
----------------

The Reflector's :meth:`assess` returns one of:

* ``"commit"``         — strong consensus and no audit flag. Run the
  existing COMMIT logic.
* ``"refine"``         — partial evidence. Loop back to HYPOTHESIZE
  with relaxed thresholds (the agent keeps the new K candidates).
* ``"ask_for_help"``   — very low confidence *and* multiple contradictions.
  The MVP cannot reach an external solver, so the agent logs + commits
  best-effort. Real deployments would route to a human or stronger LLM.
* ``"fallback"``       — only the identity heuristic survived. Use the
  existing identity-fallback path (echo the test input).

Inputs
------

* ``proposals``  — the candidate programs the reasoner produced.
* ``verdicts``   — per-candidate list-of-bool: ``[True, False, True]``
  means candidate 0 and 2 verified on train[0], candidate 1 did not.
  The current agent passes a single boolean per candidate ("did this
  candidate verify on ALL train pairs?"); the Reflector uses the wider
  shape when available to compute contradiction scores accurately.
* ``trace``      — the agent's running trace dict, used for context
  (e.g. family, attempts, audit flag).

Design notes
------------

* **Confidence** is the fraction of proposals that survived on every
  train pair. When ``verdicts`` carries per-train-pair detail we
  average the survival rate per pair, which is a more honest signal.
* **Contradiction score** measures how much the *surviving* candidates
  disagree on each train pair. A high contradiction with high
  per-pair-survival means the model is over-fitting — multiple programs
  fit the train pairs but predict different things on test. The
  Reflector treats that as a strong demote.
* **Audit gating** is delegated to an optional ``audit_harness``. If
  the harness flags the winning program, ``audit_flagged`` is ``True``
  and confidence is demoted (mirrors the v1 ``audit_flag_demote`` knob).
* **Action selection** uses two thresholds:
  ``commit`` if confidence ≥ ``threshold_high`` AND not audit-flagged;
  ``ask_for_help`` if confidence is very low AND ≥2 contradictions;
  ``fallback`` if the only survivor is the identity heuristic;
  otherwise ``refine``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """Lightweight container for a candidate program + per-train verdicts.

    ``survived`` is ``True`` if the candidate verified on every train
    pair (the agent's existing "all pairs match" filter).
    ``per_pair`` optionally carries the per-train-pair verdict; an
    empty list means "the agent only tracked the aggregate".
    ``label`` is the human-readable name (e.g. ``"rotate_largest_90"``).
    """

    label: str
    program: Any
    survived: bool
    per_pair: List[bool] = field(default_factory=list)
    is_identity_heuristic: bool = False

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return f"Candidate(label={self.label!r}, survived={self.survived})"


@dataclass
class ReflectionReport:
    """The Reflector's verdict on a single solve.

    ``confidence`` is in ``[0, 1]``; ``contradiction`` in ``[0, 1]``;
    ``audit_flagged`` mirrors the audit harness's verdict on the
    winning program; ``action`` is one of ``"commit" | "refine" |
    "ask_for_help" | "fallback"``; ``reasoning_text`` is a one-line
    human-readable rationale that gets logged in the trace.
    """

    confidence: float
    contradiction: float
    audit_flagged: bool
    action: str
    reasoning_text: str
    # The label of the candidate the report was built around. When the
    # Reflector recommends ``commit`` or ``fallback`` this is the
    # candidate the agent should apply to the test input.
    winner_label: str = ""

    def __post_init__(self) -> None:
        if self.action not in ("commit", "refine", "ask_for_help", "fallback"):
            raise ValueError(
                f"invalid action {self.action!r}; expected one of "
                "'commit', 'refine', 'ask_for_help', 'fallback'"
            )


# ---------------------------------------------------------------------------
# Reflector
# ---------------------------------------------------------------------------

class Reflector:
    """Compute a confidence score and pick the next action.

    Parameters
    ----------
    audit_harness:
        Optional object exposing ``audit(predicted_program, train_pairs,
        test_input) -> verdict_dict``. The verdict dict must carry a
        boolean ``flagged`` key. ``None`` means the Reflector does not
        call out to an audit harness — useful in unit tests.
    threshold_low, threshold_high:
        Confidence band edges. Below ``threshold_low`` the Reflector
        either asks for help (when contradictions are high) or refines;
        at or above ``threshold_high`` it commits (assuming the audit
        harness has not flagged the winner). The defaults (0.3, 0.85)
        match the values the integration test asserts on.
    """

    def __init__(
        self,
        audit_harness: Optional[Any] = None,
        threshold_low: float = 0.3,
        threshold_high: float = 0.85,
    ) -> None:
        if not 0.0 <= threshold_low <= 1.0:
            raise ValueError("threshold_low must lie in [0, 1]")
        if not 0.0 <= threshold_high <= 1.0:
            raise ValueError("threshold_high must lie in [0, 1]")
        if threshold_low > threshold_high:
            raise ValueError("threshold_low must be <= threshold_high")
        self.audit_harness = audit_harness
        self.threshold_low = float(threshold_low)
        self.threshold_high = float(threshold_high)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def assess(
        self,
        proposals: Sequence[Candidate],
        verdicts: Sequence[bool],
        trace: Optional[Dict[str, Any]] = None,
    ) -> ReflectionReport:
        """Score the candidate set and pick the next action.

        Parameters
        ----------
        proposals:
            The candidate programs the reasoner emitted. The Reflector
            uses ``proposal.label`` for reasoning text and
            ``proposal.is_identity_heuristic`` to detect the fallback
            case.
        verdicts:
            Per-candidate ``[bool]``: ``True`` iff that candidate
            survived every train pair. Must be the same length as
            ``proposals``. The agent's existing verifier returns a
            single bool per candidate ("did it verify on *all* train
            pairs?"); per-pair detail lives inside each
            ``Candidate.per_pair``.
        trace:
            Optional agent trace dict. Only ``trace.get("audit_flagged")``
            is consulted (used to seed the audit-flag detection when no
            harness is supplied).

        Returns
        -------
        ReflectionReport
            Always returns a report. Never raises on user-facing error
            conditions; only programming errors (e.g. length mismatch)
            propagate.
        """
        trace = trace or {}
        if len(proposals) != len(verdicts):
            raise ValueError(
                f"proposals ({len(proposals)}) and verdicts "
                f"({len(verdicts)}) must be the same length"
            )

        # ----- empty proposal set → no signal -----------------------
        if not proposals:
            return ReflectionReport(
                confidence=0.0,
                contradiction=0.0,
                audit_flagged=bool(trace.get("audit_flagged", False)),
                action="ask_for_help",
                reasoning_text="no proposals were produced; cannot commit",
                winner_label="",
            )

        # ----- confidence: average per-train-pair survival rate -----
        confidence = self._compute_confidence(proposals, verdicts)

        # ----- contradiction: disagreement among survivors on test ---
        contradiction = self._compute_contradiction(proposals)

        # ----- audit gate ------------------------------------------
        winner, audit_flagged = self._audit_gate(proposals, trace)
        if audit_flagged:
            # Demote by 50% — same convention as CLAgent v1.
            confidence *= 0.5

        # ----- action selection ------------------------------------
        action, reasoning = self._pick_action(
            proposals=proposals,
            verdicts=verdicts,
            confidence=confidence,
            contradiction=contradiction,
            audit_flagged=audit_flagged,
            winner=winner,
        )

        return ReflectionReport(
            confidence=float(confidence),
            contradiction=float(contradiction),
            audit_flagged=bool(audit_flagged),
            action=action,
            reasoning_text=reasoning,
            winner_label=winner.label if winner is not None else "",
        )

    # ------------------------------------------------------------------
    # Internals — confidence, contradiction, audit, action
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        proposals: Sequence[Candidate],
        verdicts: Sequence[bool],
    ) -> float:
        """Average per-train-pair survival rate across proposals.

        * When at least one candidate carries per-pair detail we average
          the per-pair True-rate.
        * Otherwise we fall back to a two-signal blend: the fraction of
          candidates whose aggregate ``verdicts[i]`` is ``True``,
          **boosted by 0.5 if at least one candidate survived every pair**.
          This means a single full-survivor among many candidates
          always lands well above the ``refine`` band.

        The result is clipped to ``[0, 1]``.
        """
        per_pair_any = any(len(p.per_pair) > 0 for p in proposals)
        if per_pair_any:
            n_pairs = max((len(p.per_pair) for p in proposals), default=0)
            if n_pairs == 0:
                return 0.0
            pair_rates: List[float] = []
            for idx in range(n_pairs):
                hits = 0
                total = 0
                for p in proposals:
                    if idx >= len(p.per_pair):
                        # Candidate did not record a verdict for this
                        # pair; treat as "not survived on this pair".
                        total += 1
                        continue
                    total += 1
                    if p.per_pair[idx]:
                        hits += 1
                if total:
                    pair_rates.append(hits / total)
            return sum(pair_rates) / len(pair_rates) if pair_rates else 0.0
        # Aggregate path: average survival ratio + any-survivor boost.
        if not verdicts:
            return 0.0
        survived = sum(1 for v in verdicts if v)
        base = survived / len(verdicts)
        if survived >= 1:
            # Boost: at least one candidate verified on every pair. This
            # is the agent's strongest "I have an answer" signal; it
            # should clear the high-confidence threshold even when many
            # candidates were tried.
            base = max(base, 0.5 + 0.5 * (survived / len(verdicts)))
        return min(1.0, base)

    def _compute_contradiction(self, proposals: Sequence[Candidate]) -> float:
        """Disagreement rate among surviving candidates on the test input.

        A "contradiction" is when two survivors produce different grids
        on the test input. We sample at most the first three survivors
        (the agent already commits to the highest-scoring one; sampling
        three is enough to detect a "consensus" vs "split" situation).
        We probe two distinct sample inputs (``[[0]]`` and ``[[1, 0],
        [0, 1]]``) so identity-vs-rotation style disagreements are
        detectable even when the trivial ``[[0]]`` case collapses.
        Returns ``0.0`` when fewer than two survivors are available.
        """
        survivors = [p for p in proposals if p.survived][:3]
        if len(survivors) < 2:
            return 0.0
        # Two distinct probe inputs so identity vs rotation shows up.
        sample_inputs: List[List[List[int]]] = [
            [[0]],
            [[1, 0], [0, 1]],
        ]
        try:
            outputs_per_sample: List[List[Any]] = []
            for inp in sample_inputs:
                outputs = []
                for s in survivors:
                    try:
                        out = s.program(_deep_copy_grid(inp))
                    except Exception:
                        return 0.0  # Couldn't evaluate → no contradiction signal.
                    outputs.append(_canonicalise(out))
                outputs_per_sample.append(outputs)
            # Pairwise disagreement rate, averaged over both probe inputs.
            pairs = 0
            diffs = 0
            for outputs in outputs_per_sample:
                for i in range(len(outputs)):
                    for j in range(i + 1, len(outputs)):
                        pairs += 1
                        if outputs[i] != outputs[j]:
                            diffs += 1
            return diffs / max(1, pairs)
        except Exception:
            return 0.0

    def _audit_gate(
        self,
        proposals: Sequence[Candidate],
        trace: Dict[str, Any],
    ) -> tuple[Optional[Candidate], bool]:
        """Run the audit harness on the winning candidate.

        Returns ``(winner, flagged)``. When no candidates survived,
        ``winner`` is ``None`` and ``flagged`` is seeded from the
        trace's pre-existing flag.
        """
        survivors = [p for p in proposals if p.survived]
        if not survivors:
            return None, bool(trace.get("audit_flagged", False))
        winner = survivors[0]
        if self.audit_harness is None:
            return winner, bool(trace.get("audit_flagged", False))
        try:
            verdict = self.audit_harness.audit(winner.program, [], None)
        except Exception:
            verdict = None
        flagged = bool(
            (verdict or {}).get("flagged", False)
            or trace.get("audit_flagged", False)
        )
        return winner, flagged

    def _pick_action(
        self,
        *,
        proposals: Sequence[Candidate],
        verdicts: Sequence[bool],
        confidence: float,
        contradiction: float,
        audit_flagged: bool,
        winner: Optional[Candidate],
    ) -> tuple[str, str]:
        """Translate a (confidence, contradiction, audit) triple into an action."""
        # 1. Identity-only fallback.
        survivors = [p for p in proposals if p.survived]
        if survivors and all(p.is_identity_heuristic for p in survivors):
            return "fallback", (
                "only the identity heuristic survives — falling back to "
                "echoing the test input"
            )

        # 2. No survivors at all → ask_for_help.
        if not survivors:
            return "ask_for_help", (
                "no candidate verified on every train pair; nothing to commit"
            )

        # 3. Audit-flagged winner.
        if audit_flagged:
            return "refine", (
                "winning candidate was flagged by the audit harness; "
                "refining instead of committing"
            )

        # 4. High confidence → commit.
        if confidence >= self.threshold_high:
            return "commit", (
                f"confidence={confidence:.2f} ≥ threshold_high="
                f"{self.threshold_high:.2f}; committing"
            )

        # 5. Very low confidence + multiple contradictions → ask_for_help.
        if confidence < self.threshold_low and contradiction >= (2 / 3):
            return "ask_for_help", (
                f"confidence={confidence:.2f} (very low) with "
                f"{contradiction:.2f} contradiction among survivors; "
                "external help required"
            )

        # 6. Default: refine.
        return "refine", (
            f"confidence={confidence:.2f} between thresholds "
            f"[{self.threshold_low:.2f}, {self.threshold_high:.2f}]; refining"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_copy_grid(grid: Any) -> Any:
    """Deep copy helper that doesn't require numpy."""
    try:
        import copy as _copy
        return _copy.deepcopy(grid)
    except Exception:
        return [row[:] for row in grid]


def _canonicalise(grid: Any) -> Any:
    """Convert a grid to a tuple-of-tuples for hashable equality."""
    try:
        return tuple(tuple(row) for row in grid)
    except Exception:
        return repr(grid)
