# Issue #12 acceptance evidence

Implemented “Choose rule-correct tactical moves without losing them to candidate
caps” against issue #1 master context and parent #9 Phase 02 specification.
Pre-work checkpoint: `6841a43fa0b4d605f379ff01bb819ff4d8082dc0` on `main`.
AI-written by OpenAI Codex. The agreed simulator/public-player/search seams come
from master section 8 and parent sections 3 and 10–11.

## Behavior and evidence

The selected APIs, completeness policy, one-ply safety guarantee, default radius
2/cap 24, ordinary ranking and PV ordering are in [the search contract](../search.md).
The default iterative player integrates tactics; the unchanged full-width search
configuration and baseline remain available. Complete outcomes are classified
through resolved simulator results; heuristic weights establish no tactical truth.

- Red/green: the first public tactical test failed on the absent tactical module,
  then passed with verified win membership and ordering. The capture test failed
  with absent opponent threats, then passed with exhaustive response analysis.
- Both colors: unique immediate wins in every orientation survive cap 1 and poor
  ordinary ordering. Overlines are excluded while distinct exact-five wins are
  selected. Simultaneous draws and capture-induced opponent wins match independent
  reference outcomes. A verified strict win beats the available simultaneous draw.
- Single direct defense, multiple endpoints, and the specified capture defense:
  both direct blocks are independently refuted. `(7, 7)` is retained despite poor
  ordinary ranking. Every legal independent opponent reply after that capture is
  enumerated, including reopened cells, without assuming defense uniqueness.
- A response that captures away the original four is rejected when its two captures
  shorten an unrelated six to a four, creating new winning endpoints `(8, 7)` and
  `(8, 12)`. Both replies are verified independently for both colors.
- Tractable dense fixtures compare every strict win, opponent threat and complete
  defense with exhaustive placements and replies from `ReferencePosition`. The
  oracle does not use the engine's geometric filter. Full-width tactical search
  agrees with original full-width unpruned search through depth 3, both colors.
  Selective trees also match alpha-beta and unpruned Negamax with varied ordering.
- Locality produces unique legal candidates, documented center opening and legal
  fallback with radius 0. Mandatory tactics bypass caps. No-defense results retain
  ordinary choices without manufacturing a forced-loss score.
- Deterministic cancellation at multiple tactical checkpoints preserves all legal
  membership and accurate partial flags. Cancellation occurs inside ranking and
  sort comparisons; public calls preserve root/external state and legal fallback.
  A verified win survives an interrupted scan with depth zero/absent score.
  Interruption in depth 2 retains the entire completed depth-1 commit, while its
  independent latest tactical diagnostic correctly reports incomplete analysis.
- The existing exhaustive node-interruption, exception propagation, PV replay and
  matched-tree checks pass after integration.
- `python3 -m unittest tests.test_tactics tests.test_iterative tests.test_search -q`:
  **34 tests passed**, 4.167 seconds.
- `PYTHONPATH=/tmp/omok-issue11-typecheck python3 -m mypy --follow-imports=silent
  omok/search.py omok/player.py omok/tactics.py`: passed. Mypy is optional local
  tooling installed outside the repo; engine dependencies remain standard library.

## Actual public timing

`python3 -m verification.tactics` records [issue-12-timing.json](issue-12-timing.json):
Python 3.14.3, macOS 13.7.8 x86_64, one worker; depth 8, 10000 cumulative recursive
nodes and a 100 ms maximum allocation. **60 public calls** cover both colors on
empty, winning, capture-defense and dense boards at incoming clocks 1, 3, 20, 200,
60000 and bounded local -1; twelve additional calls within that total use actual
board updates and decreasing cumulative 40 ms clocks. Independent reference checks
validate all returned moves. No exceptions, illegal moves, input mutations or
incoming-clock overruns were observed in this run.

At 60000 ms incoming, both colors choose `(7, 7)` for the capture defense with
depth 2 committed. Both choose a verified immediate win on the win fixture and
`(0, 4)` on the dense direct-defense fixture. The default empty-board opening is
`(9, 9)`. Public elapsed times for these eight calls were 100.045–100.092 ms:
cooperative work can slightly exceed its 100 ms allocation, which is distinct
from exhausting the incoming game clock. No hard timing guarantee is claimed.

An initial development probe returned fallback after exhausting 100 ms during
response enumeration. Checking verified existing threats first can refute unsafe
responses early; safe claims still use complete scans on resulting boards. A
subsequent depth-1 capture probe completed in 30.756 ms (black) and 31.078 ms
(white). The full depth-8 timing evidence above is from the resulting implementation.
Low budgets may leave tactics unknown and return legal fallback rather than a
perfect response. Runtime scheduling, atomic transitions and unknown grader
hardware remain limits; this work does not claim tuned strength or complete
Phase 02 acceptance. Transposition tables and league integration are later tickets.

The existing user deletions and untracked phase spec are excluded from the commit.
Visible interaction records are preserved separately under `.scratch/` without
restoring the deleted records. Review and final checks are recorded below.


## Review and final checks

[The two-axis code review](issue-12-review.md) ran independent Standards and Spec
agents. One optional duplicated-loop smell was consolidated with a shared verified
win iterator, preserving partial wins. One verification gap was closed by sweeping
**every public clock checkpoint** of a complete turn, including locality generation
and comparison sorting. Both reviewers verified the fixes and reported zero
remaining findings. All membership sorts now use checked comparisons.

- `python3 -m unittest tests.test_tactics -q`: **12 tests passed**, 4.139 seconds.
- `python3 -m unittest discover -s tests -q`: **99 tests passed**, 7.534 seconds.
- Three-module mypy typecheck and `python3 -m compileall -q omok verification tests`:
  passed after the review changes.
- The final timing rerun refreshed the linked raw file: **60 calls**, no observed
  illegal moves, mutation, exceptions or incoming-clock exceedances. Both colors
  still select `(7, 7)` on the capture fixture with depth 2 committed.
