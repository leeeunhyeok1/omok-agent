# Issue #27 acceptance

Implemented “Execute reproducible color-balanced experiment plans” against master
issue #1 and phase #24. See [the public contract](../experiments.md) and
[the two-axis review](issue-27-review.md).

## Behavior

- Immutable resolved manifests save versions/configurations, protected pools,
  policies, concrete jobs, resource settings and observed runtime/hardware.
- Paired slots exchange colors while retaining role seeds and recorded openings.
  Unsupported seeds and deterministic duplicate evidence are explicit.
- Official plans require eight empty-board games per opponent, four per color,
  and 60,000 ms per player. Development, reduced-clock screening and artificial
  fixture modes remain distinct.
- Serial execution preserves every slot through crashes, setup failures and caps.
  Raw replayable traces retain the registry metadata contract. Actual turn attempts
  and applied moves are recorded separately from preflight.
- Existing simulator, engine, evaluator and time allocation are unchanged.
  Match scoring, retries/resume and ratings remain separate tickets.

## Validation

The agreed public seams are plan resolution/save/load and serial execution/API/CLI.
Eight new tests cover official slots, immutable recreation, paired colors/openings/
seeds, identity changes, duplicate disclosure, illegal openings/policy rejection,
protected holdout selection, capped execution/replay, crash continuation,
changed-source setup failures, unlimited watchdogs, unavailable candidates and
exclusive CLI evidence writes. Tests were developed through failing-then-passing
slices; `tests.test_experiments` passes.

A saved/restored official plan was executed with the retained phase-01 player and
smoke opponent under an explicit zero-move cap. All eight slots remained present,
four per color, with original 60,000 ms budgets, replay-valid traces and zero turn
exposure. Counts: planned 8, capped 8, completed/failed/pending/infrastructure-failed
0. This checks scheduling/cap accounting; it is not a strength result or completed
competitive official match. Local artifacts: `.scratch/issue-27-official-plan.json`
and `.scratch/issue-27-official-run/`.

An initial full run passed 197/198 tests. The existing setup-classification test
used a 200 ms startup deadline; measured setup for its import-error cases took
211–358 ms, producing startup timeouts before the intended error classification.
The same test failed alone. A finite 1,000 ms allowance now distinguishes
constructor loops from setup errors and passes in isolation. Only that test's
budget changed; production deadlines and all result assertions remain intact.
Both review agents accepted the correction.

Final checks:

- `python3 -m unittest discover -s tests -q`: 199 tests passed (171.281 seconds).
- `python3 -m compileall -q omok offline verification tests`: passed.
- `.scratch/issue-21-tools/bin/python -m mypy omok offline --follow-imports=silent`:
  passed, 29 source files.
- Diff whitespace checks: passed.
- Standards review: zero remaining findings; Spec review: zero remaining findings.

No LLM usage record was created. Pre-existing unrelated workspace changes are
excluded from the implementation commit.
