# Issue #10 — Verified fixed-depth search player

Implemented on 2026-10-09 (Asia/Seoul), against issue #10 and the fixed-depth
subset of issue #9, with master issue #1 and core issue #2 as context.
AI-written by OpenAI Codex. Phase 01 simulator, baseline, supplied-player adapters
and trace format are preserved; restorable baseline commit:
`c0c56fa40826719794f0765fd35464a5c0174cc3`.

## Changes and decisions

- `FixedDepthSearch.search`: deterministic unpruned reference and production
  fail-soft Negamax alpha-beta, always with a full root window.
- Explicit recursive perspective handles the simulator's retained terminal mover.
  Wins/losses are +/-10000; draws are zero; the replaceable black-centric evaluator
  accepts bounded integers only (limit +/-4000). Default material range is +/-361.
- Full-width row-major legal trees by default, configurable deterministic trees
  for tests, validated unique candidates, and all-legal fallback for empty lists.
- Copy-based simulator transitions preserve all parent/sibling/caller state on
  completion, cutoffs, cancellation and propagated defects.
- `FixedDepthPlayer.take_turn` owns input, uses explicit color, bounds development
  work by depth/nodes/time, and exposes a completed result or legal fallback.
  No partial root score is exposed as completed.

[The contract](../search.md) records chosen APIs, exact tree definitions, scoring,
fail-soft semantics, callback requirements, counter meanings and cancellation
limits. No extensions, speculative pruning, tables, tactical candidate caps or
iterative deepening were introduced. Those belong to separate tickets.

## Actual verification

Python 3.14.3 on macOS 13.7.8 x86_64. No grader-runtime assumption or performance
threshold is inferred. Existing core evidence and handoff were read before edits.
There were no concrete prerequisite defects to repair.

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s tests -q` before edits | 64 passed, 2.117 s. |
| `python3 -m verification.differential` before edits | 5,561 transitions, 32 seeded sequences, no mismatch, 10.033 s. Same seeds/modes/caps as Phase 01: 30 terminal sequences, two 240-move verification caps. |
| `python3 -m unittest tests.test_search -v` | 17 new tests passed. Targeted checks ran throughout red/green implementation; final targeted run 0.572 s. |
| `python3 -m unittest tests.test_search tests.test_player -q` during integration | Search and retained baseline checks passed together. |
| `python3 -m unittest discover -s tests -v` at completion | 81 passed, 2.701 s. |
| `.scratch/typecheck-env/bin/mypy omok offline verification tests/test_search.py` | 21 source files passed; default mypy leaves untyped test bodies unchecked. |
| `.scratch/typecheck-env/bin/mypy --strict omok/search.py omok/player.py verification/search.py` | All three files passed, including typed production bodies. |
| `python3 -m compileall -q omok verification tests` | Passed syntax checks. |
| `git diff --check` | Passed whitespace checks. |

Matched-tree tests include hand-calculated nonterminal values at depths 0–3,
both colors, tie-aware root membership, observed recursive cutoffs, ten signed
weighted four-cell trees (seeds 0–9) at depths 1–4, and full-width late-board trees
at depths 1–3. Captures reopen legal cells in the full-width fixtures; those cells
remain in later candidate sets. The tests compare exact full-window values and
reference optimal-set membership, not merely identical selected coordinates.

Rules/search checks cover all four exact-five orientations and both colors;
overline completion; capture-induced opponent victory; simultaneous-win draw;
full-board draw at entry and after the final placement; strict win versus draw;
and capture removal counting as one placed-stone depth. Same-board values negate
between perspectives and invalid evaluator outputs are rejected.

For each algorithm every smaller node budget than its completed depth-three
capture tree was injected. All returned legal fallbacks with no partial score,
preserved root/sibling/caller state, and permitted an identical later search.
Controlled deadlines cancel before search, inside candidate enumeration and after
evaluation. Requested cancellation is explicit. A controlled evaluator defect
after capture propagates through both search modes and the public player; the
captured child remains independent and subsequent clean search succeeds.

## Public timing and isolated execution

`python3 -m verification.search > docs/verification/issue-10-timing.json` produced
[64 probes](issue-10-timing.json): empty, capture, immediate-win and dense live
boards, both explicit colors, configured depths 1/2, and remaining budgets
-1/60000/3/0.5 ms. Every returned move was validated through the simulator; caller
boards remained unchanged. Each call was independent, not a cumulative-clock
game or strength comparison.

| Remaining ms | Calls | Completed | Observed public-turn ms, min–max | Incomplete reason |
| --- | --- | --- | --- | --- |
| -1 (bounded local development) | 16 | 10 | 1.015–100.077 | deadline |
| 60000 | 16 | 10 | 1.021–100.071 | deadline |
| 3 | 16 | 0 | 0.113–0.556 | deadline |
| 0.5 | 16 | 0 | 0.098–0.542 | low_time |

Depth-two full-width trees can exhaust the 100 ms bound. Cooperative atomic work
can exceed its checked deadline slightly; these results do not prove a hard
deadline or unknown-hardware performance. Dense conversion alone can exceed a
0.5 ms incoming clock, so tiny-time legality is not a timeout guarantee.

```sh
sandbox-exec -p '(version 1)(allow default)(deny network*)' python3 -I -S verification/offline_engine.py --search > docs/verification/issue-10-offline.json
```

[The isolated probe](issue-10-offline.json) passed with engine/stdlib-only imports,
site packages disabled, Python socket audit rejection and macOS OS network denial.
Both explicit colors returned legal moves without caller mutation. Portable rerun:
`python3 -I -S verification/offline_engine.py --search`; it provides the import and
Python socket guards without claiming OS-level denial on other systems.

## Handoff and scope

Issue #10 fixed-depth acceptance passed. This is not whole-Phase-02 acceptance.
Default material is deliberately weak and untuned; cancellation uses the initial
fallback rather than partial promising moves. No forced-defense or tournament
strength claim is made. Next work should retain the fixed-depth verification mode
while adding issue #11's completed-iteration retention and clock manager, then
issues #12–#15's tactical candidates, caching, runner integration and acceptance.
Official final inheritance/naming, runtime, sentinel and packaging remain pending.

Baseline access and existing AI attribution are retained. Pre-existing local
deletions under `llm-usage/` and the untracked `02_SEARCH_ENGINE_SPEC.md` are excluded
from this work's commit. The required [two-axis review](issue-10-review.md) found
zero Standards and zero Spec findings; no issue comments, publication or push was
performed.
