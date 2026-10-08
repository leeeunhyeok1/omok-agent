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

## Issue #11: committed iterations and total-clock policy

`FixedDepthSearch.iterative(position, max_depth, limits=None, soft_deadline=None)`
searches depths 1 through the configured maximum under one cumulative node/deadline
budget. It establishes a row-major legal fallback before invoking callbacks. Only a
fully completed root search replaces the committed result. `completed` means a
coherent iteration exists, even when a later iteration was canceled; inspect
`cancellation` to determine why work stopped. A terminal entry has a score and no
move, with depth zero.

`SearchResult` now also contains `completed_depth`, `attempted_depth`,
`principal_variation`, and `pv_status`. On cancellation before depth 1, the score
is absent, completed depth is zero, and PV status is `unavailable`. After completion,
PV status is `complete`: replay the committed line until its depth horizon or an
earlier rules terminal. Partial deeper diagnostic lines are discarded rather than
exposed as completed PVs. `attempted_depth` records the interrupted iteration;
a `soft_stop` between iterations leaves it at the last attempted depth. Nodes and
cutoffs count all iterations, including interrupted work; they are not part of the
committed score/line. There is no persistent tree, hash, table, or mutable board.

`IterativePlayer(color, max_depth=8, max_nodes=10000, policy=None, search=None)`
implements the development public turn boundary. `last_result`, `last_elapsed_ms`,
and `last_allocation_ms` expose cheap diagnostics without writing or printing.
The monotonic timer starts before input conversion. Conversion validates the whole
board and its live outcome; fallback is established before optional search work.
Errors propagate, with no result from an earlier turn retained.

`TimePolicy` exposes provisional tunable defaults:

- Return margin: 2 ms.
- Later-turn reserve fraction: 0.5 of the time after that margin.
- Turn fraction: 0.1 of the unreserved remainder.
- Maximum allocation: 100 ms.
- Soft deadline: 0.8 of that allocation, measured from public entry.

For positive remaining milliseconds R, allocation is
`min(100, max(0, R - 2) * (1 - 0.5) * 0.1)` ms. The hard cooperative deadline is
public entry plus that allocation. The soft deadline prevents starting another
iteration late in the allocation; work already started may continue up to the
hard deadline. All overhead consumes the same allocation. No empty-cell count or
fixed maximum number of future placements enters this formula. Fractions are
strictly between zero and one; nonfinite/bool time values are rejected. Zero and
negative time select fallback, except exactly `-1`: the established **local**
unlimited convention still receives a 100 ms allocation and finite depth/node
limits. The supplied Player base and bots do not resolve official sentinel
translation. This remains a development player, pending final inheritance/naming.

`SearchLimits.check(clock)` is the shared cancellation mechanism available to the
later tactical layer. Candidate enumeration, recursion, and leaf entry/exit check
it; default material evaluation also checks per row. Expensive extensions may use
`cooperative_candidates(position, check)`,
`cooperative_evaluator(position, check)`, or `ordering(position, move, check)`.
Each should invoke its supplied checkpoint inside expensive loops. Ordering ranks
validated candidate coordinates by descending integer priority, with stable ties;
it does not alter membership. Both fixed-depth algorithms use the same ordering.
Legacy one-argument callbacks remain supported with checks before/after their work.
Only `SearchCancelled` is caught. Unexpected errors remain visible to the runner.

Simulator conversion/transitions, built-in sorting (at most 361 moves), and legacy
callbacks remain atomic. Cooperative checks cannot preempt blocking callbacks or
OS scheduling. The 2 ms margin is provisional, not a hard-timeout guarantee.
The actual timing report records tiny-clock overruns and an unexplained 143 ms
spike on a 100 ms allocation. The runner's cumulative clocks and failure reporting
remain authoritative. Tactical membership, transposition caching, tuning, and
full Phase 02 acceptance remain later tickets.

```sh
python3 -m unittest tests.test_iterative -v
python3 -m verification.iterative
```

See [issue #11 evidence](verification/issue-11.md).


## Issue #12: verified tactics and local candidates

`IterativePlayer` now defaults to `FixedDepthSearch(tactics=TacticalPolicy())`.
Explicitly supplied engines remain configurable. `FixedDepthSearch()` still defines
the full legal tree used by the original reference checks. To use tactical membership
with either recursion, pass `tactics=TacticalPolicy(radius=2, cap=24)`; this policy
replaces custom candidate callbacks. No optional tactical extensions are added.

`TacticalPolicy.analyze(position, check)` returns immutable `TacticalResult`:
unique legal `candidates`, separately verified `wins`, initial opponent `threats`,
and verified `defenses`. `complete`, `wins_complete`, `threats_complete`, and
`defenses_complete` distinguish completed enumeration from individual verified
moves. `defenses` is enumerated only when the opponent has a strict immediate
win; otherwise its completed set is empty. `cancellation` is the shared control
signal reason. Terminal boards return an empty completed report. `classify`
distinguishes strict mover win, draw, capture-induced opponent win and continuation
from the simulator's complete resulting outcome, using explicit mover color.

Immediate wins scan the entire legal board for maximal own runs of exactly five
through a hypothetical placement, then verify every qualifying move through
`Position.play`, including captures and both colors' terminal lines. This geometric
filter is complete on live boards: a mover cannot capture its own stones and any
new own five must include the placement. It uses no locality or ranking restriction.
It does not treat overlines or simultaneous wins as strict wins. Captures can
expose the other color's five, so the filter alone never establishes a win.

When the opponent has immediate wins, every legal response is simulated. An
already verified threat may refute a response quickly, but a surviving continuation
must pass a complete immediate-win scan on its resulting board. This includes
reopened cells and newly created threats. A terminal strict win or draw is a safe
response; a capture-induced opponent win is rejected. No uniqueness assumption
is made for the specified `(7, 7)` capture defense. A completed empty defense set
is not encoded as a forced-loss score: the ordinary tree and normal search score
remain available.

Ordinary locality uses Chebyshev distance at most `radius` from any occupied cell.
Defaults are provisional radius 2 and cap 24; radius accepts 0–18, cap any positive
integer. An empty board opens at `(9, 9)`. If locality yields no cells, ordinary
selection starts from all legal cells. Default static rank is `19 * adjacent_stones
- Manhattan_distance_to_center`; it is an untuned ordering aid, never tactical truth.
`ordinary_rank(position, move, check)` is configurable. It selects ordinary capped
membership independently of PV or search-ordering hints, with coordinate ties.

Verified wins bypass the ordinary cap. If complete threat enumeration finds safe
responses, membership contains **every** verified response and win, bypassing the
cap; other moves are excluded on the basis of complete immediate-loss checks.
This establishes one-ply safety only. Otherwise membership combines capped
ordinary choices and all verified wins. `full_width=True` retains all legal moves
while performing the same tactical validation, for tractable full-width comparisons.

If any tactical or membership work is interrupted, the report retains **all legal
cells**, ignoring locality and cap. Partially verified defenses remain individual
proofs only; unexamined responses stay unknown. Search unwinds at the expired
checkpoint and returns its last complete iteration or legal fallback. Before any
iteration completes, an independently verified strict win may replace fallback,
with absent score and depth zero. Later incomplete work never replaces committed
move, score, depth or PV. `SearchResult.tactics` records the latest root analysis
and may therefore be incomplete alongside a previously committed result.
`root_candidate_count` counts that root's selected membership; zero means generation
was not reached. Skipped low-time tactics have `tactics=None`, not completed safety.

Membership and ordering are separate. Selected moves are ordered by verified win,
verified defense, previous completed PV hint for the same immutable position, then
static/user ordering, with stable membership ties. Each iteration's PV hints are
local and discarded after the call. Deterministic fixed-depth reference calls have
no prior PV hints, and use the same membership and ordering as fixed-depth alpha-beta.
Iterative hints change ordering only. `SearchLimits.check` runs inside tactical
loops, locality, rank generation, sort comparisons, PV hint construction and the
existing recursion. `max_nodes` still counts recursive visits, not tactical simulator
probes. Conversion, each simulator transition and blocking custom callbacks remain
atomic cooperative work. No table or persistent tactical cache is introduced.

Run `python3 -m unittest tests.test_tactics -v` and
`python3 -m verification.tactics`. The latter exhaustively compares independently
resolved reference replies on small live fixtures, then records actual public turn
clocks including a decreasing cumulative clock. See
[issue-12.md](verification/issue-12.md) for acceptance evidence and timing limits.


## Issue #13: bounded compatible transpositions

`FixedDepthSearch(table=TranspositionTable(capacity=4096), compatibility=...)`
enables caching. The default fixed-depth engine remains uncached; the default
`IterativePlayer` owns a 4096-entry table. Reference recursion neither probes nor
stores table entries or uses table hints. Root searches still regenerate membership
and traverse root children, preserving root tactical diagnostics and committing
only completed roots. Completed roots are stored for later ordering hints.

### Identity and compatibility

Keys contain the full immutable `Position` (361 cells, explicit side to move and
rule-derived outcome/reason), compatibility snapshot and **exact** remaining depth.
Python's dictionary hash locates entries; full equality checks resolve collisions.
No side is inferred from stone counts, and no capture totals enter identity. There
is no incremental/reversible hash to restore after captures or cancellation.
Terminal nodes are resolved before probing, using the explicit score perspective
because terminal simulator positions retain the mover as `side_to_move`.

`engine.cache_compatibility()` exposes the current namespace for diagnostics and
controlled fixtures. Each engine has its own namespace, even if engines share a
table. Snapshots retain callback identities for evaluator, cooperative evaluator,
candidates, cooperative candidates, tactics and ordering; replacing any of them
segregates values and hints. Score bounds and the no-extensions policy version also
belong to the snapshot. Identity wrappers retain strong references, preventing
callback-ID reuse. Frozen `TacticalPolicy` replacement automatically segregates
its radius, cap, full-width and ordinary-rank changes.

`engine.compatibility` is an explicit hashable version token. Bump it whenever
mutable callback state changes evaluation, membership, extensions or score meaning.
For example, set `engine.compatibility = ('evaluation-v2', 'tactics-v3')` after
changing weights captured by an evaluator closure. Callbacks must be deterministic
for their position/configuration, and configuration must remain stable throughout
one search call. Future tactical extensions must version their complete tree policy
through this mechanism. Mutating a closure without updating the token violates the
cache contract. Arbitrary callback dependencies cannot be inferred automatically.

Both verification and production reuse values only at **equal** remaining depth
and matching policy. There is no production minimum-depth substitution: a deeper
heuristic score is not represented as the shallower fixed-depth value. The newest
retained compatible move can order another depth, after validating built-in integer
coordinates, legality and current candidate membership. Hints never add candidates,
alter ordinary capped membership or outrank verified wins/defenses.

### Bounds, lines and interruption

`TableEntry` records depth, fail-soft score, `exact`/`lower`/`upper`, best move and
a replayable principal variation. Exact compatible values return directly. A lower
bound raises alpha; an upper bound lowers beta. A closed window returns that bound.
Otherwise save the **tightened** alpha/beta window before exploring children. A
completed value at or below that alpha is upper; at or above that beta is lower;
strictly between is exact. This conservative rule avoids classifying a fail against
a cached tightening as exact. Opposite bounds are not merged into exact entries.
Existing exact entries are protected against replacement by a weaker bound.

Nonleaf value probes also require their best move to be legal and selected in the
current candidates, and their saved line to start with that move. Leaf evaluations
are stored only after the evaluator and final cancellation check complete. Other
nodes and roots store only after all required children or a valid alpha-beta cutoff
finish and the final checkpoint succeeds. A cutoff establishes a completed bound,
not an exact full-window result. Cancellation and unexpected exceptions retain
fully completed children but create no entry for the incomplete ancestor. Iterative
move, score, depth and PV remain those of the last completed root iteration; partial
work does not overwrite the commitment. Unexpected errors continue to propagate.

Scores retain the fixed `+/-10000` win convention without mate-distance encoding,
so no ply normalization is needed. Saved PVs preserve the existing complete-line
contract on exact hits, through the depth horizon or an earlier terminal.

### Memory, replacement and lifecycle

`TranspositionTable` has an immutable nonnegative entry capacity (zero disables
storage), `probe`, `store`, `hint`, `clear`, `len(table)`, `hits` and `evictions`.
Replacement evicts the oldest stored entry; replacing a key makes it newest.
Probes do not refresh age. The secondary hint index has at most one pointer per
retained position/configuration and releases pointers on replacement/eviction.
PV payloads are capped at 64 plies; longer completed lines are simply not stored.
Thus count and engine-generated board/line payloads remain bounded. Version tokens
and custom callbacks are caller-owned configuration objects; their own allocation
is outside the table's control. Eviction changes available acceleration only.

Tables persist across turns. Use `player.search.table.clear()` at a new-game
boundary, or construct a new player; no game boundary is guessed from board counts.
A version change segregates rather than immediately deletes old entries, which
remain within the same capacity and age out. `clear()` immediately releases all
entries/hints and resets counters. Clearing is also available after a configuration
change when retaining old namespaces is undesirable.

Run `python3 -m unittest tests.test_transposition -v`. See
[issue #13 acceptance](verification/issue-13.md) for checks and review evidence.

## Issue #14: integrated diagnostics

`IterativePlayer.diagnostics()` explicitly returns a JSON-ready snapshot of the
latest successful call, or `None` after an error/before a call. It preserves the
coordinate return contract and includes engine version, evaluator identity and
configuration (depth/node/time policy, tactical radius/cap/full-width/rank identity,
candidate and ordering identities, compatibility token, table capacity). Callable
identities are qualified names bounded to 256 characters. For custom callbacks with
mutable configuration, callers must version that state using the existing explicit
compatibility token; a name alone does not fingerprint callback contents.

Move, latest root candidate count, tactical enumeration completeness flags and
cancellation, fallback reason, completed/attempted depth and committed score are
recorded. Skipped tactics are `None`. Tactical reports may describe an interrupted
new iteration alongside a committed older score/line. PV coordinates are capped at
64 plies: status is `truncated` if shortened, otherwise the result's `complete` or
`unavailable`. A complete line reaches completed depth or an earlier rules terminal;
no partial deeper PV is substituted. Elapsed time covers the public call from entry
through conversion/search/return preparation; allocated and incoming remaining
milliseconds and cancellation reason accompany it. The runner's independently
measured public elapsed time remains authoritative for cumulative clock accounting.

Counters on `SearchResult` and diagnostics cover all iterations of that call,
including interrupted work, and start at zero each call:

- `nodes`: recursive node visits admitted by the node limit, including roots/leaves;
  tactical simulator checks and move hints are excluded.
- `cutoffs`: recursive alpha-beta closed-window cutoffs, including cached bound
  closures; exact cache returns are excluded.
- `table_probes`: exact-depth value lookups at nonterminal recursive children,
  including depth-zero leaves. Root/hint lookups and reference traversal are excluded.
- `table_hits`: those probes that find a compatible same-depth entry, before
  best-move/membership validation. An unusable entry may count as a hit.
- `table_value_cutoffs`: probes whose exact value or closed bound window avoids
  further recursion/evaluation, including exact cached leaves.
- `table_size`: retained entries at snapshot time, persistent across turns and
  bounded by configured capacity. It is separate from per-call counters and the
  table's older lifetime `hits`/`evictions` diagnostics.

Low-time fallback has zero counters, absent score, unavailable PV and no tactical
completeness claim. The engine retains only its last result; snapshots contain no
boards, full tactical move sets, table entries or per-node logs.
