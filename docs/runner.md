# Local baseline and game runner

AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4. Verified on Python 3.14.3;
the grader version and final submission inheritance remain unresolved.

```sh
python3 -m offline --seed 20261008 --output .scratch/game.json
python3 -m offline --baseline-color white --black-ms 60000 --white-ms 60000
python3 -m offline --fixture dense --output .scratch/dense.json
python3 -m offline --start opening.json --move-cap 200
python3 -m offline --black-ms -1 --white-ms -1 --move-cap 100
python3 -m offline --replay .scratch/game.json
python3 -m verification.smoke
python3 -m verification.smoke --issue 5
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
players with their assigned colors. Supplied `players/randomplayer.py` and
`players/simpleplayer.py` show `Player(color)`, `self.color`, list-style board access,
and `take_turn(board, time)`. Both import the absent `player` module. They are
unchanged; no guessed base class or official-compatible adapter is supplied.
Their unlimited-time interpretation and full inheritance integration remain pending.

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

`omok-game-v1` JSON contains initial/final board, explicit side and rules result,
player identifiers/colors, budgets, cap, configuration/seed/version/runtime metadata,
accepted moves with mover, captures and prior values, call durations and remaining
clocks, final status/reason/winner, and a separate failure event. Failed returned
values are recorded as their representation for diagnostics and never replayed.
Rule winners are color 0/1; draws, caps, and failures have null winner. Each accepted
move records its normalized returned coordinate. Configuration in the Python API
must be JSON serializable if the caller intends to write JSON.

`offline.replay.replay` never invokes players. It reapplies moves through the verified
simulator and compares captures, alternation, initial/final rules state, terminal
status, cap, and cumulative accounting. Truncated/invalid JSON is rejected by the
CLI; malformed and inconsistent traces raise `ValueError`. Durations are validated
for accounting, not reproduced. Failure claims are retained execution evidence:
replay cannot prove that a player really raised an exception or mutated its snapshot.
This is a consistency format, not a cryptographically authenticated log.

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

Issue #5 updates to the player, tests, smoke reporting option, and documentation
were AI-written by OpenAI Codex. `--issue 5` saves separate smoke summaries in
`docs/verification/issue-5-smoke.json` and traces in `.scratch/issue-5-smoke/`.
See [issue #5 acceptance evidence](verification/issue-5.md) for the decisions and
checks. Interaction transcripts were not recorded for this issue at user request.
