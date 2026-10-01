"""Procedural memory — reusable programs (skills) that survive across tasks.

The MVP supports only the *procedural* slice of A3S §6.3 memory; episodic and
semantic stores are delegated to the A3S reference implementation when the
agent runs under a real harness.

Lifting
-------
After every successful solve the agent stores the winning program under a
caller-chosen name. If the same sub-expression appears in >= 2 stored
programs, the memory *lifts* it as a new named subroutine so that future tasks
can compose without re-discovering the pattern.
"""
from __future__ import annotations

from memory.procedural import ProceduralMemory, LiftError

__all__ = ["ProceduralMemory", "LiftError"]