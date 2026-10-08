# Issue #7 acceptance evidence

Implemented “Verify professor-provided player integration”, bounded by issues #2
and #1. New code and documentation are AI-written by OpenAI Codex. Supplied code
is preserved unchanged; team naming and final submission packaging remain deferred.

## Source and compatibility

Recovered the missing base from the local supplied release directory
`omok_release (updated 9_17)/player.py` in Downloads and copied its exact bytes to
`players/player.py`. Both release bots compare byte-for-byte equal to the existing
repository files. The release README says the constructor was changed to explicit
`color` (black 0, white 1), with `ABC` and `abstractmethod`. Base SHA-256:
`f2be52255ac98ed0703bf284906c246540f34d1dec3ee387de354f78c78f0d7d`.
RandomPlayer SHA-256:
`4aeaabc5454929d9aaa4b31cbb47780ce59677e44a6dc9c5a5fc389a69c54c51`.
SimplePlayer SHA-256:
`34304e80ddba331c1a679599b81c29b15122e4777308e9960cfbe5b2644da69b`.
These identify the supplied local release, not a claim about an unseen grader.

The real base declares `__init__(color)`, stores only `self.color`, and declares
abstract `take_turn(board, time)`. Both bots call `super().__init__(color)` and use
nested `board[r][c]` indexing. Their only imports are `player` and, for RandomPlayer,
standard-library `random`; the base imports standard-library `abc`. No NumPy or
third-party dependency is needed. Fresh mutable list-of-list integer snapshots
work through their public boundary. Returned coordinates observed in source and
runs are tuples of built-in Python integers. The base imposes no board/coordinate
type checks: concrete grader array requirements and accepted integer types remain
unspecified. The local simulator accepts `__index__`, rejects bool/float, and does
not establish grader acceptance of those extra integer types.

Both supplied strategies ignore `time`. Neither source nor release README defines
the official unlimited CLI-to-player translation; development `-1` is not evidence
of that translation. Finite integration budgets avoid depending on it.

`offline.provided.load_players()` loads original classes using a temporary `player`
module alias, restoring any prior module. Named source modules remain inspectable.
Its factory creates fresh instances with explicit colors; no counts are used to
infer color. The baseline adapter inherits the real base and `LegalBaseline`, calls
both initializers, and delegates strategy through normal method inheritance.
It does not copy supplied strategy, repair invalid moves, or hide board mutation.
The runner owns snapshots and observes original returned values. All loader and
opponent imports stay outside `omok/`; core imports remain standard-library-only.
The loader is trusted, process-global import setup, not untrusted isolation.

## Commands and checks

```sh
python3 -m unittest tests.test_provided -v
.scratch/typecheck-env/bin/mypy omok offline verification tests/test_player.py tests/test_runner.py tests/test_replay.py tests/test_provided.py
python3 -m unittest discover -s tests -q
python3 -m compileall -q omok offline verification tests
python3 -m offline --opponent random --baseline-color white --output .scratch/provided.json
python3 -m offline --replay .scratch/provided.json
python3 -m verification.provided
python3 -m verification.provided --budget-ms 1000 --move-cap 2 --deadline-seconds 30 --output .scratch/issue-7-screening.json --traces .scratch/issue-7-screening
python3 -m verification.provided --deadline-seconds 0.001 --output .scratch/issue-7-deadline-probe.json --traces .scratch/issue-7-deadline-probe
git diff --check
```

Public-boundary tests verify actual inheritance for both colors, center openings,
input preservation, fresh RandomPlayer state, baseline strict winning fixtures,
and short supplied-bot runner traces that replay. Existing runner tests cover
unchanged failure propagation for mutation, invalid moves, exceptions, and clocks.
Core-only import is checked in a fresh interpreter without any `offline` or
supplied-player modules loaded.

Final validation passed: 64 tests in the full suite, 21 source files in the
documented mypy scope, bytecode compilation, and whitespace checks.

## Measured integration

[Raw integration report](issue-7-integration.json) contains four games as black and
four as white against each bot, seeds 20261008–20261011, empty starts, one serial
worker, 60,000 ms **total per player**, cap 1,000, and external deadline 180 seconds.
Every finished trace is replayed and records source hashes, moves, captures,
returned/applied events, clocks, and outcome. Traces are under
`.scratch/issue-7-integration/` outside the agent. Python 3.14.3, macOS 13.7.8,
x86_64. Baseline timing can vary moves across runs; seeds do not eliminate timing
variation. Deterministic repeated SimplePlayer games are duplicate evidence,
not independent strength samples. No strength or match-scoring claim is made.

Sixteen full-budget games completed in 9–43 moves and approximately 0.454–1.404
seconds per subprocess; zero capped or failed. Observed mutation,
illegal-move, crash, post-return timeout, and external timeout counts are all zero.
Separate cheaper 1,000 ms / two-move screening produced 16 capped games, zero
failed. Deliberate 0.001-second external deadline probes produced 16 external
timeouts and exercised process termination; these are expected harness probes,
not opponent reliability failures. No complete trace or offending-player claim
is available for a process killed mid-game. Execution is still timed post-return
inside the runner; hard per-turn isolation is deferred.

The local supplied inheritance and constructor are verified. Grader runtime,
concrete board/coordinate requirements, official unlimited-time translation,
team metadata, and final packaging remain pending inputs. Independent review
results are recorded in [issue-7-review.md](issue-7-review.md).
