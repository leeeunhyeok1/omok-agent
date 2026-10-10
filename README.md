# omok-agent

Issue #38 adds predeclared balanced training screening, retained failure gates,
explicit incomplete fitness, and incumbent retention. See [screening](docs/screening.md).

```sh
python -m verification.screening --output .scratch/screening-pilot
```

Issue #37 adds saved, seeded parameter policies, deduplicated immutable candidates,
and execution through the existing registry. See [candidate proposals](docs/proposals.md).

Issue #36 adds a restorable frozen incumbent and bounded one-worker optimizer
baseline collector. See [baseline commands and limits](docs/optimizer-baseline.md).

```sh
python -m verification.optimizer_baseline collect --output .scratch/baseline-run
python -m verification.optimizer_baseline verify --output .scratch/baseline-run
```

Issue #33 adds saved matchup reports with explicit rate denominators, retained attempt
history, clean-game views, family/duplicate coverage and separate runtime segments.
See [report commands and limitations](docs/reports.md).

Issue #32 adds bounded concurrent resumable batches with one result owner, isolated
players and execution-segment metadata. See [controlled concurrency](docs/experiments.md#controlled-concurrency-issue-32).

Issue #31 adds supervised trace validation, bounded preceding-position loss
exports and independently checked rule fixtures. See [replay and inspection](docs/replay.md).

Issue #30 adds contrasting frozen synthetic opponents, documented families and
protected actual holdout metadata. See [strategies, pools and bounded verification](docs/synthetic.md).

Omok++ simulator, verified one-ply baseline, bounded local runner, and versioned
record/replay and supplied-player integration implemented for GitHub issues #3–#8. Python **3.14.3** is the
verified local runtime; the grader runtime is not yet known. Engine and rule
verification use only Python's standard library.

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q omok verification tests
python3 -m verification.differential
python3 -m verification.benchmark
python3 -m offline --seed 20261008 --output .scratch/game.json
python3 -m offline --replay .scratch/game.json
python3 -m verification.smoke --issue 5
python3 -m verification.smoke --issue 6
python3 -m offline --opponent simple --baseline-color white --output .scratch/provided.json
python3 -m verification.provided
python3 -m verification.smoke --issue 8
```

The differential command defaults to 16 ordinary and 16 capture-biased sequences,
seeds 20261008–20261023 and 20361008–20361023, at most 240 moves each. It stops on
rule outcomes. Its verification cap does not introduce a game draw rule. A mismatch
saves its seed and replayable moves under `.scratch/differential/`.

See [the simulator contract](docs/simulator.md) and
[the acceptance report](docs/verification/issue-3.md).

`omok/` is the engine and development player; `offline/` contains the runner and local smoke opponent. `verification/` contains the independent offline reference
and checks; `tests/` contains deterministic public-boundary fixtures.
`players/` holds the unchanged professor-provided bots and recovered release base.
Thin offline adapters verify inheritance without adding opponent imports to the
agent. See [issue #7 compatibility evidence](docs/verification/issue-7.md).
The local player and runner contracts and commands are documented in
[docs/runner.md](docs/runner.md). Issue #10 adds a bounded fixed-depth search player
and deterministic unpruned reference; [docs/search.md](docs/search.md) describes
the APIs, score bounds and cancellation behavior. `LegalBaseline` remains available.
Issue #11 adds committed iterative deepening and remaining-total-clock allocation
through `IterativePlayer`. Issue #12 adds verified immediate tactics and configurable
local candidates to its default engine. Issue #13 adds a bounded transposition
table with strict depth/policy compatibility; final packaging remains deferred.

```sh
python3 -m unittest tests.test_search -v
python3 -m verification.search
python3 -m unittest tests.test_iterative -v
python3 -m verification.iterative
python3 -m unittest tests.test_tactics -v
python3 -m verification.tactics
python3 -m unittest tests.test_transposition -v
python3 -I -S verification/offline_engine.py --search
```

Phase 01 core acceptance passed. Fresh commands, measured timing, network-denied
execution, and remaining external checks are in the
[issue #8 acceptance report](docs/verification/issue-8.md). The
[Phase 02 handoff](docs/phase-01-handoff.md) records the verified APIs and checkpoint
restore instructions. Issue #8 changes are AI-written by OpenAI Codex; no new LLM
usage records were created at user request.

Earlier AI attribution and interaction records are in [llm-usage](llm-usage/README.md).
Issue #5 decisions, AI attribution, and acceptance evidence are in
[its report](docs/verification/issue-5.md); no new interaction transcript was recorded
at user request.
Issue #6 record/replay decisions and validation are in
[its report](docs/verification/issue-6.md). No LLM usage records were created.

Issue #14 exposes the integrated search player in the existing offline CLI and
supplied inheritance adapter, with optional bounded replay-compatible diagnostics.
See [the runner contract](docs/runner.md) and [acceptance evidence](docs/verification/issue-14.md).

```sh
python3 -m offline --engine search --agent-color black --opponent baseline --diagnostics --move-cap 12 --output .scratch/search.json
python3 -m verification.integration
python3 -m unittest tests.test_integration -v
```

Phase 2 correctness and local game checks are recorded in
[issue #15 acceptance](docs/verification/issue-15.md), with preserved replay traces
and [Phase 3 handoff/checkpoint instructions](docs/phase-02-handoff.md).
Submillisecond timing acceptance remains partial; SimplePlayer beat the temporary
material evaluator in all reported games. Reproduce bounded measurements/games:

```sh
python3 -m verification.acceptance measure
python3 -m verification.acceptance screening
python3 -m verification.acceptance official
python3 -m verification.acceptance replay
python3 -I -S verification/offline_engine.py --iterative
```

Issue #16 adds an isolated, validated saved material evaluator and development
inspection route. See [configuration/loading/inspection](docs/evaluation.md) and
[acceptance evidence](docs/verification/issue-16.md). The Phase 2 default and
checkpoint remain available; richer feature families are separate follow-up work.

Issue #18 adds selectable, inspectable open/broken threes and two-stone line
potential. Definitions and provisional weights are in [docs/evaluation.md](docs/evaluation.md);
[acceptance evidence](docs/verification/issue-18.md) includes the reproducible suite.

```sh
python3 -m verification.potential --config configs/potential-v1.json
python3 -m unittest tests.test_potential -q
```

Issue #19 adds the experimental `capture-v1` evaluator for legal capture moves,
multiple pairs and actual vulnerable pairs, with independently configurable
opportunity/risk weights and rule-correct prospective outcomes. See
[definitions](docs/evaluation.md) and [verification](docs/verification/issue-19.md).

```sh
python3 -m verification.captures --repetitions 5
python3 -m unittest tests.test_captures -q
```

Issue #20 adds experimental capture-effect and endpoint-multiplicity inspection,
shared capture defenders, and context-consistent opportunity/urgency weights.
The Phase 2 default remains active because profiling shows a substantial runtime
cost. See [definitions](docs/evaluation.md) and [acceptance evidence](docs/verification/issue-20.md).

```sh
python3 -m verification.threat_effects --repetitions 5
python3 -m verification.threat_effects --games
python3 -m unittest tests.test_threat_effects -q
```

Issue #21 adds evaluator-call/cache/cancellation counters, optional sampled
production feature costs, saved-config runner flags, and bounded frozen-candidate
comparisons. See [measurement commands and definitions](docs/measurement.md) and
[recorded acceptance evidence](docs/verification/issue-21.md).

```sh
python3 -m verification.measurement --output .scratch/measurement.json
python3 -m unittest tests.test_measurement -q
```

Issue #22 retains Phase 2 material as the default after full-evaluator comparisons,
76 replayed games, and family ablations. See [the evidence](docs/verification/issue-22.md)
and [Phase 3 handoff](docs/phase-03-handoff.md). Reproduce bounded evidence with:

```sh
python3 -m verification.evaluation_acceptance gate
python3 -m verification.evaluation_acceptance development
python3 -m verification.evaluation_acceptance integration
python3 -m verification.evaluation_acceptance ablations
python3 -m verification.evaluation_acceptance summary
```

Issue #23 completes the [Phase 3 acceptance map and handoff](docs/phase-03-handoff.md)
and verifies restoration of both immutable engine checkpoints. Engineering checks
pass, but SimplePlayer qualification remains unmet (0/8 for both evaluators) and
tiny-clock timing acceptance remains partial.

```sh
python3 -m verification.checkpoint --output .scratch/restoration.json
```

Issue #26 adds immutable registered-player selection, bounded adapter preflight,
actual retained engine loading, protected pool snapshots and explicit exposure
records. See [the registry contract and commands](docs/registry.md).

```sh
python3 -m offline.registry_cli freeze --output .scratch/registry-v1.json
python3 -m offline.registry_cli play --registry .scratch/registry-v1.json --candidate phase3-material --opponent random --move-cap 20 --output .scratch/registered-game.json
python3 -m unittest tests.test_registry -q
```

Issue #27 adds saved color-balanced experiment plans and serial execution with
stable game identities, paired seeds/openings, explicit modes and exposure records.
See [the experiment API and commands](docs/experiments.md).

```sh
python3 -m offline.experiment_cli plan --registry .scratch/registry-v1.json --candidate phase2 --opponent random --mode official --output .scratch/official-plan.json
python3 -m offline.experiment_cli run --plan .scratch/official-plan.json --output .scratch/official-run
python3 -m unittest tests.test_experiments -q
```

Issue #28 adds separate qualification, tournament and coin decisions while
preserving raw game outcomes and execution failures. Missing slots, caps,
infrastructure errors and both-player crashes remain unresolved. See
[the scoring policy and commands](docs/matches.md) and
[acceptance evidence](docs/verification/issue-28.md).

```sh
python3 -m offline.experiment_cli score --plan .scratch/official-run/manifest.json --results .scratch/official-run/results.json --output .scratch/match-scores.json
python3 -m unittest tests.test_matches -q
```

Phase 4's [acceptance evidence](docs/verification/issue-34.md) and
[Phase 5 handoff](docs/phase-04-handoff.md) preserve controlled verification,
the actual frozen candidate smoke league, protected pool snapshots, local
throughput measurements, restoration and execution/reporting contracts.
Rerun the bounded collector with a fresh output directory:

```sh
python3 -m verification.league_acceptance gates --output .scratch/new-phase04-gates
python3 -m verification.league_acceptance smoke --output .scratch/new-phase04-smoke
```

Phase 5 supports [bounded optimizer stop/resume](docs/optimizer.md) over immutable
proposals and training cohorts. Resume preserves committed attempts, proposal RNG
state, ancestry, decisions, and execution provenance. See the command examples
and abrupt-owner-death limits in that contract.
