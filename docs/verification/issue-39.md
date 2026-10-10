# Issue #39 — exact optimizer stop/resume

AI-written by OpenAI Codex, under #35 and master #1 (Phase 5).

Implemented `offline.optimizer.create/run` and the bounded command documented in
[the optimizer contract](../optimizer.md). One immutable proposed cohort is
evaluated through saved Phase 4 batches; no proposal regeneration or automatic
promotion occurs on restart.

Acceptance mapping:

| Requirement | Evidence |
| --- | --- |
| Complete search identities, population/ancestry/RNG, stage, evidence, pending/eliminated state, incumbent/history/exposure/decisions | Checksummed embedded proposal+stage manifest, root run checkpoint and durable per-plan attempt checkpoints |
| Global time/game bounds, progress, checkpoint, stop/resume | CLI `run` requires both limits; tests for one-game and zero-time bounds and explicit stop |
| Phase 4 stable IDs, locking, atomic commits, additive attempts | Direct reuse of owner/Checkpoint/run_experiment; repeat-resume test retains four attempts |
| Compatibility and corrupt-artifact rejection | Source/policy/root/child corruption tests, including deletion of previously initialized checkpoints before dispatch |
| Commit/export interruption, duplicate delivery, reordered completion | Public optimizer-run fixtures inject owner interruption and duplicate/reordered execution at the Phase 4 execution boundary; proposals and logical decisions match |
| Completed/failed/capped evidence retained, failures visible | Existing batch/screening reliability gates remain active; shutdown now commits completed verified futures instead of discarding them |
| Incumbent/history and promotion integration | Stable incumbent/history, single stage-identified committed decision, explicit `promotion: false` |

The real-engine pilot is retained in
[pilot-summary.json](issue-39/pilot-summary.json) and the compressed root
checkpoint `issue-39/pilot-checkpoint.json.gz`. It uses one seeded material
mutation, the retained engine, a controlled training opponent and a fixed
one-ply-capped fixture. First invocation: 1 committed job, 3 pending, 1 attempt.
Resume with two workers: 4 committed jobs, 0 pending, 4 attempts. Another resume:
the same four attempts, evidence, population and decisions. External gates are
absent, so candidates remain inconclusive; this is recovery evidence, not a
strength or promotion claim.

Nine optimizer tests cover bounded dispatch, graceful stop, commit/export
recovery, source and policy mismatch, corrupt and missing authoritative artifacts,
duplicate delivery, completion-order independence and idempotent decisions.
Two-axis review found and resolved root/child deletion recovery defects; see
[the review](issue-39-review.md).

Commands:

```sh
python -m unittest tests.test_optimizer tests.test_batches -q
python -m unittest discover -s tests -q
python -m mypy omok offline --follow-imports=silent
python -m offline.optimizer --help
git diff --check
```

Final settled-source validation: **283 tests passed** in 345.435 seconds;
typechecking passed all **37 source files**. The nine focused optimizer tests,
CLI help and whitespace checks also passed. The full suite was restarted after
implementation edits so registered-source identity checks used a stable tree.

Abrupt owner death cannot guarantee descendant cleanup or preservation of
uncommitted player calls. Running attempts are retained as interrupted and can
be restarted with new attempt IDs. Inspect orphan processes before resuming.
Compatible cross-machine/worker changes create labeled condition segments;
different source/runtime requires a new run. A dispatch time budget can be
exceeded by orderly supervision cleanup and durable export work.
