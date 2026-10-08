# Issue #4 acceptance evidence

Implemented “Play bounded games with a legal baseline”, within authoritative Phase
01 issue #2 and project context #1. AI-written by OpenAI Codex (GPT-6.1-sol).

- Full suite: `python3 -m unittest discover -s tests -v` — **48 tests passed**
  in 1.108 seconds, including the existing simulator/reference/differential checks.
- Targeted player/runner/replay tests: **12 passed**. Public seams are the ones
  pre-agreed in issues #1 and #2. Deterministic clock tests establish floor rounding,
  independent cumulative debits, exhaustion without a call, exact-budget acceptance,
  rejection after overtime, and distinct exception/invalid/mutation/timeout failures.
- Runner fixtures complete after one move for mover victory, capture-induced opponent
  victory, and simultaneous draw. Already terminal positions invoke no player.
- Player fixtures cover both assigned colors, empty/sparse/capture/dense live inputs,
  legal return at 0.001 ms incoming time, unchanged input, strict wins with sufficient
  budget, avoiding detected capture-induced loss, and strict win versus simultaneous
  draw. The low-time responsiveness bound is 100 ms, not a claim of satisfying a
  0.001 ms clock on this machine.
- Replay verifies captures, alternation, states, caps/failures, and accounting.
  Damaged captures, final boards, mover colors, missing final state, changed status,
  reason, clocks, and boolean values masquerading as board/capture/winner integers
  are rejected.
- `mypy omok offline verification tests/test_player.py tests/test_runner.py
  tests/test_replay.py` — **18 source files passed**, using the existing ignored local
  `.scratch/typecheck-env`. Broadening to all existing tests reveals the pre-existing
  `tests/test_reference.py:8` class-variable annotation incompatibility between
  `ReferencePosition` and `Position`. Those issue #3 files were unchanged.
- `python3 -m compileall -q omok offline verification tests` passed.
- `python3 -S` import of `omok.player` passed with no site packages; inspected loaded
  modules contain no `offline`, `players`, or `verification`. Agent code imports only
  standard-library modules and the verified simulator and has no network operations.

## Smoke results

`python3 -m verification.smoke` runs one subprocess at a time with a **30-second
external deadline per game**, on Python 3.14.3 / macOS 13.7.8 / x86_64, one worker.
Each regular game uses 60,000 ms per player, cap 1,000, an empty board, and seeds
20261008–20261011 paired in both colors. This is local smoke evidence against
`SeededSmokePlayer`, not provided-bot evaluation or a tournament strength claim.

| Run category | Completed | Capped | Failed |
| --- | ---: | ---: | ---: |
| Regular smoke: baseline black | 4 | 0 | 0 |
| Regular smoke: baseline white | 4 | 0 | 0 |
| Deliberate cap and unlimited probes | 0 | 2 | 0 |
| Deliberate zero-budget probe | 0 | 0 | 1 |

All eight regular games ended with the baseline winning by exact five. Games used
17–21 total moves and 0.277–0.337 seconds wall time including process startup.
Baseline total thinking time was approximately 136–195 ms per game. All eleven
traces passed replay; the exhausted probe records timeout without a player call.
Raw summaries, runtime, clocks, seeds, and trace paths are in
[issue-4-smoke.json](issue-4-smoke.json). Complete local traces are saved under
`.scratch/issue-4-smoke/`; rerun the command to regenerate them on another checkout.
The issue #3 transition benchmark remains applicable because the simulator is unchanged.

## Handoff and limitations

See [runner contracts and commands](../runner.md). The replacement point is
`LegalBaseline.take_turn`/its one-ply selection; rules remain `Position.play` with
owned immutable child states. `DevelopmentPlayer` establishes color and method shape
without inventing official Player inheritance. `SeededSmokePlayer` is isolated offline.

Professor bot integration is pending the absent `player` base module. No supplied
files were changed. Hard per-call process isolation remains deferred: elapsed timing
only rejects returning players, while external smoke deadlines bound verification.
Match crash aggregation, search, league scheduling, optimization, and packaging are
outside this ticket. AI interaction records are preserved under `llm-usage/`.

Independent [two-axis code review](issue-4-review.md) completed with no outstanding
Standards or Spec findings after fixes and targeted re-verification.
