# omok-agent

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
