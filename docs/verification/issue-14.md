# Issue #14 acceptance evidence

AI-written by OpenAI Codex. Scope: integrated offline search selection, supplied
inheritance adapter and optional replay-compatible search diagnostics. Master context
is issue #1; no tournament, evaluator redesign or submission packaging is included.

## Verified boundaries

Tests use the previously agreed public player and complete-runner seams from issue
#1. Each new capability started with a failing test before implementation.
`tests.test_integration` verifies opt-in snapshots leave moves/clocks unchanged,
independent PV replay, per-call cold/warm table counters, explicit-color supplied
inheritance, both-color CLI selection against the retained baseline, mandatory wins
and capture defenses with cap one, cached/uncached/unpruned identical tactical trees,
node-limit interruptions and recovery, deadline interruption of tactics/deeper
iterations with retained commitment, and exception/mutation/illegal/timeout reporting
when optional diagnostics fail. Zero-move verification caps return valid summaries. Existing replay readers are unchanged.

## Measured smoke games

Run `python3 -m verification.integration`; summary is in
[issue-14-games.json](issue-14-games.json). Six seeded games use both colors against
LegalBaseline and the unchanged supplied RandomPlayer/SimplePlayer, one worker,
independent 60000 ms clocks and an explicit 12-ply resource cap. Five runs stopped
as `capped/move_cap` with live boards; one ended through the exact-five rule. These
are integration smoke runs, not win-rate or tournament-strength evidence.

All 72 applied moves, six traces and 36 complete committed PVs passed independent
reference replay. Both player clocks strictly decreased on their own turns, with no
observed execution failures. Largest public search elapsed time was about 100.17 ms
on a 100 ms allocation; the cooperative deadline is not a hard preemption guarantee.
No turn exhausted its incoming total clock. Largest table held 1061 entries, below
4096. Full traces are retained locally in `.scratch/issue-14/`; regenerate them with
the command above. Summary records runtime, seeds via trace configuration, colors,
opponents, clock settings and measured timing. These bounded games do not establish
reliability for an entire official eight-game match or unknown grading hardware.

## Checks and external gates

- Targeted: `python3 -m unittest tests.test_integration -v`.
- Types: `/tmp/omok-issue14-types/bin/mypy omok offline --ignore-missing-imports`
  (temporary verification environment; no new engine dependency).
- Syntax/import compilation: `python3 -m compileall -q omok offline verification tests`.
- Full suite: `python3 -m unittest discover -s tests -v`.

Grader board types/runtime, final team naming and official unlimited-time translation
remain unresolved external checks. Professor sources are unchanged. The baseline,
rule outcomes, replay formats and cumulative-clock accounting are retained. Existing
user deletions under `llm-usage/` and the untracked phase specification are excluded
from this implementation commit.

Validation passed: 118 tests, type checking of all 13 engine/runner files,
compilation, and diff whitespace checks. See [the two-axis review](issue-14-review.md).
