# Phase 2 checkpoint and Phase 3 handoff

Correctness and local game reliability verified for issue #15; submillisecond public
clock acceptance remains partial. See [acceptance evidence](verification/issue-15.md)
for commands, counts, hardware, all outcomes and timing failures. AI-written by
OpenAI Codex. This is a development checkpoint, not a final submission.

## Preserve verified boundaries

Keep `Position.play`, independent reference rules, committed iterative Negamax,
alpha-beta, candidate/tactical membership, bounded table and cumulative-clock runner.
Position owns immutable tuple rows; exploration retains parents instead of undoing
mutable state. Terminal outcomes precede leaf evaluation; capture-exposed opponent
wins and simultaneous draws must retain their existing semantics.

The next scoped work is `03_EVALUATION_SPEC.md`. Improve position judgment through
`FixedDepthSearch(evaluator=...)`, or its cooperative evaluator callback receiving
`check`, rather than replacing rules/search. The evaluator returns a black-centric
built-in integer in [-4000, 4000]. The retained Phase 2 material evaluator is
independent of stored side. Phase 3 evaluators may use side-to-move context while
preserving fixed-context perspective inversion and color/context symmetry; see
[the evaluation contract](evaluation.md). Search converts to the
logical perspective; terminals are +/-10000, draws zero, without mate-distance
encoding. Floats/bools/out-of-range outputs raise errors. Current feature is only
black stone count minus white stone count on the resulting board (range +/-361).
No capture-total reward, threat features, tuning or mature evaluation is claimed.

`IterativePlayer(color).take_turn(board, remaining_ms)` copies input, uses explicit
color, establishes a legal fallback, and retains only a full iteration's move,
score, depth and PV. Diagnostics are optional and remain separate from the returned
integer coordinate pair. Errors propagate to the runner. The provided offline
adapter supplies actual Player inheritance; final names remain deferred.

## Candidates, ordering, cache and clocks

Candidate defaults are radius 2, cap 24; center on an empty board. Whole-board
verified wins and safe responses bypass the ordinary cap. A defense is safe only
after full rule-aware immediate-reply checking; partial scans keep all legal cells
and expose incomplete diagnostics. No optional extensions are implemented.
Static rank `19 * adjacent_stones - center_Manhattan_distance` selects ordinary
membership. Search ordering/PV/table hints can reorder that membership and cannot
change it. Static rank is not leaf evaluation or tactical proof.

Table keys use full immutable Position (board, side, outcome/reason), engine namespace,
explicit compatibility version, callback/policy identities, score bounds and extension
version, plus exact remaining depth. Python dictionary equality verifies collisions;
no incremental/Zobrist hash exists. Exact-depth values only, including leaves;
other-depth compatible entries may supply legal member hints. Bounds classify
against the effective window after probe tightening. Capacity 4096, oldest-write
replacement; exact entries resist weaker same-key replacement. Entries/PVs over
64 plies are not retained. Completed children may survive a canceled parent;
uncompleted ancestor exact results must not.

When Phase 3 changes callback behavior in place (weights/closures/external feature
configuration), bump `search.compatibility` and clear `search.table`. Replacing
callback/policy objects changes identity automatically, but clearing releases stale
bounded entries immediately. Create fresh players or explicitly clear tables between
games; preserve immutable evaluator/configuration IDs for comparisons. Do not rely
on callback names or board alone to identify compatible values.

`TimePolicy`: positive R allocates `min(100, max(0, R-2) * 0.5 * 0.1)` ms,
starting before conversion. Half of post-margin time remains reserved, turn fraction
0.1, soft stop at 0.8 of allocation. The `-1` local sentinel still caps at 100 ms;
other zero/negative inputs return fallback. Default bounds depth 8/nodes 10000.
No fixed remaining-move estimate exists. Cooperative checks cover tactics,
sorting/order/evaluation/recursion/table writes; transitions, conversion and OS
scheduling remain atomic. Profiling indicates tactics/candidate scans dominate;
new leaf features should check cancellation inside costly loops and stay within the
score bound. Re-measure actual public calls when feature costs change.

## Regression suite and strength context

Retain all existing fixtures. `tests/test_tactics.py`, `tests/test_search.py`,
`tests/test_transposition.py`, `tests/test_iterative.py`, and `tests/test_integration.py`
cover exact-five/overline/capture/draw behavior, cap-one capture defense `(7,7)`,
independent exhaustive replies, matched reference trees, bound signs/config/depth,
and cancellation preserving full commits/state. Keep score/value comparisons with
matched trees and fresh/compatible tables whenever evaluator configuration changes.

Local 60-second cumulative-budget games: 8/8 baseline wins, 8/8 RandomPlayer wins,
0/8 SimplePlayer wins. This is not a promotion or class-rank guarantee. Preserved
SimplePlayer loss traces are starting points for Phase 3 analysis. Their causes
are hypotheses until replay/diagnostic alternatives establish them. Tactical
correctness remains a gate before strength measurements. Low-clock probes had 48
observed overruns at 0.001/0.1 ms; no game exhausted its incoming clock. Do not
turn local reliability into a hard-timeout claim or promise unseen grader behavior.

## Restorable checkpoints and attribution

Phase 1 checkpoint remains `c0c56fa40826719794f0765fd35464a5c0174cc3`.
The issue #15 commit below preserves Phase 2 source, tests, evidence and all 48
compressed game traces; it is a passing correctness checkpoint with the explicit
timing qualification above. Restore in a separate worktree without altering local
user changes:

```sh
git worktree add --detach ../omok-phase01 c0c56fa40826719794f0765fd35464a5c0174cc3
git log --all --format='%H %s' --grep='Verify Phase 2 acceptance and preserve handoff (#15)'
git worktree add --detach ../omok-phase02 <issue-15-commit-sha>
cd ../omok-phase02
python3 -m unittest discover -s tests -v
python3 -m verification.acceptance replay
```

Python/standard library suffice; optional mypy and the previous machine's `.scratch`
logs are unnecessary to restore/run. `verification.acceptance` regenerates profiling
and games. It replaces output for a selected mode, so copy results before rerunning.
The baseline implementation and supplied professor files are unchanged.

Earlier disclosure records and AI source attribution are retained in Git history;
pre-existing working-tree deletions under `llm-usage/` and the untracked phase spec
are excluded from this commit. This task's visible interaction export is
`llm-usage/issue-15-interaction.jsonl`, using the existing exporter (reasoning/system
prompts excluded). It is a snapshot before commit/final response; rerun the exporter
against the same local session afterward to capture trailing records. No paid plan,
team metadata or model identity beyond available runtime information is invented.
Final submission disclosure completeness must be checked against the actual retained
sessions before packaging; this checkpoint does not claim that packaging is done.
