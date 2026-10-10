# Issue #38 acceptance evidence

AI-written by OpenAI Codex. Implements **Screen candidates with declared fitness
and failure gates**, consuming the verified Phase 4 tournament APIs. The master
context is #1; #35 supplies the optimizer-run testing seam and screening context.
This ticket implements a bounded screening stage only.

Policy, pool, cohort entries, gates and all plans are saved before dispatch.
Balanced requested jobs, objective units, weights, denominator hierarchy, budgets,
coverage/stopping rules and failure/retry handling are explicit. Validation and
holdout are rejected as opponents and as related role-switched candidates.
Incomplete coverage produces no completed fitness; caps produce no invented draws
or coins. Any candidate player failure in any attempt or failed fixed external
gate vetoes eligibility. Imported retries must obey the saved Phase 4 bound.

The public screening-run tests cover weighting with unequal sample counts, balanced
colors, deterministic duplicate evidence, caps, pending and infrastructure jobs,
unavailable opponents, crash/timeout/mutation/illegal-move vetoes across attempts,
external restoration/score/tactic vetoes, identical repeated attempt delivery,
allowed/excessive infrastructure retries, suspicious censoring, unchanged incumbent,
pool separation, saved-policy tampering and real dispatch/resume.

The [real pilot summary](issue-38/summary.json) records two generated material
candidate configurations and the retained Phase 3 material incumbent. Each passed
six fixed public probes over both colors: low-time fallback/reuse, exactly-five
win and capture defense, with unchanged inputs and valid/absent diagnostic scores.
The caller's saved gate evidence is retained verbatim; these bounded probes do
not replace the existing full correctness/regression suites.

The final serial pilot completed and replayed **12 games** against training-only
`smoke` and `synthetic-aggressive`, both colors for each version. It saved and
resumed one job per plan; all partial candidate states were inconclusive. Final
stage fitness was **0.75 for every version** with four committed games per version
and zero observed player failures. Neither candidate advanced because there was
no favorable gain. The incumbent remained unchanged; no promotion occurred.
Elapsed pilot time was **32.257 seconds**. No validation or holdout was exposed.

The [compressed evidence archive](issue-38/evidence.json.gz) retains every pilot
JSON artifact: proposal policies/parents/actual configurations, fixed gate probes,
screening policy, immutable pool/cohort/plans, checkpoints, results, all attempts,
execution conditions, replay traces, partial/final decisions and summary. Its
`identity` hashes the canonical `artifacts` mapping. Paths are relative to the pilot
root. Reproduction requires the saved compatible source/configuration identities;
replay and reporting can inspect these artifacts without running competitors.

The pilot uses one easy legal opening near an immediate win, a 5000 ms total
clock and move cap 20. It validates complete-stage accounting and resume, **not**
full-league strength, official timing, qualification, generalization or champion
promotion. Local external CPU contention was uncontrolled; the full suite ran
during the pilot, so elapsed times are descriptive rather than controlled benchmarks.

Reproduce the code checks and bounded pilot:

```sh
python -m unittest tests.test_screening -v
python -m unittest discover -s tests -v
python -m mypy omok offline verification/screening.py --follow-imports=silent
python -m compileall -q omok offline verification tests
python -m verification.screening --output .scratch/fresh-screening-pilot
```

The [two-axis review](issue-38-review.md) has no unresolved Standards or Spec
findings; its imported retry-bound finding was reproduced and fixed before commit.
Final command output is retained in [final checks](issue-38/final-checks.json).
No LLM usage records were created, as requested.

Final validation: **274 tests passed**, mypy passed all **37 targeted source
files**, bytecode compilation and staged whitespace checks passed. The full-suite
command took **276.258 seconds**. An earlier suite run overlapped source edits and
failed two existing source-bound concurrency checks; both passed in isolation and
in the final fixed-source run. No runner changes were required.

The compressed archive's canonical identity, all saved screening decisions, and
all 12 game replays were independently rechecked from the committed artifact.
