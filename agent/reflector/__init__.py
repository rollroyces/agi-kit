"""Reflector — CLAgent module 5 (metacognition).

Public surface
--------------

* :class:`Reflector` — the scorer + action selector.
* :class:`ReflectionReport` — the immutable result of ``Reflector.assess``.
* :class:`Candidate` — input container for ``Reflector.assess``.
"""
from __future__ import annotations

from .reflector import Reflector, ReflectionReport, Candidate

__all__ = ["Reflector", "ReflectionReport", "Candidate"]
