"""Standard-conformant example heuristic: `output_equals_majority_of_train_outputs`.

This is a new shallow heuristic that **does** look at the train pairs
(unlike most of the registry, which only inspects the test input).
The rule:

    Predicted output = majority colour across all training outputs.

If any training output is mostly colour 0 except for one other colour,
this heuristic returns that colour everywhere — which is the right
answer for any task where the rule is "fill with the dominant training
output colour."

Registering into the audit registry::

    import sys, os
    sys.path.insert(0, os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "domains", "arc", "audit"
    ))
    from heuristics import HEURISTICS
    from heuristic import output_majority_of_train_outputs

    HEURISTICS["output_majority_of_train"] = output_majority_of_train_outputs
"""
from __future__ import annotations

from collections import Counter
from typing import List, Sequence, Tuple

Grid = List[List[int]]
TrainPair = Tuple[Grid, Grid]


def output_majority_of_train_outputs(
    train_pairs: Sequence[TrainPair],
    test_input: Grid,
) -> Grid:
    """Predict the most frequent colour seen in any training output.

    Output grid matches the shape of the test input.
    """
    counter: Counter = Counter()
    for _, out in train_pairs:
        for row in out:
            counter.update(row)

    if not counter:
        fill = 0
    else:
        # Tie-break by colour value (smaller colour wins) for determinism.
        fill = min(((c, n) for c, n in counter.items()), key=lambda cn: (-cn[1], cn[0]))[0]

    h = len(test_input)
    w = len(test_input[0]) if h else 0
    return [[fill for _ in range(w)] for _ in range(h)]


# --- usage / self-test ------------------------------------------------------

if __name__ == "__main__":
    train = [
        ([[1]], [[1, 1], [1, 1]]),  # output is all 1s
    ]
    test_in = [[0, 0], [0, 0]]
    pred = output_majority_of_train_outputs(train, test_in)
    assert pred == [[1, 1], [1, 1]], f"got {pred}"
    print("heuristic.py: self-test passed; HEURISTIC READY FOR REGISTRATION")
