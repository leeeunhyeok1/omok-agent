# Issue #17 acceptance record

AI-written by OpenAI Codex. Issue: “Evaluate fours and rule-verified exact-five
continuations”; context: GitHub #1 and the user-supplied Phase 3 specification.
Review baseline: `4105d16b112f754df5169db33b63dd0829b2f901`.

Implemented `lines-v1` as an explicit experimental configuration. Definitions,
overlap policy, coefficient bounds, ablation and inspection are recorded in
`docs/evaluation.md`; reproducible coefficients are in `configs/lines-v1.json`.
Phase 2 remains the default and its saved configuration is unchanged.

The agreed seams from #1 cover independent simulator/reference outcomes, public
player behavior and matched-candidate alpha-beta/reference search. The first
open-four test failed on the unsupported lines-v1 version before implementation.
The eight line tests cover the specified five completion fixtures, an endpoint
with an own stone beyond it, both colors and all eight geometric symmetries,
shared endpoints, a contiguous overline, capture-induced opponent wins and
simultaneous draws, a capturable open four and safe public response, configuration
serialization/validation/ablation/table invalidation, bounds and cancellation,
matched trees through depth three, public strict wins under negative weights,
low-time legal moves, immutable input and terminal priorities. Geometric features
are deliberately separate from strict-win labels. Independent reference outcomes
are used for the specified completion and capture fixtures.

Commands:

```sh
python3 -m unittest tests.test_lines tests.test_evaluation -q
.scratch/typecheck-env/bin/mypy omok offline verification/evaluation.py --ignore-missing-imports --follow-imports=silent
python3 -m unittest discover -s tests -q
```

Focused suite: 13 tests passed. Typecheck: 16 source files passed.
Full suite: 132 tests passed in 15.660 seconds. No LLM usage was recorded per user
instruction. Existing uncommitted deletions and supplied specification were not
included in the implementation commit.

`issue-17-timing.json` records 30 single-process calls per fixture, runtime and
machine. Median full line evaluation was 1.52–3.28 ms versus 0.025–0.026 ms for
configured material on empty, open-four, capture-defense and full dense boards.
This is a substantial cost increase and supports retaining the Phase 2 default.
These are static development timings, not wall-clock game or strength evidence.
No leagues, tuning, promotion, extensions or packaging were implemented. Required
line features remain checked and selectable; subsequent tickets own other Phase 3
families and broader evaluator comparisons.

The required two-axis review is recorded in `issue-17-review.md`. Its one
nonblocking duplication finding was fixed and confirmed by both reviewers.
Afterward the focused suite and typecheck passed again; the final full suite
passed all 132 tests in 15.599 seconds.
