# Issue #11 code review

Reviewed using the code-review skill's independent parallel Standards and Spec
agents, against pre-work checkpoint
`588e8a4d3d9e7ee2ffcb03ea4d2d1a7af345fe1a`.
Diff command: `git diff 588e8a4d3d9e7ee2ffcb03ea4d2d1a7af345fe1a...HEAD`.
Initial reviewed commit: `c3fd5ca Retain committed iterative search within
 game-clock budgets (#11)`. This report and the reviewed fix are included in the
amended checkpoint. AI-written by OpenAI Codex.

## Standards

No documented-standard violations found.

One judgment-call smell: possible Duplicated Code in `omok/search.py`. The new
default-evaluator branch repeated `material_evaluation`'s cell scoring:

```python
value += sum(1 if cell == 0 else -1 if cell == 1 else 0 for cell in row)
```

Future evaluation changes could update the public evaluator while leaving the
default search path unchanged. Give `material_evaluation` an optional checkpoint
argument and call it from `score`, preserving its existing one-argument interface.
Keep the separately implemented reference recursion unchanged.

Resolution: implemented that consolidation during review. The affected search
checks and typecheck passed afterward.

Standards: 0 hard violations, 1 optional smell addressed.

## Spec

No actionable Spec findings against issue #11 or the supplied master context.

The change implements public-boundary timing, documented provisional
allocation/reserve/margin, legal fallback, atomic completed-result retention,
attempted depth, shared cooperative cancellation, bounded local `-1`, independent
PV replay, and actual public timing measurements. Deterministic node-budget tests
cover interruptions across all restricted-tree nodes through depth 4, preserving
committed results and comparing subsequent searches against fresh engines.

`python3 -m unittest tests.test_iterative`: six tests passed.

Timing evidence records submillisecond incoming-clock overruns and a 143 ms call
against a 100 ms allocation. These remain material limitations, explicitly
disclosed under the requirement to “label scheduling and cooperative-cancellation
limitations.” No unexpected scope expansion identified.

Standards: 0 outstanding findings; Spec: 0 findings, no worst issue.

The Standards reviewer independently verified the consolidation, including per-row
checks and backward-compatible evaluator calls: no remaining Standards concerns.
The full 87-test suite and compileall passed again after this review-stage change.
