# Local baseline and game runner

AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4. Verified on Python 3.14.3;
the grader version and final submission arrangement remain unresolved. Local
inheritance through the recovered release Player is verified by issue #7.

```sh
python3 -m offline --seed 20261008 --output .scratch/game.json
python3 -m offline --baseline-color white --black-ms 60000 --white-ms 60000
python3 -m offline --fixture dense --output .scratch/dense.json
python3 -m offline --start opening.json --move-cap 200
python3 -m offline --black-ms -1 --white-ms -1 --move-cap 100
python3 -m offline --replay .scratch/game.json
python3 -m verification.smoke
python3 -m verification.smoke --issue 5
python3 -m verification.smoke --issue 6
python3 -m unittest discover -s tests -v
```

`opening.json` must contain `board` (19 rows of 19 integer cells) and explicit
`side_to_move` (0 or 1). Built-in starts are `empty`, `mover-win`, `opponent-win`,
`simultaneous`, and `dense`. Fixtures establish geometry, not historical reachability.
The live capture fixtures only produce their named result when `(8, 10)` is played;
the baseline may choose another legal move. Controlled runner tests verify those
results. Default start is empty, black to move. Coordinates are `(row, column)`.

`omok.player.DevelopmentPlayer` defines explicit `color` and
`take_turn(board, time)`. `LegalBaseline(color)` owns and validates its input,
establishes a legal fallback, and immediately returns it at incoming time <=2 ms.
With more time it examines all legal one-ply candidates (no candidate pruning),
ordered by own adjacent stones, Manhattan distance to center `(9, 9)`, row, and
column. Each child resolves captures and both colors' exact-five results before
classification. It immediately returns a verified strict win, rejects directly
detected opponent wins, and scores the other explored children by **4 per captured
stone + 1 per adjacent own stone**. Equal scores retain the first candidate in that
order. Simultaneous wins remain draws, with no strict-win bonus. These numerical
weights are temporary, untuned baseline parameters; no forced-defense enumeration
or multi-ply search is performed. Optional work uses at most 10% of remaining time
after a 2 ms reserve, capped at 100 ms; unlimited mode still caps that work at 100 ms.
These are temporary development choices, without tuned weights or strength claims.
The monotonic deadline starts before public input conversion, is checked before
candidate preparation and each simulation, and again before optional scoring. A
transition or scoring call already in progress can run beyond its check deadline;
the runner measures the whole call. An evaluation exception skips that score while
preserving a known safe legal choice. Immutable child copies leave the owned parent,
sibling candidates, and caller input unchanged during failures or early stopping.
Tiny positive time cannot guarantee a return within a submillisecond budget.
Terminal input is rejected. Replace move selection here for Phase 02 without
changing the runner. Agent imports are Python standard library plus `omok.simulator`;
no offline runner, supplied bot, network, or third-party dependency is imported.

`offline.opponents.SeededSmokePlayer` uniformly chooses an empty cell using its
own seeded random generator. It is independently AI-authored and is **not** the
professor's `RandomPlayer`. Each CLI invocation instantiates fresh independent
players with their assigned colors. `--opponent random` and `--opponent simple`
select the unchanged supplied bots. `offline.provided.load_players()` loads their
recovered release `players/player.py` base under a unique module name and temporarily
aliases it as `player` for the original imports, restoring the previous alias.
Use this trusted loader before threaded work; its import alias is process-global.
Each `create(name, color)` constructs fresh state. Its `baseline` class inherits
both `LegalBaseline` and the real abstract `Player`, explicitly initializing both;
move selection and board ownership remain in `LegalBaseline`. This development
adapter lives outside the submitted agent and adds no strategy or move repair.
The base stores only `self.color` and requires `take_turn(board, time)`. Supplied
bots use nested indexing and ignore `time`; no concrete board or coordinate type,
or official unlimited-time translation, is specified by these sources.
The CLI seeds the original RandomPlayer's module-global RNG once per subprocess;
it does not replace its strategy. Full integration uses finite clocks. Local `-1`
remains a development convention. See [issue #7 evidence](verification/issue-7.md).

`offline.runner.run_game` accepts players in black/white order, an optional owned
`Position`, per-color budgets, a move cap, and a monotonic clock. The Python API
uses `None` for unlimited; CLI `-1` maps to it. Development players receive `-1`
in that mode. Finite budgets include 60,000 ms per player and may differ by color.
The runner measures each call with `time.monotonic`, subtracts only that player's
elapsed milliseconds, and passes **floor(remaining_ms)**. A positive fraction below
1 ms is passed as zero; exhaustion is tested against the unrounded remaining clock.
A call returning at exactly its remaining budget may be accepted; one exceeding it
is rejected before applying its move. Rule-check and logging overhead outside the
call is not charged to either player's clock.

Each call receives fresh mutable rows copied from immutable authoritative state.
Snapshot mutation, exceptions, invalid moves, and timeout stop the game, identifying
the player/color and preserving exception details and all detected violations.
Priority for concurrent violations is exception, mutation, timeout, invalid move;
coordinate validation runs only if earlier checks passed. Illegal moves are never
repaired. Coordinates follow `Position.play`: integer `__index__` values accepted,
booleans/floats rejected. A terminal start stops without calling either player.

`completed` means a rules win or draw. `capped` means the configured number of
accepted moves was reached while live, with no winner or official draw. `failed`
means execution failure, also without a rules winner. Match-level crash aggregation
is deferred, with failure details preserved for it. CLI prints a JSON summary and
`--output` saves a complete trace. A reported game failure is a successful CLI
execution (exit 0); invalid configuration/replay errors exit 2. Inspect `status`.

## Trace contract

New records use **`omok-game-v2`**, one complete UTF-8 JSON object written with the
standard library. The replay reader also accepts existing `omok-game-v1` records.
The root fields are `format`, `initial`, `players`, `budgets_ms`, `move_cap`, `config`,
`moves`, `events`, `failure`, `status`, `reason`, `final`, `remaining_ms`, and `winner`.
`initial` and `final` contain `board`, `side_to_move`, `outcome`, and rules `reason`.
Players are in black/white order, each with `color`, class-name `identifier`, and
`source`: module, qualified class name, and SHA-256 of its defining file, or null
hash when source is unavailable. Hashes identify that file, not all dependencies;
replay validates their shape without importing players or reading their source.
CLI configuration includes seed, baseline/opponent versions, start, runtime,
hardware, and worker count. API callers supply applicable seed/version settings in
`config`; it is copied through JSON before execution and must be a finite JSON
object. No seed or version is invented for an unknown player.

`events` is ordered execution evidence:

- `returned`: color, diagnostic `returned` representation, normalized integer-pair
  `move` when representable (null otherwise), `elapsed_ms`, and own `remaining_ms`.
  This event follows each attempted call, including calls that raise exceptions.
- `applied`: color, accepted `move`, explicit `captured` cells with `prior_value`,
  elapsed/remaining time, and resulting complete `state`. Only this event changes
  the board. `moves` retains the accepted-move summary for existing consumers;
  replay checks it against the events, never silently choosing one over the other.
- `failure`: player/color, primary reason, ordered violations, `called`, diagnostic
  returned value, exception type/message, elapsed and remaining time. A timeout
  before a call has only this event; a failure after a call follows `returned` and
  has no `applied` event. The root `failure` mirrors its diagnostic fields.

Captures are sets: order is immaterial; duplicates, wrong coordinates or prior
values are errors. Time is milliseconds, null for unlimited remaining clocks.
Rule winners are color 0/1; draws, caps, and failures have null winner. Terminal
moves retain the mover as side to move, matching the simulator's convention.
`completed` must match an actual rules outcome; `capped`/`move_cap` and execution
failures leave the rules outcome `ongoing`. A complete final object is required
even for caps and failures; an interrupted partial write is rejected.

`offline.replay.replay` never invokes players. It reapplies moves through the verified
simulator and compares captures, alternation, initial/final rules state, terminal
status, cap, cumulative accounting, and v2 intermediate states and event order.
`load_trace(Path(...))` reads JSON and rejects duplicate keys, nonfinite numbers,
and non-object roots. Truncated/invalid JSON is rejected by the CLI; malformed and
inconsistent traces raise `ValueError`. Durations are validated
for accounting, not reproduced. Failure claims are retained execution evidence:
replay cannot prove that a player really raised an exception or mutated its snapshot.
This is a consistency format, not a cryptographically authenticated log.

Keep generated traces under `.scratch/` or another experiment-output directory,
outside `omok/` and the eventual submitted agent. Existing supplied-player files,
AI attribution, and earlier interaction records are preserved. Issue #6 source and
documentation additions are AI-written by OpenAI Codex; no new LLM usage records
were created at the user's request.

## Limits and verification

Timing is **post-return** for trusted local players: a never-returning call cannot
be stopped by this runner. Hard process isolation is deferred. The smoke command
runs each CLI subprocess under a 30-second external deadline, serially, so the
verification itself is bounded. Unlimited mode should always be combined with a
move cap and external wall deadline when running experiments. This is a minimal
runner, without league scheduling, match scoring, resumable batches, or search.

The smoke command saves replayable traces under `.scratch/issue-4-smoke/` and a
summary in `docs/verification/issue-4-smoke.json`. It distinguishes eight regular
60,000 ms empty-board games (four in each color) from deliberate cap, zero-clock,
and unlimited probes. Seeds are 20261008–20261011 in both colors. Local timing may
change selected moves when the baseline's optional scan reaches its wall deadline;
a seed alone does not guarantee identical games across hardware.

`python3 -m verification.provided` runs four games per baseline color against
each supplied bot, serially, with 60,000 ms total per player, a 1,000-move cap,
and a 180-second external deadline per process. Each returned trace is replayed.
It saves traces under `.scratch/issue-7-integration/` and a report under
`docs/verification/issue-7-integration.json`. Failed process exits and external
timeouts are reported separately from runner failures; a terminated process does
not identify the offending player or provide a complete replay. The report is
updated after each game. `--budget-ms 1000 --move-cap 2 --output .scratch/screen.json
--traces .scratch/screen` is labeled cheaper screening; it is not official-budget
evidence. Source hashes include the base and both unchanged bots in trace config,
plus the underlying baseline implementation and the adapter's defining source.
This is integration evidence, without tournament scoring or strength claims.

Issue #5 updates to the player, tests, smoke reporting option, and documentation
were AI-written by OpenAI Codex. `--issue 5` saves separate smoke summaries in
`docs/verification/issue-5-smoke.json` and traces in `.scratch/issue-5-smoke/`.
See [issue #5 acceptance evidence](verification/issue-5.md) for the decisions and
checks. Interaction transcripts were not recorded for this issue at user request.

## Issue #14: selecting search and recording diagnostics

The existing command defaults to the retained `LegalBaseline`. Select the integrated
`IterativePlayer` with `--engine search`; choose its explicit color with
`--agent-color black|white`. The older `--baseline-color` spelling remains an alias.
`--opponent baseline|smoke|random|simple` includes the retained local baseline and
unchanged supplied bots. Supplied games construct `ProvidedSearch`, which inherits
the recovered supplied `Player` base and initializes its verified color constructor.
This offline adapter imports no opponents into `omok/`.

```sh
python3 -m offline --engine search --agent-color white --opponent simple --diagnostics --move-cap 12 --output .scratch/search.json
python3 -m offline --replay .scratch/search.json
python3 -m verification.integration
```

`run_game(..., diagnostics=callback)` is the explicit opt-in route. The callback
receives the player after the public turn has returned and been timed. It may return
`None` or a finite JSON object of at most 16384 characters. A detached copy is saved
as `search` on that turn's existing `returned` event. Callback/serialization failures
record only `diagnostics_error` (exception type) and do not change execution failure
classification, authoritative moves, clock debits or event ordering. Diagnostic work
is offline observation outside the player's timed call. The CLI's callback records
only iterative players. With diagnostics disabled, no snapshot callback runs.

The trace format stays `omok-game-v2`, and existing v1/v2 replay readers continue to
use moves, captures, states and clocks. Diagnostics are advisory: replay does not
trust or validate their search claims. `verification.integration` independently
replays actual transitions and every selected complete PV through reference rules.
Engine code never writes per-turn files or prints diagnostics; the CLI writes the
completed trace once when `--output` is provided.

Official board types/runtime, final team class/file names, and official unlimited
clock translation remain external gates. Offline `None` clocks pass `-1`, which
still has a finite local search allocation. Cooperative cancellation and post-return
timeout reporting remain unchanged; no hard isolation or leagues are introduced.

## Supervised games (issue #25)

AI-written by OpenAI Codex. The CLI now uses
`offline.supervised.run_supervised_game(black_spec, white_spec, ...)` by default.
`PlayerSpec(module, factory, options={}, seed=0)` names an importable factory called
as `factory(color, **options)` inside a fresh Python subprocess. The factory must
assign explicit `color`. Options must be JSON serializable. Each game starts new
instances; each instance persists across all of its turns. The legacy
`offline.runner.run_game` remains available for trusted deterministic checks and
older measurements; it still cannot interrupt a nonreturning call.

The supervisor starts one player process at a time, using the current Python
executable and a repository-relative working directory. Authenticated loopback TCP
carries length-prefixed JSON (65,536-byte maximum frames); no remote service is
required. Separate stdout/stderr pipes are continuously drained, including native
file-descriptor writes. Each stream retains a bounded prefix (16,384 bytes by
default), with bytes-seen and truncation flags. No arbitrary returned object is
pickled or represented by calling its `repr`; only a validated coordinate pair is
transported, and malformed moves are rejected without substitution.

Default setup is bounded at 5,000 ms **per player**, separately recorded and never
debited from thinking time. Imports, construction, explicit color validation and
source inspection must finish inside that bound. Player dependency/import errors
are `setup_failed/player_setup`; startup expiry is `startup_timeout`. Failure to
launch a process/socket is a `supervisor_error`, not a player forfeit.

Finite clocks retain floating-point milliseconds. Each turn sends
`floor(remaining_ms)`; a positive fraction under 1 ms sends zero, while an exhausted
unrounded clock stops before `take_turn`. The authoritative timer starts immediately
before request encoding/dispatch and ends after the complete response is received
and its protocol fields checked. Dispatch, IPC, response serialization, optional
worker diagnostics and caller scheduling delays within this envelope are charged
to **only the active player**. Board snapshot preparation, ordinary idle time,
startup, rule application and cleanup are excluded. This conservative policy does
not claim to reproduce the grader's unknown timing implementation. The worker also
reports its call/return-coordinate-validation elapsed time; the difference from the
envelope is reported as overhead, with unavailable measurements kept null.

There is no smaller finite per-turn kill limit: the watchdog uses the precise
remaining cumulative clock. Replies received after that deadline are rejected.
An exactly-budget reply is eligible, but the next turn cannot run with zero time.
The public `clock` injection is for deterministic accounting verification only;
when injected, a separate real watchdog is at least `unlimited_call_ms` so synthetic
submillisecond clocks do not depend on OS scheduling. Production uses monotonic
accounting and the exact finite budget for both watchdog and accounting.

Python `None` / CLI `-1` denotes unlimited development time and is passed as `-1`.
Negative budgets other than that CLI sentinel, nonfinite values and booleans are
rejected. Unlimited calls still have a 1,000 ms watchdog by default; expiry records
`capped/unlimited_call_cap`, never a rules draw. The move cap also remains a cap.
Configure resource policies with `--startup-ms`, `--cleanup-ms`,
`--unlimited-call-ms` and `--output-bytes`.

At end/failure, close each connection, terminate the worker, and wait up to
`cleanup_ms` (default 500 ms). If needed, kill and wait another `cleanup_ms`.
Output-drain thread joins share one additional `cleanup_ms` window per worker.
Process IDs, reaping status, exit codes, setup/cleanup timing and bounded output
are retained. Normal worker termination by the supervisor is not a player crash.
Failure to reap is a supervisor cleanup error. These processes provide lifecycle
isolation, not a security sandbox or a guarantee about player-created descendants.

Traces use `omok-game-v4`; replay retains support for v1–v3. See
[versioned evidence and loss inspection](replay.md). Board winner/draw and
execution status remain separate. Reasons distinguish exact-five, simultaneous
wins, full board, exception, player exit, protocol failure, invalid move, observable
snapshot mutation, timeout, resource caps, setup failure and supervisor errors.
The board remains the last valid simulator state. A failure identifies the offending
side where known; `winner` is only a rules winner. This API does not assign forfeit
scores, coins or match-level crash overrides; those belong to the aggregation ticket.
Snapshot mutation is reported by the worker even though process isolation already
protects the authoritative board. Unobservable mutate-and-restore behavior is not
claimed to be detected. Transport timeout takes precedence over an unusable late
reply; otherwise exception, observable mutation and illegal move are checked in
that order. Optional diagnostics are bounded to a 16,384-character JSON object.

```sh
python3 -m unittest tests.test_supervised -q
python3 -m offline --engine search --opponent random --fixture mover-win --diagnostics --output .scratch/supervised.json
python3 -m offline --replay .scratch/supervised.json
python3 -m offline --black-ms -1 --white-ms -1 --unlimited-call-ms 1000 --move-cap 20
```
