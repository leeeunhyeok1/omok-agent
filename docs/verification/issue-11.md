# Issue #11 acceptance evidence

Implemented “Return committed search results within the remaining game clock” on
2026-10-09, against issue #1 master context and parent issue #9 Phase 02 scope.
AI-written by OpenAI Codex. Pre-work checkpoint:
`588e8a4d3d9e7ee2ffcb03ea4d2d1a7af345fe1a`.

The agreed seams are public `take_turn`, search result correctness and restoration,
and independent PV replay, as established by master section 8 and parent sections
11.2–11.3. Tests inspect public calls/results, not traversal internals.

## Decisions and verification

The API, provisional formula, reserve/margin/limits, shared tactical cancellation
checkpoint, counters and diagnostic semantics are documented in
[docs/search.md](../search.md). Only complete root iterations commit move, score,
depth and PV. Aborted lines are discarded. All board state remains immutable.
Fixed-depth reference comparisons and the original baseline remain available.

- Red/green: initial iteration test failed because `iterative` was absent; public
  clock test failed because `IterativePlayer` was absent; cooperative scan test
  failed because its hook was absent. Each passed after its implementation slice.
- Six new tests cover every node limit below completion of a restricted depth-4
  capture tree, including cancellation before depth 1, during depth 2 and after
  deeper completion; root, sibling and external board equality and subsequent
  searches against clean equivalent engines.
- Fake clocks cancel inside candidate scans, ordering and cooperative evaluation,
  and at measured checkpoint offsets after depths 1 and 3. Soft stops preserve
  completed commits. Public cancellation returns its committed move/score/PV.
- Independent rules replay checks both colors, material leaves, terminal exact-five
  lines, coherent horizon length and committed scores. Terminal lines may be
  shorter than depth; interrupted diagnostic lines are unavailable.
- Public conversion advances a fake clock beyond the allocation, proving conversion
  consumes the public budget. Zero/negative/tiny time uses legal fallback; bounded
  local `-1` remains distinct from unresolved official semantics.
- Unexpected evaluator errors propagate and clear public diagnostics. Invalid
  limits, time fractions and nonfinite time fail visibly.
- `python3 -m unittest tests.test_iterative tests.test_search -q`: 22 tests passed
  before the final additional public/configuration test.
- `python3 -m unittest tests.test_iterative -q`: all 6 new tests passed.
- `python3 -m unittest discover -s tests -q`: **87 tests passed**, 3.266 seconds.
- `PYTHONPATH=/tmp/omok-issue11-typecheck python3 -m mypy --follow-imports=silent
  omok/search.py omok/player.py`: passed for both changed annotated engine modules.
  Mypy 2.4.0 was installed outside the repo as optional development tooling.
- `python3 -m compileall -q omok verification tests`: passed syntax checks.

## Actual public timing

`python3 -m verification.iterative` produced
[issue-11-timing.json](issue-11-timing.json), Python 3.14.3,
macOS 13.7.8 x86_64, one worker. **349 calls** cover empty, sparse capture, tactical
and dense live boards, both colors, three repetitions per independent budget,
and up to twelve board-updating calls with a genuinely decreasing cumulative
40 ms clock. Defaults: depth 8, 10000 cumulative nodes, policy as documented.

| Incoming ms | Independent calls | Observed elapsed ms | Completed depths |
| --- | ---: | --- | --- |
| -2 | 24 | 0.102–0.663 | 0 |
| 0 | 24 | 0.102–0.778 | 0 |
| 0.001 | 24 | 0.100–0.556 | 0 |
| 0.1 | 24 | 0.100–0.618 | 0 |
| 1 | 24 | 0.103–0.584 | 0 |
| 3 | 24 | 0.113–0.710 | 0 |
| 5 | 24 | 0.164–0.568 | 0 |
| 20 | 24 | 0.924–1.067 | 0 |
| 200 | 24 | 4.568–11.298 | 0, 3, 8 |
| 60000 | 24 | 5.005–143.001 | 1, 5, 8 |
| -1 (local) | 24 | 4.612–102.128 | 1, 5, 8 |

No exceptions, illegal moves or input mutations were observed. **47 positive-clock
exceedances** occurred: all 24 calls at 0.001 ms and 23 of 24 at 0.1 ms. These are
real limitations, not suppressed failures. Zero/negative clocks are fallback probes,
not successful game-clock claims. No incoming-clock exceedance was observed at
1 ms or above or in the decreasing-clock sequence.

An empty-board white call with 60000 ms incoming exceeded its 100 ms allocation:
143.001 ms, retaining depth 1 and interrupting attempted depth 2. The cause of this
spike is not established; scheduler delays and atomic operations are limitations
of cooperative cancellation. Allocation overshoot is visible in raw records and
must be remeasured before tuning/promotion. Unknown grader hardware, blocking
callbacks and submillisecond mandatory validation cannot carry hard guarantees.
This ticket establishes control-flow correctness and provisional clock behavior,
not tactical strength, tuned reserves or complete Phase 02 acceptance.

Existing user-deleted LLM records and the untracked phase specification are excluded
from this checkpoint. The current visible interaction is preserved separately in
`.scratch/issue-11-interaction.jsonl` for eventual disclosure, without restoring
those deleted files. Exporting the final response can be repeated with the existing
`verification.export_interaction` utility.

## Spike follow-up and review

The initial timing pass ran while optional typechecking was completing in another
local process; background machine load was not controlled. A separate sequential
12-call empty-board white follow-up at 60000 ms incoming produced
**100.039–100.257 ms**, depth 1 committed in every call, no illegal moves, mutations
or incoming-clock overruns. Raw records:
[issue-11-spike-followup.json](issue-11-spike-followup.json). This does not establish
the initial spike's cause or erase it. Minor cooperative-deadline overshoot remains.

The code-review skill ran independent Standards and Spec agents. Spec reported
zero findings. Standards reported zero documented violations and one optional
Duplicated Code smell: material scoring appeared both in the public evaluator and
its checked default search branch. The review-stage refactor consolidates this
formula in `material_evaluation(position, check=...)`, preserving its one-argument
interface and per-row cancellation. The independent reference recursion is retained.
The affected 23 search/iteration tests and engine typecheck pass after refactoring.
The Standards reviewer verified the fix and reported no remaining concerns.
The full 87-test suite and compileall passed again after the review-stage refactor.
