# Issue #18 acceptance record

AI-written by OpenAI Codex. Issue: “Evaluate open and broken threes and smaller
line potential”; context: GitHub #1 and the supplied Phase 3 specification.
Review baseline: `6172fecfa054dda39b90c19644613d3c0023c981`.

Implemented the explicit experimental `potential-v1` configuration, with open
threes (40), broken threes (25), two-stone potential (5) and material (1).
Definitions, counted units, development exclusions, deliberate overlaps and
zero-sum construction are in `docs/evaluation.md`, separate from the supplied
specification. Existing material-v1/lines-v1 files and persisted identities remain
unchanged. The Phase 2 default and checkpoint remain available.

Used the previously agreed inspection/search/public-player seams. The first
literal open-three test failed on unsupported potential-v1 before implementation;
the saved-config test failed on the missing file before it was added. Six new
behavior tests cover 18 literal fixtures in both colors and all eight board
symmetries, deduplicated development windows, blocked/edge/overline development,
intersecting axes, independent reference exactly-five outcomes after development,
configuration loading/validation, ablation, boundedness, table invalidation,
matched alpha-beta/reference trees through depth three for both sides, public
turn configuration, input ownership, cancellation with no completed partial
result/table entry, low-time legal moves, mandatory wins/capture defenses and
terminal score priority. Existing four/material behavior tests also pass.

Commands:

```sh
python3 -m unittest tests.test_potential tests.test_lines tests.test_evaluation -q
.scratch/typecheck-env/bin/mypy omok offline verification/evaluation.py verification/potential.py --ignore-missing-imports --follow-imports=silent
python3 -m unittest discover -s tests -q
python3 -m verification.potential --repetitions 10
```

Focused suite: 19 tests passed. Typecheck: 17 source files passed.
Full suite: 138 tests passed in 20.007 seconds.

The reproducible `issue-18-suite.json` embeds seven nonterminal boards,
configuration, raw counts/units and weighted contributions, potential-disabled
inspection and static evaluation timings. Dense board seed: 20261015, 222 stones.
Scores under this provisional configuration are open three 43, broken three 28,
two 7, blocked three 2, edge three 3, overline-adjacent 454 and dense 1329.
The overline-adjacent fixture has zero potential but existing four/completion
contributions: potential exclusions do not erase stronger features. Open > broken
is a configured preference, not a game-rule fact or a measured strength claim.

Single-process median static evaluation was 5.79–9.08 ms across these positions.
This added cost supports retaining the Phase 2 default. Timing includes existing
four/win verification and is not isolated potential cost or official-clock
acceptance. No leagues, optimization, search extensions or packaging are added.
No LLM usage is recorded. Pre-existing deletions and the supplied specification
are excluded from the implementation commit.

The required independent two-axis review is recorded in `issue-18-review.md`.
Standards and Spec reviewers both reported zero findings. The final follow-up
only records those review results.
