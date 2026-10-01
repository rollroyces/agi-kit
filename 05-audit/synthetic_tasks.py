"""Hand-rolled synthetic ARC-style tasks for the audit harness.

Each task is the standard ARC JSON shape:
    {
        "task_id": str,
        "train": [{"input": grid, "output": grid}, ...],
        "test": [{"input": grid, "output": grid}]
    }

We include at least two tasks that are *trivially solvable* by one of the
shallow heuristics so the harness flagging is exercised.

The grid shapes here are small and the colors stay in 0-9.
"""

TASKS = []


def _make(task_id, train, test_in, test_out):
    return {
        "task_id": task_id,
        "train": [{"input": tin, "output": tout} for tin, tout in train],
        "test": [{"input": test_in, "output": test_out}],
    }


# ---------------------------------------------------------------------------
# Task 1 — horizontal mirror (trivially solvable by `mirror`)
# ---------------------------------------------------------------------------

# Train pairs demonstrate: output = horizontal flip of input.
# Test grid has a clear "arrow" pointing left; flipping it makes it point right.
TASK_MIRROR = _make(
    "mirror_lr",
    train=[
        ([[1, 0, 2], [0, 0, 1], [2, 1, 0]],
         [[2, 0, 1], [1, 0, 0], [0, 1, 2]]),
        ([[3, 3, 0], [3, 0, 3], [0, 3, 3]],
         [[0, 3, 3], [3, 0, 3], [3, 3, 0]]),
    ],
    test_in=[[5, 0, 6],
             [0, 5, 0],
             [6, 0, 5]],
    test_out=[[6, 0, 5],
              [0, 5, 0],
              [5, 0, 6]],
)
TASKS.append(TASK_MIRROR)


# ---------------------------------------------------------------------------
# Task 2 — identity (trivially solvable by `identity`)
# ---------------------------------------------------------------------------

# Output equals input. Easy to spot: the test grid has no transformation cue.
TASK_IDENTITY = _make(
    "identity",
    train=[
        ([[1, 1, 2], [2, 1, 1]],
         [[1, 1, 2], [2, 1, 1]]),
        ([[4, 4, 4], [4, 5, 4], [4, 4, 4]],
         [[4, 4, 4], [4, 5, 4], [4, 4, 4]]),
    ],
    test_in=[[7, 7, 8],
             [8, 7, 7],
             [7, 8, 7]],
    test_out=[[7, 7, 8],
              [8, 7, 7],
              [7, 8, 7]],
)
TASKS.append(TASK_IDENTITY)


# ---------------------------------------------------------------------------
# Task 3 — palette majority fill (trivially solvable by `palette_majority`)
# ---------------------------------------------------------------------------

# Output is a uniform grid of the most common color in the input.
# In each example 0 is overwhelmingly present.
TASK_MAJORITY = _make(
    "fill_majority",
    train=[
        ([[0, 1, 0], [0, 0, 2], [0, 0, 0]],
         [[0, 0, 0], [0, 0, 0], [0, 0, 0]]),
        ([[3, 0, 0], [0, 0, 0], [0, 4, 0]],
         [[0, 0, 0], [0, 0, 0], [0, 0, 0]]),
    ],
    test_in=[[0, 0, 5],
             [0, 0, 0],
             [6, 0, 0]],
    test_out=[[0, 0, 0],
              [0, 0, 0],
              [0, 0, 0]],
)
TASKS.append(TASK_MAJORITY)


# ---------------------------------------------------------------------------
# Task 4 — background swap (trivially solvable by `background_swap`)
# ---------------------------------------------------------------------------

# Output swaps background (0) with the rare color (each example uses a
# different rare color, but the rule is structural: 0 <-> rare-non-zero).
TASK_BG_SWAP = _make(
    "bg_swap",
    train=[
        ([[0, 0, 1], [1, 0, 0], [0, 1, 0]],
         [[1, 1, 0], [0, 1, 1], [1, 0, 1]]),
        ([[0, 2, 0], [0, 0, 2], [2, 0, 0]],
         [[2, 0, 2], [2, 2, 0], [0, 2, 2]]),
    ],
    test_in=[[0, 3, 0],
             [0, 0, 0],
             [3, 0, 3]],
    test_out=[[3, 0, 3],
              [3, 3, 3],
              [0, 3, 0]],
)
TASKS.append(TASK_BG_SWAP)


# ---------------------------------------------------------------------------
# Task 5 — diagonal replicate (trivially solvable by `diagonal_replicate`)
# ---------------------------------------------------------------------------

# Output is the input tiled into a 2x2 block grid (4 copies).
TASK_DIAG = _make(
    "diag_replicate",
    train=[
        ([[1, 2], [3, 4]],
         [[1, 2, 1, 2],
          [3, 4, 3, 4],
          [1, 2, 1, 2],
          [3, 4, 3, 4]]),
        ([[7, 8], [9, 0]],
         [[7, 8, 7, 8],
          [9, 0, 9, 0],
          [7, 8, 7, 8],
          [9, 0, 9, 0]]),
    ],
    test_in=[[2, 2],
             [2, 5]],
    test_out=[[2, 2, 2, 2],
              [2, 5, 2, 5],
              [2, 2, 2, 2],
              [2, 5, 2, 5]],
)
TASKS.append(TASK_DIAG)


# ---------------------------------------------------------------------------
# Task 6 — palette invert (trivially solvable by `palette_invert`)
# ---------------------------------------------------------------------------

# Each color c becomes 10 - c (with 0 <-> 9 swap).
TASK_INVERT = _make(
    "palette_invert",
    train=[
        ([[1, 2, 3], [4, 5, 6]],
         [[9, 8, 7], [6, 5, 4]]),
        ([[7, 0, 1], [2, 3, 9]],
         [[3, 9, 9], [8, 7, 1]]),
    ],
    test_in=[[4, 5, 6],
             [7, 8, 9]],
    test_out=[[6, 5, 4],
              [3, 2, 1]],
)
TASKS.append(TASK_INVERT)


# ---------------------------------------------------------------------------
# Task 7 — largest-object (trivially solvable by `largest_object`)
# ---------------------------------------------------------------------------

# Multiple blobs of non-background color; output keeps only the biggest.
TASK_LARGEST = _make(
    "largest_object",
    train=[
        ([[0, 0, 0, 0],
          [0, 2, 0, 2],
          [0, 2, 0, 0],
          [0, 0, 0, 0]],
         [[0, 0, 0, 0],
          [0, 2, 0, 0],
          [0, 2, 0, 0],
          [0, 0, 0, 0]]),
        ([[0, 1, 0, 1],
          [0, 1, 0, 0],
          [0, 1, 0, 1],
          [0, 0, 0, 0]],
         [[0, 1, 0, 0],
          [0, 1, 0, 0],
          [0, 1, 0, 0],
          [0, 0, 0, 0]]),
    ],
    test_in=[[0, 0, 0, 0, 0],
             [0, 3, 0, 3, 0],
             [0, 3, 0, 0, 0],
             [0, 3, 0, 3, 0],
             [0, 0, 0, 0, 0]],
    test_out=[[0, 0, 0, 0, 0],
              [0, 3, 0, 0, 0],
              [0, 3, 0, 0, 0],
              [0, 3, 0, 0, 0],
              [0, 0, 0, 0, 0]],
)
TASKS.append(TASK_LARGEST)


# ---------------------------------------------------------------------------
# Task 8 — non-trivial composite rule (no shallow heuristic should solve it)
# ---------------------------------------------------------------------------

# Rule: rotate 90 deg clockwise AND recolor: original color c -> (c+3) % 10.
# None of the eight shallow heuristics reproduces this.
def _rot90(g):
    h, w = len(g), len(g[0])
    return [[g[h - 1 - r][c] for r in range(h)] for c in range(w)]

def _shift(g, k):
    return [[(c + k) % 10 for c in row] for row in g]

_rot_in = [[1, 2, 3], [4, 5, 6]]
_rot_out = _shift(_rot90(_rot_in), 3)

_rot_in2 = [[7, 8], [9, 0], [1, 2]]
_rot_out2 = _shift(_rot90(_rot_in2), 3)

TASK_HARD = _make(
    "rotate_then_shift",
    train=[(_rot_in, _rot_out), (_rot_in2, _rot_out2)],
    test_in=[[2, 0, 4],
             [5, 1, 7]],
    test_out=_shift(_rot90([[2, 0, 4], [5, 1, 7]]), 3),
)
TASKS.append(TASK_HARD)


# ---------------------------------------------------------------------------
# Task 9 — non-trivial (intentional "shape-specific XOR" — no heuristic wins)
# ---------------------------------------------------------------------------

# Rule: output[i][j] = (input[i][j] XOR input[i][len-1-j]) % 10.
# This is a row-wise XOR with the row's mirror; only the rare shape
# matches the test output. None of the eight heuristics produce this.
def _row_xor(g):
    return [[(g[i][j] ^ g[i][len(g[0]) - 1 - j]) % 10 for j in range(len(g[0]))] for i in range(len(g))]

_xor_in = [[1, 4], [2, 5], [3, 6]]
_xor_out = _row_xor(_xor_in)

_xor_in2 = [[7, 2, 7], [0, 0, 0]]
_xor_out2 = _row_xor(_xor_in2)

_xor_test_in = [[8, 3], [4, 9], [6, 1]]
TASK_HARD2 = _make(
    "row_xor_mirror",
    train=[(_xor_in, _xor_out), (_xor_in2, _xor_out2)],
    test_in=_xor_test_in,
    test_out=_row_xor(_xor_test_in),
)
TASKS.append(TASK_HARD2)


if __name__ == "__main__":
    for t in TASKS:
        print(f"{t['task_id']}: train={len(t['train'])}, test_in={len(t['test'][0]['input'])}x{len(t['test'][0]['input'][0])}")