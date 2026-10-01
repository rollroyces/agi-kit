"""Procedural memory — reusable programs (skills) that survive across tasks.

The MVP supports the *procedural* slice of A3S §6.3 memory; the v2 update
adds an :class:`EpisodicMemory` store that records per-task traces and
retrieves the top-K most similar past traces during a new solve. The
underlying A3S reference still owns the episodic store under a real
harness; this in-process store is what the agent uses by default.

Lifting
-------
After every successful solve the agent stores the winning program under a
caller-chosen name. If the same sub-expression appears in >= 2 stored
programs, the memory *lifts* it as a new named subroutine so that future tasks
can compose without re-discovering the pattern.
"""
from __future__ import annotations

from memory.procedural import ProceduralMemory, LiftError
from memory.episodic import EpisodicMemory, Trace, episodic_vector

__all__ = [
    "ProceduralMemory", "LiftError",
    "EpisodicMemory", "Trace", "episodic_vector",
]