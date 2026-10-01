"""Prompt construction for :class:`LLMProposer`.

The prompt is deliberately compact (under ~2000 tokens for the four
canonical families) and structured so the model can copy the AST syntax
directly. The hard-coded worked examples match what the
:class:`TemplateProposer` actually emits, so a well-aligned model will
reproduce the same answers — and a creative model can produce variants.

v2 — when natural-language hints are passed in, they are appended as a
"TASK HINTS" block with explicit instructions to incorporate them. Both
``task["hints"]`` and episodic-memory hints from prior traces flow in via
the same parameter.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Worked examples — one per canonical family.
#
# Each example is ``(family, task_summary, gold_program_ast_as_callable)``.
# We render the AST as a Python tuple literal so the model can literally
# copy the syntax. The actual program body uses ``(identity,)`` as the
# "current grid" placeholder, then DSL primitives.
# ---------------------------------------------------------------------------

EXAMPLES: List[Dict[str, Any]] = [
    {
        "family": "count_colors",
        "blurb": (
            "Each train pair shows a grid with 2 non-background cells placed "
            "anywhere; the output is a same-shape grid of zeros with exactly "
            "two adjacent 8s in the bottom-left corner."
        ),
        "program_str": "(\"make_grid\", (\"shape\", (\"identity\",)), 8)",
    },
    {
        "family": "rotate_largest",
        "blurb": (
            "Each train pair has 1-2 small objects on a zero background. "
            "The largest object (by cell count) is rotated 90° clockwise "
            "about its top-left cell."
        ),
        "program_str": "(\"apply_program\", <LARGEST_OBJECT_ROTATED_90>)",
    },
    {
        "family": "fill_enclosed",
        "blurb": (
            "Each train pair has a closed non-bg loop with one bg pocket "
            "inside. Fill the pocket with the most-frequent non-bg colour "
            "(or 8 if only one colour besides the bg)."
        ),
        "program_str": "(\"identity\",)",
    },
    {
        "family": "symmetry_complete",
        "blurb": (
            "Each train pair populates only the LEFT or TOP half of the grid. "
            "Mirror the populated half across the vertical or horizontal axis "
            "to fill the empty half."
        ),
        "program_str": "(\"identity\",)",
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_dsl_primitives() -> List[str]:
    """Return the registry's primitive names (deterministic order)."""
    # Lazy import to avoid pulling DSL at module-load time during tests.
    from ..dsl.registry import all_names
    return all_names()


def describe_primitives(names: List[str]) -> List[str]:
    """Return one-line descriptions for each primitive.

    The descriptions are intentionally terse — the model already knows
    Python tuple syntax; we only need to remind it of arity and intent.
    """
    descriptions: Dict[str, str] = {
        # Construction
        "make_grid": "make_grid(h, w, fill=0) — fresh grid",
        "from_list": "from_list(rows) — build from list-of-lists",
        # Inspection
        "shape": "shape(grid) -> (h, w)",
        "color_at": "color_at(grid, r, c) -> int",
        "distinct_colors": "distinct_colors(grid) -> sorted list",
        "count_color": "count_color(grid, c) -> int",
        "background_color": "background_color(grid) -> most-frequent colour",
        # Geometry
        "rotate": "rotate(grid, k=1) — rotate 90° CW k times",
        "flip_h": "flip_h(grid) — mirror left↔right",
        "flip_v": "flip_v(grid) — mirror top↔bottom",
        "translate": "translate(grid, dr, dc, fill=0) — shift",
        # Object ops
        "connected_components": "connected_components(grid, bg) -> list of components",
        "largest_object": "largest_object(grid, bg) -> cells of biggest component",
        "bounding_box": "bounding_box(cells) -> (r0,c0,r1,c1)",
        "flood_fill": "flood_fill(grid, r, c, new_color) — 4-conn fill",
        "enclosed_regions": "enclosed_regions(grid, bg) -> bg pockets not touching the edge",
        # Palette
        "recolor": "recolor(grid, mapping) — map colours",
        "invert_palette": "invert_palette(grid) — 0↔9, 1↔9, …",
        # Higher-order
        "compose": "compose(f, g, …) — left-to-right function composition",
        "iterate": "iterate(f, n, x) — apply f n times",
        "zip_with": "zip_with(f, g1, g2) — cell-by-cell binary",
        "identity": "identity(grid) — deep copy",
        "apply_program": "apply_program(prog, grid) — run a callable program",
        # v2 multi-channel
        "make_multichannel": "make_multichannel(*channels) — bundle 2D grids into a multichannel grid",
        "extract_channel": "extract_channel(grid, i) — pick channel i (single grid: ok as 0)",
        "combine_channels": "combine_channels(*channels) — alias of make_multichannel",
        "project_luminance": "project_luminance(grid) — mean-merge multichannel → single grid",
    }
    out: List[str] = []
    for n in names:
        out.append(f"  - {n}: {descriptions.get(n, '(no description)')}")
    return out


def _grid_to_str(grid: Any, *, max_rows: int = 8, max_cols: int = 12) -> str:
    """Compact grid rendering for prompt inclusion.

    v2 — if ``grid`` is multichannel (a list of 2D grids), render each
    channel on its own block and label it ``channel i``. Falls back to a
    flat rendering for plain 2D grids.
    """
    if not grid:
        return "[]"
    # Multi-channel detection: list of 2D grids.
    if isinstance(grid, list) and grid and isinstance(grid[0], list) \
            and grid[0] and isinstance(grid[0][0], list):
        blocks = []
        for i, ch in enumerate(grid):
            blocks.append(f"  -- channel {i} --\n{_grid_to_str(ch)}")
        return "\n".join(blocks)
    rows = grid[:max_rows]
    body = []
    for r in rows:
        line = " ".join(str(int(v)) for v in r[:max_cols])
        if len(r) > max_cols:
            line += " …"
        body.append(f"  [{line}]")
    if len(grid) > max_rows:
        body.append("  …")
    return "\n".join(body)


def _render_train_pairs(task: dict, *, max_pairs: int = 3) -> str:
    train = task.get("task", {}).get("train", [])[:max_pairs]
    blocks: List[str] = []
    for idx, pair in enumerate(train, 1):
        inp = _grid_to_str(pair.get("input", []))
        out = _grid_to_str(pair.get("output", []))
        blocks.append(f"-- pair {idx} input --\n{inp}\n-- pair {idx} output --\n{out}")
    return "\n\n".join(blocks)


def build_proposer_prompt(
    task: dict,
    k: int,
    dsl_primitives: List[str],
    examples: List[Dict[str, Any]],
    *,
    include_test_input: bool = True,
    hints: Optional[List[str]] = None,
) -> str:
    """Assemble the prompt for :class:`LLMProposer`.

    The prompt is intentionally compact: <2k tokens for the four canonical
    families. Structure:

    1. Role + format request.
    2. DSL primitive catalogue (name + 1-line description).
    3. 2-3 worked examples for the known task families.
    4. Current task: train pairs + (optionally) test input.
    5. Request: ``K`` candidate programs, one AST tuple per line.

    v2 — when ``hints`` is non-empty, include them as a numbered list and
    explicitly instruct the model to incorporate them. Both task hints
    (``task["hints"]``) and episodic-memory hints (labels of similar past
    traces) flow in via this parameter.
    """
    prim_lines = describe_primitives(dsl_primitives)

    # Render worked examples compactly.
    example_blocks: List[str] = []
    for ex in examples:
        example_blocks.append(
            f"### Family: {ex['family']}\n"
            f"{ex['blurb']}\n"
            f"gold program (copy this AST shape):\n"
            f"  {ex['program_str']}\n"
            f"(If the literal example does not exactly fit, output a variant "
            f"with the same shape — e.g. swap arguments, add a recolor, or "
            f"compose with translate.)"
        )
    examples_text = "\n\n".join(example_blocks) if example_blocks else "(no examples)"

    # Render train pairs.
    train_text = _render_train_pairs(task)

    test_text = ""
    if include_test_input:
        test_input = task.get("task", {}).get("test", [{}])[0].get("input", [])
        test_text = (
            "\n\n-- test input (apply your chosen program to it) --\n"
            + _grid_to_str(test_input)
        )

    # v2 — hint block.
    hint_lines: List[str] = []
    if hints:
        for i, h in enumerate(hints, 1):
            hint_lines.append(f"  {i}. {h}")
    hints_text = ""
    if hint_lines:
        hints_text = (
            "\n\nTASK HINTS (incorporate these in your proposals):\n"
            + "\n".join(hint_lines)
        )

    prompt = (
        "You are an ARC (Abstraction and Reasoning Corpus) program synthesiser.\n"
        "The grid DSL uses Python tuple ASTs. The zero-arg form (\"identity\",) "
        "is sugar for \"the current execution grid\".\n"
        "Any child of an AST that is itself a tuple is recursively compiled as "
        "a sub-program; anything else is a literal.\n"
        "Higher-order primitives: compose, iterate, apply_program.\n"
        + (
            "If TASK HINTS are provided, treat them as authoritative guidance: "
            "prefer programs that directly express the described transformation.\n"
            if hint_lines else ""
        )
        + "\n"
        + "DSL PRIMITIVES (name — description):\n"
        + "\n".join(prim_lines)
        + "\n\n"
        + "WORKED EXAMPLES:\n"
        + examples_text
        + "\n\n"
        + "CURRENT TASK — train pairs:\n"
        + train_text
        + test_text
        + hints_text
        + "\n\n"
        + f"PROPOSE {k} CANDIDATE PROGRAMS in DSL AST syntax, one per line, "
        + f"NO commentary, NO markdown, NO numbering. Each line must be a single "
        + f"valid AST tuple such as (\"rotate\", (\"identity\",), 1) or a "
        + f"compose call. Do not include explanations."
    )
    return prompt