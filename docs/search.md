# Fixed-depth search contract

Issue #10 adds `omok.search.FixedDepthSearch` and
`omok.player.FixedDepthPlayer`. These are development APIs chosen for this ticket;
the simulator, `LegalBaseline`, supplied-player adapters and trace format are
preserved. AI-written by OpenAI Codex. The Phase 01 checkpoint remains
`c0c56fa40826719794f0765fd35464a5c0174cc3`.

```python
from omok.search import FixedDepthSearch, SearchLimits
from omok.simulator import Position
from omok.player import FixedDepthPlayer

root = Position.empty()
engine = FixedDepthSearch()
reference = engine.search(root, 1, reference=True)
production = engine.search(root, 1)
assert production.score == reference.score
assert production.move in reference.optimal_moves

bounded = engine.search(root, 2, limits=SearchLimits(max_nodes=1000))
move = FixedDepthPlayer(color=0, depth=1).take_turn(root.board, 60000)
```

## State and values

Only immutable owned `Position` instances enter search. Public turns copy and
validate input once, with explicit color. Every child uses `Position.play`; parent
references restore exploration without undo operations or shared mutable state.
Traversal counters belong to each call. Terminal outcomes are checked before
evaluating or generating moves, including terminal fixtures at entry.

`engine.score(position, perspective)` accepts explicit black/white perspective.
Win/loss values are integers `+10000`/`-10000`; every draw is `0`. There is no
distance-to-win adjustment. Recursion always flips its logical perspective after
one placement, including terminal children whose stored side retains the mover.
Winner classification comes from `outcome`, never that retained side.

The replaceable evaluator is a callable taking a position and returning a
**black-centric**, board-based integer in `[-4000, 4000]`. Search negates this
value for white, enforcing the same-board zero-sum convention. Out-of-range
values, floats, booleans, NaN and infinity raise `ValueError`; there is no silent
clamping. Default `material_evaluation` counts black stones minus white stones,
bounded by `[-361, 361]`. Captured stones affect that resulting-board count, with
no cumulative capture score. This is minimal untuned material, not a tactical
or mature Omok++ evaluator. Terminal values dominate all permitted evaluators.

## Trees and reference comparison

Depth counts placed stones, irrespective of how many stones a placement captures.
Depth zero scores the root and returns no move. A terminal entry also returns no
move. `take_turn` requires a live root and positive configured depth.

By default every empty cell belongs to the tree at every live node, in row/column
order. There is no locality filter, ordinary cap, extension, selective reduction,
table, or speculative pruning. A custom `candidates(position)` iterable defines a
restricted tree for deterministic verification. Both algorithms use identical
membership and ordering. Coordinates must be built-in integer pairs targeting
empty in-bounds cells; duplicates collapse in first-seen order. Invalid candidates
raise errors. An empty iterable falls back to **all** legal cells.

`reference=True` uses unpruned Negamax and reports the exact root `optimal_moves`
set. Production uses alpha-beta with child window `(-beta, -alpha)`. The root
window is always `(-10001, 10001)`, strictly outside all scores. Cutoffs are
**fail-soft**: a node returns its best observed score rather than clamping to the
window. Internal cutoff values can be bounds; they do not establish tied optimal
root moves. Production therefore reports only its selected move and exact
completed root score, with `optimal_moves=None`. Strict improvement replaces the
selected root move, retaining the first proved best move on ties.

The separately implemented reference recursion shares the validated simulator,
candidate contract and evaluator with alpha-beta. Worked literal-value tests
anchor their signs and recurrence independently of equivalence alone. Tests cover
both colors, exact five, overlines, capture-exposed opponent wins, simultaneous
draws and full-board draws. Ten seeds (0–9) define four-cell restricted trees at
depths 1–4 with signed black-centric weights; default full-width late-board trees
are tested at depths 1–3. Captures can reopen cells in those full-width trees.
These are correctness checks, not evidence of exhaustive 19 × 19 strategy.

## Cancellation and the public player

`SearchLimits` optionally supplies an absolute monotonic `deadline`, `max_nodes`,
and a `cancelled()` predicate. `FixedDepthSearch(clock=...)` permits controlled
clock tests. A live search establishes its first row-major legal fallback before
candidate generation or evaluation. `SearchCancelled` is the intentional signal;
only this exception is caught. Other candidate, evaluator, clock and simulator
errors propagate. State remains intact on either kind of interruption.

`SearchResult` exposes `move`, `score`, `completed`, `optimal_moves`, `nodes`,
`cutoffs`, and `cancellation`. Canceled work returns the established legal fallback,
`score=None`, `completed=False`, no optimal set, and the reason `node_limit`,
`deadline`, or `requested`. Partial work is never represented as a completed score.
Depth zero has no move on completion; terminal entry scoring precedes cancellation.
`nodes` counts live-root and recursive node entries, including leaves, after their
budget checks; a terminal entry performs no traversal and reports zero nodes.
`cutoffs` counts recursive alpha-beta windows closed by `alpha >= beta`.

`FixedDepthPlayer(color, depth=1, max_nodes=10000, max_time_ms=100, search=None)`
implements the existing development `take_turn(board, time)` protocol and exposes
`last_result` without changing the returned coordinate type. It clears old results
at turn entry, including failing calls. The incoming time is remaining total game
milliseconds. The provisional bound follows the Phase 01 baseline: at <=2 ms
return fallback; otherwise allocate `min(max_time_ms, (time - 2) * 0.1)` ms measured
from before board conversion. The offline `-1` sentinel allocates `max_time_ms`;
configured depth/node/time bounds still apply. Other negative times take the
low-time path. Nonfinite/bool time values are rejected. This sentinel is a local
development convention, not established grader behavior.

Cancellation is checked during candidate enumeration, recursion, and before/after
evaluation. Simulator transitions and arbitrary user-supplied callbacks are
cooperative atomic work; they cannot be preempted. Board conversion and fallback
cost are outside those checks. Small budgets and scheduler delays cannot guarantee
a hard deadline; the existing runner still reports actual elapsed-time failures.
A canceled fixed-depth search uses fallback even if some promising root moves
were explored. Completed-iteration retention and the refined clock manager are
issue #11; verified tactical candidates, caching, integrated runner diagnostics and
Phase 02 acceptance belong to issues #12–#15. Final official inheritance/naming and
packaging remain deferred; this class makes no new compatibility claim.

Run `python3 -m unittest tests.test_search -v` and
`python3 -m verification.search`. Acceptance evidence is in
[issue-10.md](verification/issue-10.md).
