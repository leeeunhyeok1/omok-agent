# Simulator contract and implementation decision

Chosen for issue #3 on 2026-10-08: immutable owned board copies, with full-board
terminal detection. This is a new engine; the professor's players are unchanged.

```python
from omok.simulator import Position

parent = Position.empty()                  # black to move
transition = parent.play((1, 0))           # row, column, zero-based
child = transition.position
assert parent.board[1][0] == -1
assert child.board[1][0] == 0

fixture = Position([[-1] * 19 for _ in range(19)], side_to_move=1)
```

`Position(board, side_to_move)` copies and validates a 19 × 19 rectangular
sequence, normalizes cell values, and detects its outcome immediately. It accepts
fixture positions regardless of historical reachability or stone-count parity.
The caller must supply color; it is never inferred. Board values are -1 empty,
0 black, 1 white. The primary maintained state is exactly `board`, `side_to_move`,
`outcome`, and `reason`. The board is a tuple of tuple rows; the position and
transition records are frozen. No counters, hashes, caches, or history are maintained.

Cells, color, and coordinates accept Python integers and objects supporting the
integer `__index__` protocol; booleans, floats (even 0.0), and strings are rejected.
Both provided players return tuples of built-in integer coordinates and index
board rows directly. No concrete NumPy array requirement appears in their source.
This establishes compatibility with their visible indexing/coordinate behavior,
not with the absent official Player class or an unknown grader environment.

`play((row, column))` requires a live position and empty in-bounds target, otherwise
raises `ValueError` without state change. Its result exposes:

- `move`: normalized row/column tuple.
- `color`: the mover's explicit color.
- `captured`: sorted immutable records with `cell` and `prior_value`.
- `position`: the independent resulting position with explicit outcome and reason.

The engine copies rows, places the stone, collects all qualifying pairs from the
post-placement board in eight rays, removes their union, then checks maximal runs
for both colors in four orientations. Exactly five wins; overlines alone do not.
No recursive captures, capture-count win, repetition draw, or move limit exists.
Internal child creation skips external board validation because its cells are
already owned and valid; it still performs full terminal detection.

| Outcome | Reason |
| --- | --- |
| `ongoing` | `None` |
| `black_win`, `white_win` | `exact_five` |
| `draw` | `simultaneous_wins` or `full_board` |

A continuing child advances side to the opponent. A terminal child retains the
mover's side, including opponent victories and draws. A loaded terminal fixture
retains its explicitly supplied side. Search must check `outcome` before interpreting
side or expanding children. `play` rejects every terminal position.

To return from a child, retain the unchanged parent reference. Sibling and nested
transitions cannot modify it. To modify a board for another fixture or a player,
create `[list(row) for row in position.board]` and load a new Position if needed.
There is no mutable make/unmake or undo token. Tests inspect every maintained field,
external inputs, rejected moves, consecutive captures, multiple siblings, nested
children, and modified exported snapshots at this public seam.

## Independent reference

`verification.reference.ReferencePosition` implements the same observable
position/transition vocabulary. It enumerates all length-four windows in the four
undirected orientations, accepts the newly placed cell only at either endpoint,
and collects the matching windows before removal. Its terminal detector constructs
complete rows, columns, and diagonals and groups equal cells with `itertools.groupby`.
It never calls the engine's capture or terminal helpers. Shared constants, typing
aliases, and the captured-cell value record do not contain rule logic.

The same literal deterministic expectations run against each implementation;
differential sequences additionally compare every board cell, captured cell/prior
value, outcome, reason, and side. Captures do not count toward victory.

## Independently verified dense fixtures

Generate the full board as `board[r][c] = ((r + 2*c) % 4) // 2` for 0 ≤ r,c < 19.
Along the four orientations, the residue advances by 2, 1, 3, or -1 modulo four.
The horizontal colors alternate; the other orientations have runs of at most two.
Thus no maximal five exists, and the full board is a draw. Both the run-start
engine scan and independently grouped reference lines verify this construction.

For final-placement fixtures, remove `(0, 0)`:

- Black fills it: the only qualifying ray is down-right. `(1, 1)` and `(2, 2)`
  are white and `(3, 3)` is black. Those two cells become vacant and play continues.
  Removal cannot extend any remaining run, so it cannot create a five here.
- White fills it: no capture. Horizontal and down-right first cells are white;
  downward starts black, white, white, which is not a captured pair. Changing
  the corner extends the down-right white run to three, not five. The board is
  a full-board draw.

Tests repeat these constructions with colors complemented, explicitly asserting
starting live status, exact captured sets, outcome, and reason at both rule seams.
