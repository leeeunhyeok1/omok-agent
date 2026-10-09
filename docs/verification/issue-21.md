# Issue #21 acceptance

AI-written by OpenAI Codex. Issue: “Measure evaluator cost through search
diagnostics and replayable runs.” No LLM usage records were created.
Definitions, provisional measurement decisions and commands are in
[the measurement contract](../measurement.md).

## Evidence

[Recorded runs](issue-21-measurement.json) contain eight frozen-tree comparisons
and two real-clock material games, with canonical loaded/reloaded configurations,
actual initial boards/colors, source identities, opponent version, settings,
sampling overhead and observed hardware/runtime/worker conditions.

All eight comparisons completed depth two. Material and effects configurations
visited the same five nodes in fixed-depth reference search; node-budget runs
visited seven nodes. Completed plain/sampled scores, moves, node counts and
cancellation status matched. Sparse fixture plain runtime was 0.45–0.52 ms for
material and 55–68 ms for effects in fixed-depth runs; node-budget runs were
0.79–0.92 ms versus 72–88 ms. These timings exclude frozen candidate preparation.
(Times are rounded; the JSON is authoritative.) Paired sampled timing
can be faster due to noise/cache/order effects and is reported honestly.

Both six-ply material games against retained Phase 2 replayed successfully,
completed depth two on all turns, kept legal coordinates and immutable caller
boards, and debited each side's cumulative 60000 ms clock. Both were **capped**;
there were no runner failures or exhausted clocks. Material configuration
save/reload preserved its identity. No strength promotion or final holdout claim
is made. Effects remains experimental and is substantially slower here.

## Validation

```sh
python3 -m unittest tests.test_measurement tests.test_integration -q
python3 -m unittest discover -s tests -q
.scratch/issue-21-tools/bin/python -m mypy omok offline verification/measurement.py --follow-imports=silent
python3 -m compileall -q omok offline verification tests
python3 -I -S verification/offline_engine.py --iterative
python3 -m verification.measurement --output docs/verification/issue-21-measurement.json
```

Seven measurement tests and nine existing integration tests passed. Full suite:
**161 tests passed**, 29.620 seconds. Typecheck passed for 21 source files.
Compile/import/network guard passed with engine and standard-library imports only.
Tests include cold/warm table distinctions, per-turn reset, terminal bypass,
completed plain/sampled equivalence, cancellation inside a sampled material scan,
propagating evaluator errors, shared scan attribution, supplied configurable-player inheritance, loaded configs in both
CLI colors, cumulative clock/replay, and separately labeled node-budget stops.

The Phase 2 evaluator/checkpoint and all existing feature implementations remain
available. There are no changes to rules, candidate protection, ordinary ranking,
search recursion, player inheritance, or the clock formula. Instrumentation may
consume real time; sampled clock results must always be compared with their
recorded instrumentation settings. Frozen candidate preparation is explicitly
outside timed search. Reports are bounded, serial development comparisons, not
a tournament framework. User-owned existing local changes were excluded.

Two-axis [code review and disposition](issue-21-review.md) found no unresolved
Standards or Spec findings.
