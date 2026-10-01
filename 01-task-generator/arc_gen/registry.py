"""Registry mapping generator names to callables.

Each registered generator must accept `(public_seed, private_seed, **kwargs)`
and return an ARC task dict (see `arc_gen.core.validate_arc_task`).
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from generators import (
    count_colors,
    fill_enclosed,
    rotate_largest,
    symmetry_complete,
)

TaskFn = Callable[..., Dict[str, Any]]

GENERATORS: Dict[str, TaskFn] = {
    "fill_enclosed": fill_enclosed.generate,
    "rotate_largest": rotate_largest.generate,
    "count_colors": count_colors.generate,
    "symmetry_complete": symmetry_complete.generate,
}


def generate_task(name: str, public_seed: Any, private_seed: Any, **kwargs: Any) -> Dict[str, Any]:
    """Dispatch to the named generator with seeds and parameters."""
    if name not in GENERATORS:
        raise KeyError(
            f"Unknown generator '{name}'. Known: {sorted(GENERATORS)}"
        )
    return GENERATORS[name](public_seed, private_seed, **kwargs)