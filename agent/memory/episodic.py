"""Episodic memory — per-task traces with k-NN retrieval (v2).

Stores one :class:`Trace` per ``task_id``. Each trace carries a *feature
vector* derived from :class:`reasoner.features.TaskFeatures` so the next
solve can ask for traces from prior tasks that "looked like this one" and
pass them to the proposer as hints from past experience.

The similarity metric is a normalised Euclidean distance over a small,
deterministic feature vector — intentionally cheap so retrieval adds no
observable overhead to a solve. A hand-crafted example trace is pre-seeded
so retrieval works on the very first task after a cold start.

Trace schema (v2)
-----------------
::

    {
        "task_id": str,
        "family": str,                # task["generator"] if present
        "features": TaskFeatures,     # snapshot for distance computation
        "winning_program_label": str, # template/LLM label that was committed
        "winning_program_repr": str,  # repr() of the callable for inspection
        "confidence": float,
        "hints": List[str],           # task["hints"] if present
    }

Public surface
--------------
* :class:`EpisodicMemory` — the store.
* :func:`episodic_vector` — project a :class:`TaskFeatures` to a feature
  vector (the same function the agent uses for retrieval, so callers and
  the store agree on the distance space).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# Fixed feature vector layout. Keep in sync with :func:`episodic_vector`.
_FEATURE_NAMES: Tuple[str, ...] = (
    "palette_size_norm",
    "object_count_norm",
    "has_symmetry_h",
    "has_symmetry_v",
    "shape_invariant",
    "n_train_norm",
    "output_introduces_new_color",
    "is_multichannel",
)


def _safe_max(values: List[float], default: float = 1.0) -> float:
    return max(default, max(values) if values else default)


@dataclass
class Trace:
    """One task's recorded outcome. Lightweight — feature vector + winner."""

    task_id: str
    family: str = ""
    features: Any = None
    winning_program_label: str = ""
    winning_program_repr: str = ""
    confidence: float = 0.0
    hints: List[str] = field(default_factory=list)


def episodic_vector(feat: Any) -> List[float]:
    """Project a :class:`TaskFeatures` (or similar) to a fixed-length vector.

    The vector is unit-scale-ish so distances stay in a stable range. Any
    attribute access on the input is wrapped in ``getattr(..., default)`` so
    the function gracefully handles tests that pass dicts, mocks, or
    ``None``.
    """
    g = lambda n, d=0: getattr(feat, n, d)

    palette = max(1, g("palette_size", 1))
    obj_count = max(1, g("object_count", 1))
    n_train = max(1, g("n_train_pairs", 1))
    return [
        g("palette_size", 1) / 10.0,
        g("object_count", 1) / 5.0,
        1.0 if bool(g("has_symmetry_h", False)) else 0.0,
        1.0 if bool(g("has_symmetry_v", False)) else 0.0,
        1.0 if bool(g("shape_invariant", True)) else 0.0,
        n_train / 5.0,
        1.0 if bool(g("output_introduces_new_color", False)) else 0.0,
        1.0 if bool(g("is_multichannel", False)) else 0.0,
    ]


def _distance(a: List[float], b: List[float]) -> float:
    """Euclidean distance between two feature vectors."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class EpisodicMemory:
    """Per-task trace store with k-NN retrieval over the feature vector."""

    def __init__(self) -> None:
        self._traces: Dict[str, Trace] = {}
        # Stats collected while running (useful for diagnostics + tests).
        self.last_query_hits: List[str] = []

    # ---- CRUD --------------------------------------------------------

    def store_trace(self, trace: Trace) -> None:
        """Insert (or overwrite) one trace keyed by ``trace.task_id``."""
        self._traces[trace.task_id] = trace

    def get(self, task_id: str) -> Optional[Trace]:
        """Return the trace for ``task_id`` (or ``None``)."""
        return self._traces.get(task_id)

    def __len__(self) -> int:
        return len(self._traces)

    def __contains__(self, task_id: object) -> bool:
        return isinstance(task_id, str) and task_id in self._traces

    def list_all(self) -> List[Trace]:
        """All traces in insertion order."""
        return list(self._traces.values())

    # ---- Retrieval ---------------------------------------------------

    def retrieve_similar(
        self,
        query_features: Any,
        k: int = 3,
        *,
        exclude: Optional[List[str]] = None,
    ) -> List[Trace]:
        """Return up to ``k`` traces whose feature vectors are closest to
        ``query_features`` (Euclidean). Excludes any task_id in ``exclude``
        so the current task never sees its own prior trace.
        """
        if not self._traces:
            self.last_query_hits = []
            return []
        excl = set(exclude or [])
        qv = episodic_vector(query_features)
        scored: List[Tuple[float, Trace]] = []
        for tid, trace in self._traces.items():
            if tid in excl:
                continue
            tv = episodic_vector(trace.features)
            scored.append((_distance(qv, tv), trace))
        scored.sort(key=lambda pair: pair[0])
        out = [trace for _, trace in scored[:k]]
        self.last_query_hits = [t.task_id for t in out]
        return out

    # ---- Pre-seeding -------------------------------------------------

    @staticmethod
    def preset() -> "EpisodicMemory":
        """Return a memory pre-loaded with one hand-crafted trace.

        The seed mimics a prior ``rotate_largest`` solve so the very first
        retrieval on a rotation-style task returns a sensible hint instead
        of an empty list.
        """
        from dataclasses import asdict
        # Build a fake TaskFeatures-like object so episodic_vector() works.
        @dataclass
        class _Feat:
            palette_size: int = 3
            background: int = 0
            object_count: int = 2
            has_symmetry_h: bool = False
            has_symmetry_v: bool = False
            n_train_pairs: int = 3
            shape_invariant: bool = True
            output_introduces_new_color: bool = False
            is_multichannel: bool = False

        seed = Trace(
            task_id="seed::rotate_largest::01",
            family="rotate_largest",
            features=_Feat(),
            winning_program_label="rotate_largest_90",
            winning_program_repr="tpl_rotate_largest",
            confidence=0.9,
            hints=[],
        )
        mem = EpisodicMemory()
        mem.store_trace(seed)
        return mem