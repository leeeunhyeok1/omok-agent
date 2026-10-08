# omok-agent

Omok++ simulator, legal baseline, and bounded local runner implemented for GitHub issues #3 and #4. Python **3.14.3** is the
verified local runtime; the grader runtime is not yet known. Engine and rule
verification use only Python's standard library.

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q omok verification tests
python3 -m verification.differential
python3 -m verification.benchmark
python3 -m offline --seed 20261008 --output .scratch/game.json
python3 -m offline --replay .scratch/game.json
python3 -m verification.smoke
```

The differential command defaults to 16 ordinary and 16 capture-biased sequences,
seeds 20261008–20261023 and 20361008–20361023, at most 240 moves each. It stops on
rule outcomes. Its verification cap does not introduce a game draw rule. A mismatch
saves its seed and replayable moves under `.scratch/differential/`.

See [the simulator contract](docs/simulator.md) and
[the acceptance report](docs/verification/issue-3.md).

`omok/` is the engine and development player; `offline/` contains the runner and local smoke opponent. `verification/` contains the independent offline reference
and checks; `tests/` contains deterministic public-boundary fixtures.
`players/` holds the unchanged professor-provided bots. Their `player` base module
is absent, so official player integration remains pending. The local player and runner contracts and commands are documented in
[docs/runner.md](docs/runner.md). Search and final submission packaging are deferred.

AI attribution and interaction records are in [llm-usage](llm-usage/README.md).
