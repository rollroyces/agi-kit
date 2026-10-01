"""Procedural memory: keyed name → program mapping with simple lifting.

A program here is anything callable from the DSL or composed in Python. Names
are stable across tasks; the agent chooses the name when storing.

Lifting heuristic
-----------------
A sub-expression is "lifted" when:
    1. It appears as a sub-tuple (or as a callable bound to a name) in at least
       ``min_support`` (default 2) distinct stored programs.
    2. Its textual fingerprint (a canonical hashable repr) is unique enough to
       be worth naming.

We use the AST repr string as the fingerprint. Lifted names get the prefix
``auto_lift_`` plus a short stable hash. Lift failures (``LiftError``) are
non-fatal; the caller may catch and continue.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


class LiftError(Exception):
    """Raised when a lift operation cannot be completed."""


def _fingerprint(node: Any) -> str:
    """A stable textual fingerprint for an AST or callable.

    For ASTs we collapse nested structure into a canonical string. For
    callables we hash the source code (via :func:`inspect.getsource`) so two
    distinct Python objects with identical bodies produce the same fingerprint
    — this is what makes lifting across separately-defined templates work.
    """
    if callable(node):
        try:
            import inspect
            src = inspect.getsource(node)
        except Exception:
            src = repr(node)
        return f"callable::{src}"
    if isinstance(node, tuple):
        return "(" + " ".join([_fingerprint(x) for x in node]) + ")"
    return repr(node)


class ProceduralMemory:
    """Keyed store of named programs with simple AST-subtree lifting."""

    def __init__(self, min_support: int = 2) -> None:
        if min_support < 2:
            raise ValueError("min_support must be >= 2")
        self._store: Dict[str, Any] = {}
        self._support: Dict[str, List[str]] = defaultdict(list)
        self.min_support = min_support

    # ---- CRUD --------------------------------------------------------------

    def add(self, name: str, program: Any) -> None:
        """Store ``program`` under ``name``; reject names that already exist."""
        if name in self._store:
            raise KeyError(f"procedural memory: name already used: {name!r}")
        self._store[name] = program
        self._register_support(name, program)

    def get(self, name: str) -> Any:
        """Return the program stored under ``name`` (KeyError if missing)."""
        return self._store[name]

    def has(self, name: str) -> bool:
        return name in self._store

    def list_all(self) -> List[Tuple[str, Any]]:
        """Return ``[(name, program), ...]`` in insertion order."""
        return list(self._store.items())

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._store

    # ---- Lifting -----------------------------------------------------------

    def _register_support(self, name: str, program: Any) -> None:
        """Index every distinct sub-tree of ``program`` for lift counting."""
        for fp in _subtree_fingerprints(program):
            self._support[fp].append(name)

    def candidates_to_lift(self) -> List[Tuple[str, List[str]]]:
        """Return ``[(fingerprint, supporting_names), ...]`` ready to lift."""
        out: List[Tuple[str, List[str]]] = []
        for fp, names in self._support.items():
            if fp.startswith("auto_lift::"):
                continue
            if len(set(names)) < self.min_support:
                continue
            if not _is_worth_lifting(fp):
                continue
            out.append((fp, names))
        return out

    def lift(self, fingerprint: Optional[str] = None) -> str:
        """Promote a sub-expression to a named subroutine.

        If ``fingerprint`` is ``None`` the first eligible candidate from
        :meth:`candidates_to_lift` is lifted. Returns the new subroutine's
        name.
        """
        cands = self.candidates_to_lift()
        if fingerprint is not None:
            cands = [(fp, n) for fp, n in cands if fp == fingerprint]
            if not cands:
                raise LiftError(f"no liftable candidate with fingerprint {fingerprint!r}")
        if not cands:
            raise LiftError("no liftable candidates found")
        fp, _names = cands[0]
        # Find the actual sub-tree by walking one of the supporting programs.
        sub = _find_subtree_by_fingerprint(self._store[_names[0]], fp)
        if sub is None:
            raise LiftError("lift failed: could not locate subtree")
        short = hashlib.sha1(fp.encode("utf-8")).hexdigest()[:8]
        new_name = f"auto_lift_{short}"
        if new_name in self._store:
            return new_name
        # Wrap the sub-tree as a fresh callable so callers can use it directly.
        self._store[new_name] = sub
        self._support[fp].append(new_name)
        return new_name

    # ---- Pre-seeding -------------------------------------------------------

    @staticmethod
    def preset() -> "ProceduralMemory":
        """Return a memory pre-loaded with three hand-crafted primitives."""
        from ..dsl.primitives import identity, flip_h, flip_v, rotate, largest_object, _deep_copy
        from ..dsl.primitives import background_color as _bg
        from ..dsl.primitives import recolor

        mem = ProceduralMemory()
        mem.add("identity_program", identity)
        mem.add("mirror_program", flip_h)
        mem.add("flip_v_program", flip_v)
        return mem


# ---------------------------------------------------------------------------
# Sub-tree utilities
# ---------------------------------------------------------------------------

def _subtree_fingerprints(node: Any) -> Iterable[str]:
    """Yield the fingerprint of every distinct sub-tree under ``node``.

    The root is included.
    """
    seen = set()
    stack = [node]
    while stack:
        cur = stack.pop()
        fp = _fingerprint(cur)
        if fp in seen:
            continue
        seen.add(fp)
        yield fp
        if isinstance(cur, tuple):
            stack.extend(cur[1:])
        elif isinstance(cur, list):
            stack.extend(cur)


def _find_subtree_by_fingerprint(node: Any, fp: str) -> Optional[Any]:
    """Walk ``node`` and return the first sub-tree whose fingerprint matches."""
    if _fingerprint(node) == fp:
        return node
    if isinstance(node, tuple):
        for child in node[1:]:
            found = _find_subtree_by_fingerprint(child, fp)
            if found is not None:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _find_subtree_by_fingerprint(child, fp)
            if found is not None:
                return found
    return None


_TRIVIAL_FPS = {
    "(identity)",                # the zero-arg "current grid" placeholder
}


def _is_worth_lifting(fp: str) -> bool:
    """Skip trivially-shared subtrees like ``("identity",)``.

    These appear in every program that uses the placeholder and lifting them
    would just create noise.
    """
    if fp in _TRIVIAL_FPS:
        return False
    # Don't lift single-literal subtrees either (e.g. ``(rotate, x, 1)`` where
    # only ``1`` is shared).
    if fp.startswith("(") and fp.endswith(")") and fp.count("(") == 1 and fp.count(" ") == 0:
        return False
    return True