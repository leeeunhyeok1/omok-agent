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
slots serially. Output must be a new directory; existing evidence is never replaced.

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
`omok-game-v3` trace when available, and exposure purpose/pool/version identities.
Exposure counts dispatched turn attempts by color and applied moves; a timed-out
call is still an attempted exposure. Preflight, zero-move caps and terminal fixtures
are labeled `no-player-turns`. Fixture turn attempts are separately labeled.

Caps, setup and infrastructure errors are not assigned player losses or rules
draws. Player errors retain the offending color and raw reason. The saved failure
policy deliberately performs no match scoring: eight-game aggregation/crash
match overrides, checkpoints/resume and ratings are separate phase tickets.

The output directory contains the manifest, one file per completed slot, and a
final results file. These exclusive writes preserve evidence but are not an atomic
checkpoint/resume protocol. On interruption, the manifest still lists every slot;
only written per-game records establish completed execution.
