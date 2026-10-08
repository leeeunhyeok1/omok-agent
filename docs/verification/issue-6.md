# Issue #6 acceptance evidence

Implemented “Record and replay games with corruption checks”, bounded by Phase 01
issue #2 and project context #1. Source and documentation additions are AI-written
by OpenAI Codex. No LLM usage records were created, as requested by the user.
Existing attribution and professor-provided player files are preserved.

## Decisions

New standard-library JSON traces use `omok-game-v2`; existing v1 traces remain
replayable. Returned, applied, and failure events are distinct. Applied events
include complete intermediate state; the accepted `moves` summary remains for
existing consumers and is checked against those events. Failed calls never apply
their returned coordinates. Configuration is copied as finite JSON before play.
Player module/qualified name and available defining-file SHA-256 identify source;
CLI config retains seed, named versions, runtime/hardware, and worker settings.
Unknown source hashes remain null rather than inventing a version.

Replay uses only stored coordinates and the simulator, without instantiating or
importing players. It checks captured-cell sets (including duplicate rejection),
intermediate/final boards and sides, outcome/reason/winner, event sequencing,
execution accounting, and cap/failure classification. Clock measurements are
checked for consistency, not rerun. Duplicate JSON keys, nonfinite numbers,
unsupported versions, truncated records, malformed types, and inconsistent
states produce errors. Failure evidence and source identity cannot authenticate
what an external player actually did; this is a consistency format.

Record/replay commands and field semantics are in [../runner.md](../runner.md).
Generated traces remain outside the agent under `.scratch/issue-6-smoke/`.
No search, league, GUI, submission packaging, or hard timeout isolation was added.

## Validation

- `python3 -m unittest discover -s tests -q`: 61 tests passed, including the
  numeric-overflow regression added after review.
- Targeted replay and runner suites pass. JSON round trips cover a completed
  nine-move empty-board game, mover win, capture-induced opponent win, simultaneous
  draw, and dense full-board draw. Corruption checks cover captures, final result,
  intermediate state, move/color types, event order/content, clocks, source hash,
  missing/truncated fields, duplicate keys, and nonfinite configuration.
  The trace reader also rejects finite-looking JSON tokens that overflow to
  infinity (`1e999` and `-1e999`).
- Controlled players/clocks verify exception, mutation, invalid move, post-return
  timeout, exhausted-before-call timeout, caps, unlimited budgets, and legacy v1
  replay. CLI subprocess checks reject malformed records cleanly with exit 2 and
  accept a valid capped trace with rules outcome `ongoing`.
- `.scratch/typecheck-env/bin/mypy omok offline verification tests/test_player.py
  tests/test_runner.py tests/test_replay.py`: 18 source files passed. This preserves
  the documented issue #4 typecheck scope.
- `python3 -m compileall -q omok offline verification tests` and `git diff --check`
  passed.
- `python3 -m verification.smoke --issue 6`: eight completed empty-board games
  (four per baseline color, seeds 20261008–20261011, 60,000 ms per player) and three
  probes (two capped, one exhausted-clock failure) all replayed. Completed games
  lasted 17–21 moves. Runs were serial, one worker, with a 30-second external
  deadline per subprocess, on Python 3.14.3 / macOS 13.7.8 / x86_64.
  [Raw smoke evidence](issue-6-smoke.json) records measured durations and results.

Professor-provided integration remains pending the missing base Player module.
The existing runner measures trusted calls after return; never-returning calls
still require an external deadline. These are existing Phase 01 limitations.

Independent review results are in [issue-6-review.md](issue-6-review.md).
