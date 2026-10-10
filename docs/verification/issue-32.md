# Issue #32 — controlled concurrent resumable batches

AI-written by OpenAI Codex. Phase 4 (#24), master context #1. The existing complete
runner/tournament boundary supplies the agreed test seam. No LLM usage archive added.

Bounded supervisor threads reuse fresh per-game player subprocesses. Saved schedules
remain immutable across serial/parallel execution. One owner commits validated results;
stop, time bounds and owner exceptions cancel all active games before checkpointing.
Attempts reject late/foreign/superseded arrivals. Segment records expose actual worker
settings, hardware/runtime/contention changes, completion order and scheduling time.
See [the operational contract](../experiments.md#controlled-concurrency-issue-32).

Controlled tests cover out-of-order completion with stable game identities/seeds/colors/
configurations, independent clocks, persistent player turn state, bounded dispatch,
player exits without retries, supervisor creation faults, owner reporting failure,
multi-game stop/resume, late arrivals, hardware changes and parallel time-bound cleanup.
Existing checkpoint tests retain duplicate, truncated checkpoint and commit-window
interrupt coverage. These checks establish infrastructure behavior, not playing strength.

Validation commands:

```powershell
python -m unittest tests.test_concurrency tests.test_batches -v
$env:PYTHONPATH='.scratch/typecheck-tools'
python -m mypy omok offline --follow-imports=silent
python -m unittest discover -s tests -v
python -m compileall -q omok offline tests
git diff --check
```

Final wall-clock comparisons require serial execution and documented external-load
controls. Parallel official-budget games remain contention-sensitive. Graceful cleanup
is bounded by the existing supervisor policies; abrupt owner termination cannot promise
cleanup. Runtime and frozen source checks still apply on resume; hardware changes are
explicit segment evidence, while incompatible Python/source versions remain rejected.

CLI evidence: [execution segments](issue-32-execution.json) record a four-slot,
zero-move-cap screening fixture, first dispatched with two workers and a three-attempt
bound, then resumed with one worker. All four slots were retained, each committed once,
and the worker change was labeled in the second segment. Concurrent full-suite load
is declared in the contention description; this fixture measures infrastructure only.

Both independent review axes have **0 remaining findings** after moving shutdown
state reconciliation into `Checkpoint`; see [the review record](issue-32-review.md).

Final validation on Python **3.14.8**, Windows, 8 logical CPUs, 25,700,585,472 bytes RAM:

- Full suite after the review correction: **246 tests passed**, 231.478 seconds.
- All **33** `omok`/`offline` modules passed mypy.
- Bytecode compilation and staged whitespace checks passed.
- Focused commit-window recovery and owner-failure tests: **3 passed**.
- Eight new concurrency checks passed as part of the final suite.
- CLI bounded dispatch and resume with changed worker count passed.
- Standards **0** and Spec **0** remaining findings.
