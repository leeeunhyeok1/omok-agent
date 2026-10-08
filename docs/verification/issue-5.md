# Issue #5 acceptance evidence

Implemented “Add verified one-ply baseline choices”, within Phase 01 issue #2 and
project context #1. AI-written by OpenAI Codex. The professor-provided files remain
unchanged. No LLM interaction transcript was recorded, as explicitly requested by
the user; attribution is retained in source comments and this report.

## Decisions

The issue #4 baseline already simulated legal children and classified strict wins
and capture-induced losses. This ticket adds modest capture/locality scoring,
checks the deadline before optional preparation and scoring, and preserves a safe
legal choice when optional evaluation throws. `Position.play` remains the rules
source: captures and both-color exact-five outcomes resolve before classification.
Simultaneous wins are draws, never strict wins. An observed opponent win is excluded
from scoring; a known safe alternative replaces an unverified fallback.

All legal candidates remain eligible. Deterministic order is adjacent own stones,
Manhattan center distance, row, then column. Scores are **4 per captured stone and
1 per adjacent own stone**, with equal scores retaining candidate order. These are
explicitly temporary, untuned baseline parameters. No multi-ply search, comprehensive
forced defense, mature evaluator, or candidate pruning was added.

Timing retains temporary baseline allowances: 10% of incoming remaining time after
2 ms reserve, capped at 100 ms; unlimited mode also caps optional work at 100 ms.
The monotonic start precedes input conversion. The baseline preserves a row-major
legal fallback at tiny positive time or exhausted allowance. Conversion, ordering,
and a single in-progress transition/scoring call cannot be preempted; submillisecond
remaining time cannot guarantee an on-time return. Deadline injection verifies
conversion and explored-child stopping separately from scheduler-dependent timing.

## Validation

- `python3 -m unittest discover -s tests -q`: **53 tests passed in 3.302 seconds**.
- Targeted player and runner suites pass. Fixtures cover unique strict wins in all
  four orientations for both colors, modest capture preference, capture-induced
  opponent victory avoidance, strict win versus simultaneous draw, and legal moves
  with unchanged input on empty, sparse, capture-heavy, and dense live boards.
  The latter run for both colors at 0.001 ms, 60,000 ms, and unlimited incoming time.
- Controlled monotonic clocks stop after conversion and after ordinary/capturing
  children. Owned parent and external input remain unchanged. Diagnostic evaluation
  fault injection throws after a capture, verifies the isolated child and intact
  parent, and demonstrates legal subsequent choices and a successful later call.
- Runner integration completes unique-win fixtures in both colors after one move;
  traces replay successfully. Existing simulator/reference/differential/restoration
  fixtures continue to pass.
- `.scratch/typecheck-env/bin/mypy omok offline verification tests/test_player.py
  tests/test_runner.py tests/test_replay.py`: **18 source files passed**. Scope follows
  issue #4; its documented pre-existing reference-test annotation issue is unchanged.
- `python3 -m compileall -q omok offline verification tests` and `git diff --check`
  pass.

One initial suite run overlapped typechecking and exposed scheduler-dependent capture
selection and a 200 ms normal-time assertion. Capture scoring now uses a controlled
clock to guarantee complete analysis; normal-time responsiveness permits 1 second
of scheduling tolerance, while tiny-time checks retain their 100 ms bound. The
serial full-suite run above passed. These tolerances are test bounds, not engine
allowances or tournament guarantees.

## Runner demonstration

`python3 -m verification.smoke --issue 5` runs serially with a 30-second external
subprocess deadline, one worker, Python 3.14.3 / macOS 13.7.8 / x86_64. Eight regular
empty-board games use 60,000 ms per color, cap 1,000, seeds 20261008–20261011 paired
in both colors. All eight completed by exact five in 17–21 moves; all eleven traces
(including two cap probes and a deliberate zero-budget timeout) replayed successfully.
Raw evidence is [issue-5-smoke.json](issue-5-smoke.json); complete replayable traces
regenerate under `.scratch/issue-5-smoke/`. This demonstrates legal integration with
`SeededSmokePlayer`, not a win-rate threshold or tournament strength.

Usage and timing contracts are in [../runner.md](../runner.md). Official professor
Player integration remains pending its missing base module; later search,
optimization, and packaging are deferred. Independent Standards and Spec review
results are recorded in [issue-5-review.md](issue-5-review.md).
