# Issue #29 — stop and resume serial batches

AI-written by OpenAI Codex. Scope: phase 4 (#24), with master context #1.
The existing complete tournament/persistence seam is reused; engine rules,
evaluation and player time allocation are unchanged.

Implementation adds checksummed atomic checkpoints with OS-backed exclusive
ownership, durable dispatch and result records, stable jobs with fresh attempt IDs,
bounded segment execution and cooperative worker interruption. Committed results
and every prior retry/interruption remain visible. Resume validates source/runtime,
manifest/configuration/policy and replayable result evidence. Each segment records
its execution conditions. See [the operational contract](../experiments.md).

Controlled fixtures cover completed-game restart, active worker cleanup,
uncommitted dispatch recovery, moved outputs, partial temporary writes, truncated
checkpoints/results, duplicate commits, conflicting ownership, bounded infrastructure
retries and genuine player crash/timeout retention. Fault injection also covers
Ctrl+C during durable result commit.

Validation commands:

```powershell
python -m unittest tests.test_batches -v
python -m unittest discover -s tests -v
$env:PYTHONPATH='.scratch/typecheck-tools'
python -m mypy omok offline --follow-imports=silent
python -m compileall -q omok offline tests
git diff --cached --check
```

The mypy directory contains development tooling only. New offline code uses the
standard library; no submission dependency or LLM interaction archive is added.
These controlled checks establish infrastructure behavior, not playing strength.

Final results on the local Python 3.14.3 / Windows environment:

- Full suite: **224 tests passed**, 183.559 seconds.
- All **31** `omok`/`offline` modules passed mypy.
- Bytecode compilation and staged whitespace checks passed.
- Both commit-window fault injections failed before their corrections and passed
  afterward. The final suite includes all 12 new batch regression tests.
- Independent follow-up reviews: **Standards 0; Spec 0** remaining findings.
  See [the review record](issue-29-review.md).

Power-loss durability follows filesystem/platform guarantees; Windows has flushed
file replacement, while POSIX additionally flushes the directory. Graceful stop
cleans up workers; abrupt supervisor termination may leave only the dispatch
record and cannot guarantee worker cleanup. Old output without an authoritative
checkpoint is rejected. Moving a project requires its frozen source bundles and
Git objects, and resumed timing segments retain distinct hardware observations.
