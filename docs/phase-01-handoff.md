# Phase 01 handoff

Verified for issue #8 on 2026-10-09 (Asia/Seoul). Core acceptance passed; local
supplied-player inheritance passed. This is a development checkpoint, not a final
submission or a claim about an unseen grader. AI-written by OpenAI Codex; this
session's LLM usage recording was omitted at the user's request. Earlier records
and attribution remain intact.

## Contracts to reuse

| Boundary | Verified contract |
| --- | --- |
| `omok.simulator.Position(board, side_to_move)` | Owned immutable 19 × 19 tuple rows; `-1` empty, `0` black, `1` white; explicit side; validates shape/values and detects terminal fixtures. Historical reachability is not required. |
| `Position.empty()` | Empty board, black to move. |
| `Position.play((row, column))` | Live position and empty target required; rejects illegal moves without mutation. Returns frozen `Transition(move, color, captured, position)`; each captured record has `cell` and `prior_value`. |
| Child ownership/restoration | Keep the parent reference to return from exploration. Parent, siblings, nested children, and external inputs stay independent. No make/unmake, undo token, counters, hash, or cache. All maintained state is board, side, outcome, reason. |
| Rules | Place, collect all eight-ray pairs before removal, remove their union, then check both colors' maximal runs. Exactly five wins; overlines alone do not. Capture count has no victory role. |
| Terminal convention | Continuing child flips side; terminal child retains the mover, even for an opponent win or simultaneous draw. Loaded terminal fixture retains its supplied side. Check outcome before interpreting side or expanding. |
| Outcomes | `ongoing`/`None`; `black_win` or `white_win`/`exact_five`; `draw`/`simultaneous_wins` or `full_board`. No repetition or rules move cap. |
| `LegalBaseline(color).take_turn(board, time)` | Explicit color, legal row/column tuple on live inputs, no caller mutation; terminal input rejected. Owns input, establishes fallback, returns promptly at <=2 ms. |
| Baseline optional work | One ply across legal candidates, verified strict-win preference, detected opponent-loss avoidance. Score: 4 per captured stone + 1 per adjacent own stone, untuned. Ordered by own adjacency, center distance, row, column. Deadline: 10% of time after 2 ms reserve, capped at 100 ms. No forced defense or search. |
| Public integer handling | Engine accepts integer `__index__`, rejects bool/float/string. Supplied players use built-in integer tuples and nested indexing. This does not establish the grader's acceptance of additional integer types. |
| `offline.runner.run_game` | Players in black/white order; fresh mutable snapshot per call. Separate cumulative clocks in ms, floor remaining time passed; API `None`/CLI `-1` means development unlimited. No invalid-move repair. |
| Runner result | `completed` rules outcome, `capped` experiment limit, or `failed` execution. Mutation, exception, invalid move, and post-return timeout preserve authoritative state and identify color. |
| `offline.replay.load_trace` / `replay` | `omok-game-v2` JSON, v1 reader compatibility. Initial/final states, accepted moves/captures, returned/applied/failure events, clocks, configuration, source identity. Replay invokes no players and rejects malformed/inconsistent/damaged traces. |

See [simulator details](simulator.md) for dense fixture derivation and independent
reference design, and [runner details](runner.md) for event fields, exception
priority, and accounting. `verification.reference.ReferencePosition` uses independent
capture and terminal geometry. Keep deterministic fixtures and differential checks
when replacing baseline behavior or optimizing transitions.

## Integration and dependencies

`omok/` imports only the standard library. `offline/` owns opponent loading and
execution; `verification/` and `tests/` are offline tooling. Experiments live in
`.scratch/`, outside the agent. Python 3.14.3 on macOS 13.7.8 x86_64 is the verified
development runtime; no grader Python version is known. Mypy is optional development
tooling, not an engine dependency; compileall checks syntax, not types.

The unchanged professor bots and recovered release base are in `players/`.
`offline.provided.load_players().create(name, color)` constructs fresh `random`,
`simple`, or `baseline` instances. The baseline adapter inherits the actual release
abstract Player, which stores only `self.color` and requires `take_turn(board, time)`.
This adapter is the verified local public boundary; `LegalBaseline` alone implements
the development protocol. Final submission class/name/metadata remain deferred.
The loader temporarily aliases `player` process-wide, restores the previous alias,
and must be initialized before threaded work. It is trusted local loading.

Both supplied bots ignore `time`; their imports need only standard-library `abc`
and `random`. No NumPy requirement is visible. Source provenance/hashes are in
[issue #7](verification/issue-7.md) and fresh
[integration evidence](verification/issue-8-integration.json). Concrete grader
board/coordinate requirements and official unlimited-time translation remain
unknown. No authoritative local Player source is missing now.

## Evidence and timing

[Acceptance report](verification/issue-8.md): 64 tests passed; 5,561 differential
transitions, 16 sequences per mode, seeds 20261008–20261023 and
20361008–20361023; 1,064 captured stones. Of 32 sequences, 30 reached terminal
rules outcomes and two reached the 240-move verification cap without mismatch.
Eight local and 16 supplied-bot full-budget games completed; zero capped/failed
regular games. Separate deliberate probes produced two caps and one zero-clock
failure. Every returned game trace replayed.

Timing and known hardware are recorded in the report, without a speed or win-rate
gate. These are copy-plus-full-scan transitions, not search nodes per second.
Seeds do not make time-bounded baseline decisions identical across machines.

## Remaining work and checkpoint

The runner measures trusted players after return. A never-returning call is not
interrupted per turn. Verification subprocess deadlines bound the whole experiment,
not each player's invocation. Submillisecond baseline completion is not guaranteed;
an in-progress candidate can exceed its checked deadline. Replay checks internal
consistency and cannot authenticate that logged failures actually occurred.

External gates: unseen grader runtime and concrete types, official unlimited-time
semantics, final inheritance/class naming, team metadata, and submission packaging.
No search, tournament strength claim, or Phase 02 implementation is included.
Request `02_SEARCH_ENGINE_SPEC.md` before starting that separate work order.

The commit titled `Verify Phase 01 acceptance and preserve handoff (#8)` is the
restorable checkpoint; its parent is
`14e4f3fefe0314d7886090d60404fe513a92e16c`. Find it with:

```sh
git log --all --format='%H %s' --grep='Verify Phase 01 acceptance and preserve handoff (#8)'
git worktree add --detach ../omok-phase01 <checkpoint-sha>
```

The checkpoint retains source, tests, contracts, and measured JSON reports. Raw
smoke traces and full command logs remain in ignored `.scratch/` and are not part
of the Git snapshot; rerun the report's commands to regenerate them. Restoring
source/evidence does not require those traces or the local mypy environment.
