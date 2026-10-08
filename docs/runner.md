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
