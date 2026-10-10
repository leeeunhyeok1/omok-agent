# Reproducible serial experiments

Issue #27 adds `offline.experiments.ExperimentPlan` and
`python3 -m offline.experiment_cli`. The submitted engine, evaluator and time
allocation remain unchanged. Registry entries supply the frozen configuration;
the experiment never edits player settings.

```sh
python3 -m offline.registry_cli freeze --output .scratch/league.json
python3 -m offline.experiment_cli plan --registry .scratch/league.json --candidate phase2 --opponent random --mode official --output .scratch/official-plan.json
python3 -m offline.experiment_cli run --plan .scratch/official-plan.json --output .scratch/official-run
python3 -m offline.experiment_cli plan --registry .scratch/league.json --candidate phase2 --opponent smoke --mode screening --total-ms 100 --games 2 --move-cap 4 --output .scratch/screen-plan.json
python3 -m offline.experiment_cli run --plan .scratch/screen-plan.json --output .scratch/screen-run
```

Freeze a registry after changing framework code: the existing registry loader
verifies adapter/source digests and the registered Python runtime. A saved plan
requires those sources and checkpoint Git objects to remain available. This is
source verification, not an embedded copy of every dependency.

## Public API and formats

`ExperimentPlan.resolve(candidate, snapshot, ...)` resolves all defaults before
dispatch. `save(path)` writes a new JSON file; `load(path)` verifies its digest,
registry/pool identities and the entire reconstructed schedule. `record()` returns
an owned JSON object. `run_experiment(plan, output=directory)` executes the saved
slots serially. The first run requires a new directory; `resume=True` continues it
using its authoritative checkpoint and preserves prior attempt evidence.

`omok-experiment-v1` saves candidate/configuration, full pool snapshot, selected
opponents, mode/purpose, cumulative clock and failure policies, opening and seed
policies, game counts, move cap, supervision limits, diagnostics, resource/start
settings, runtime, CPU, RAM where observable, and contention conditions. References
use project-relative paths or full checkpoint commits. External bundles must be
placed inside the project before resolving a portable plan. Converting an absolute
in-project registry root to a relative root creates a new registered identity,
retaining source/configuration digests. Move the complete project, including those
bundles and Git history, to recreate it.

Match/game IDs derive from resolved definitions. Different configurations, seeds,
openings, selected pools or policies change IDs. Hardware observations do not
change job IDs; manifest identity includes them, and execution records fresh
conditions. Execution order cannot assign or alter colors/seeds. Runtime versions
remain subject to registry compatibility checks.

Each adjacent pair exchanges candidate colors, retaining its starting position
and candidate/opponent role seeds. Opening sequences cycle by pair. The two role
seeds differ even for self-play; each player has its own process/global RNG.
Constructor and process-global seeding use the registry contract. Unsupported
seeding is disclosed per job. Two entries declaring deterministic behavior get a
`duplicate_evidence_group` for repeated same-color/same-opening jobs: seed changes
alone do not establish independent evidence. Clock-sensitive deterministic engines
may still vary with machine timing. Pairing does not guarantee matching random
choices after different moves or random-number consumption.

## Modes and budgets

- `official`: exactly eight games per opponent, alternating colors (four each),
  empty board and 60,000 ms total for each player. Incompatible overrides fail.
- `development`: explicit saved total wall clocks, game counts and legal opening
  sequences. `--total-ms -1` passes the inspected unlimited sentinel, while finite
  move and `--unlimited-call-ms` watchdog caps bound execution externally.
- `screening`: reduced finite total wall-clock budget, explicitly below 60,000 ms.
  Existing node/depth limits in the registered configuration remain intact; this
  route does not manufacture a fixed-work interface for unsupported opponents.
- `fixture`: `--fixture` supplies a JSON object containing `board` and explicit
  `side_to_move`. Artificial fixtures are labeled and excluded from ordinary
  strength interpretations. Terminal fixtures require no turns.

`--openings` accepts a JSON list of move sequences, for example
`[[[9,9]], [[9,9],[8,8]]]`. Each sequence is replayed from the empty board through
the simulator; illegal moves, continuation after terminal states and terminal
opening positions fail. The manifest records both construction and actual starting
board/side. The same colored starting board is retained when exchanging player
colors; stones are not recolored. Artificial boards are exclusive to fixture mode.

The existing supervisor charges dispatch-through-response time cumulatively to
only the active player, floors the public remaining-ms argument, and records
call time/overhead separately. Startup and cleanup use separate finite limits.
An official-mode move cap can still stop a game; that result is capped, not an
official draw or completed official match.

## Results and scope

Every requested slot receives a result, including setup failures and player
failures. Both color constructors are bounded-preflighted before each game.
A changed or missing source produces setup failure rather than omission.
Fresh supervised players persist across turns and are cleaned up after each game.
Execution then proceeds to the next slot, without retrying away failure evidence.

`omok-experiment-results-v1` records planned/completed/failed/capped/pending and
infrastructure-failed counts. Each slot retains IDs, preflight facts, raw replayable
`omok-game-v4` trace when available, and exposure purpose/pool/version identities.
Saved v1–v3 traces remain replayable; see [replay and loss inspection](replay.md).
Exposure counts dispatched turn attempts by color and applied moves; a timed-out
call is still an attempted exposure. Preflight, zero-move caps and terminal fixtures
are labeled `no-player-turns`. Fixture turn attempts are separately labeled.

Caps, setup and infrastructure errors are not assigned player losses or rules
draws. Player errors retain the offending color and raw reason. The saved failure
policy deliberately performs no scoring on the raw facts. Issue #28 adds a
separate, versioned scoring report. See [eight-game scoring](matches.md) for the
interpretation and limits.

The output directory contains the immutable manifest, an authoritative checkpoint,
one export per committed slot, and `results.json` and `match-scores.json` summaries.
The returned results contain `match_scores`, all attempts and execution segments.

## Stop, checkpoint and resume (issue #29)

```sh
python3 -m offline.experiment_cli run --plan .scratch/screen-plan.json --output .scratch/bounded-run --max-jobs 1 --max-seconds 30
python3 -m offline.experiment_cli run --plan .scratch/screen-plan.json --output .scratch/bounded-run --resume --max-seconds 30
```

`run_experiment` accepts `resume`, `max_jobs`, `max_seconds`, `stop_requested`
(a predicate), `progress` (a counts callback), and `infrastructure_retries`.
Job bounds count dispatched attempts per invocation, including retries. Time bounds
use a monotonic wall clock and include preflight/game work; bounded worker cleanup
and checkpoint/report writes may extend the segment beyond that bound. The CLI
prints progress after each commit and at shutdown. Ctrl+C, SIGTERM where supported,
or an existing `--stop-file` stops dispatch and interrupts active setup/turns.
Polling is at most 50 ms during worker waits; cleanup follows the saved supervision
limits. Caps remain experiment results; batch interruption leaves the job pending.

`omok-batch-checkpoint-v1` stores the manifest identity, saved retry policy, attempts,
latest committed results, and segments. Attempts are durably recorded as running
before dispatch. Cleanup precedes result commit. A complete checksummed JSON document
is flushed with `fsync` then atomically replaced from the same directory. POSIX also
flushes the directory; Windows uses flushed files and atomic replacement, subject to
the filesystem's power-loss guarantees. Temporary files from partial writes are not
results. OS file locks enforce one authoritative owner and release on process exit.
Identical duplicate commits are no-ops; conflicting duplicates and late commits for
interrupted attempts are rejected. Each job counts once.

Resume verifies the manifest, checkpoint checksum, assignments, replayable committed
traces, runtime and source/configuration snapshots before dispatch. Truncated or
conflicting committed exports are rejected. Missing or valid stale exports can be
rebuilt from the authoritative checkpoint after a crash between commit and export.
Old runs without a checkpoint are not silently imported. Committed successful,
failed and capped jobs stay committed; uncommitted running attempts become explicitly
interrupted before restarting the same job/seeds/colors with a new attempt ID.
Graceful interruptions retain available partial trace/preflight and cleanup evidence.
A hard process exit may leave only the durable dispatch record. No mid-game object
serialization is used; abrupt supervisor termination cannot guarantee worker cleanup.

`--infrastructure-retries N` saves a bounded setup/supervisor retry allowance in the
checkpoint, separate from the raw manifest's no-scoring policy. It defaults to zero;
resume inherits it and rejects changes. Every prior result remains in its attempt.
Genuine player crashes/timeouts and cleanup errors retaining a player failure are
never retried automatically. Attempt history is additive evidence; ordinary scoring
uses the latest committed record for each slot. Resource limits may leave authorized
infrastructure retries for the next resume.

Outputs can move independently; their manifests contain project-relative source
roots and immutable Git references, resolved in the current project. Move required
source bundles and Git objects with the project when migrating machines. Each resume
adds a labeled segment with fresh hardware/runtime/contention observations; traces
and results identify their attempt and segment. Timing from different segments must
not be presented as measurements under identical hardware conditions. Ratings remain
outside this ticket.

## Controlled concurrency (issue #32)

```sh
python3 -m offline.experiment_cli run --plan .scratch/screen-plan.json --output .scratch/parallel-run --workers 2 --max-seconds 30 --contention "development screening; other CPU load uncontrolled"
python3 -m offline.experiment_cli run --plan .scratch/screen-plan.json --output .scratch/parallel-run --resume --workers 1 --contention "dedicated timing run; other experiments stopped"
```

`run_experiment` accepts `workers` (1..64, default 1) and a nonempty `contention`
description. Each slot runs in a supervisor thread with fresh, isolated Python
player subprocesses; each player's instance persists across that game's turns.
There are at most `workers` active games and at most `2 * workers` live player
processes during normal supervision. No executor backlog is submitted. The main
owner alone creates attempts, validates/commits results, writes checkpoints and
calls progress callbacks. A game cannot have overlapping attempts. Completion
order does not alter saved job IDs, seeds, colors, openings or configurations.
Returned results stay in planned order; segments also record completion order.
The job bound limits dispatched attempts; already dispatched games finish before
stopping at that bound. Time bounds and stop requests interrupt every active game.

Changing workers on resume changes execution conditions rather than the saved plan.
The manifest's original resource settings are defaults; each durable segment records
the actual worker count, process-start policy, CPU/count/affinity, RAM, Python/platform,
load average when available and declared contention. `changed_conditions` explicitly
lists changes from the preceding segment. Segment `wall_seconds` includes cleanup;
`owner_cpu_seconds` measures CPU consumed by the owner process (including supervisor
threads), excluding player subprocess CPU. Windows RAM uses the native memory API;
POSIX uses physical page counts. Reports retain all segments and each result's segment.
Hardware and worker changes must remain separate timing evidence.

Each result's `scheduling.queue_ms` measures waiting from segment start to execution
start, including waiting for an available game slot. `execution_ms` covers setup,
play and cleanup. Per-player startup/cleanup observations remain in preflight and
trace worker records. None of these scheduler times are charged to player clocks.
Only that player's dispatch-through-response calls consume its cumulative clock.

Cancellation sets a shared stop event, stops dispatch, joins supervisors and uses
the existing finite player cleanup policy concurrently across games. Interrupted
attempts retain partial trace/preflight and cleanup evidence. Completed responses
awaiting commit at cancellation are stored as discarded evidence, never counted.
Checkpoint commits reject results from interrupted, superseded or foreign-owner
attempts; identical current committed duplicates remain no-ops. Owner/reporting
exceptions also cancel other games and preserve the checkpoint before propagating.
Unexpected supervisor faults are infrastructure results with explicit error and
available cleanup evidence, without player losses; retry limits still apply.
An abrupt OS-level owner kill remains outside graceful cleanup guarantees.

Use a dedicated machine with other experiments stopped, stable power/CPU settings,
and **one game worker** for final wall-clock comparisons. Record those controls with
`--contention`; the default honestly says uncontrolled. Parallel segments are labeled
unsuitable for final timing comparisons even when they use official 60-second budgets.
No automatic promotion or claim of controlled external load is made. Choose development
worker counts conservatively from measured throughput/RAM and observe timing spikes.
Reduced-clock screening remains wall-clock screening. Saved candidate node/depth caps
describe separate screening conditions; they do not remove the opponent's clock or
make a mixed clock/work-limit experiment equivalent to an official timing check.
