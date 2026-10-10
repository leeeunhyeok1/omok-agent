# Bounded optimizer runs

AI-written by OpenAI Codex for #39, under Phase 5 (#35).

`offline.optimizer` binds the immutable #37 proposal artifact to an already
prepared #38 training stage. Prepare proposals and the matching stage through
those APIs first; the stage must contain precisely the unique proposed candidates
and the recorded incumbent parent. This command evaluates one fixed cohort.
Advancement is screening only. The recorded survivors and raw results can feed
the [broader training league](league.md); fresh confirmation, promotion, and
adaptive multi-generation scheduling are subsequent work.

```sh
python -m offline.optimizer create --proposals .scratch/population/proposals.json --stage .scratch/stage --output .scratch/optimizer
python -m offline.optimizer run --output .scratch/optimizer --max-games 10 --max-seconds 300 --workers 1 --stop-file .scratch/stop-optimizer
```

Repeat `run` to resume. Limits apply globally to that invocation, across all
candidate/opponent plans. The game bound counts dispatched attempts, including
infrastructure retries, rather than only wins or recognized games. Zero limits
dispatch nothing. Progress prints plan counts and final global counts, plus the
checkpoint location. Create the stop file or use Ctrl+C to stop; remove the file
before resuming. Graceful stop ends dispatch, cancels supervised active games,
commits completed verified results, and leaves interrupted jobs pending with
additive attempt records. Cleanup can extend beyond the dispatch time budget.
Failed/capped results remain committed and contribute to the existing reliability
and completion gates; they are never retried as favorable evidence.

The checksummed `manifest.json` binds the complete population, ancestry, initial
and final proposal RNG state, schema/proposal policy, incumbent, stage assignments,
engine/configuration identities, pool snapshot and screening policy. Resume does
not call proposal generation. The checksummed `optimizer-checkpoint.json` persists
evidence, exposure, pending jobs, eliminated candidates, decisions, incumbent and
history. Each plan directory retains Phase 4's authoritative checksummed attempt
checkpoint, stable job identities, owner lock, and atomic durable commits. A root
owner lock prevents concurrent optimizer owners. Do not execute child batches
independently while an optimizer run owns the directory.

Child checkpoints are the authority for game attempts. If the owner dies between
a child commit and the optimizer commit, resume reconciles the durable child
evidence before dispatch. All children and registered versions are validated
before any new work. Missing/truncated/conflicting authoritative artifacts, policy
changes, incompatible registered source/configuration/runtime, or inconsistent
committed decisions are rejected. Disposable reports can be regenerated, and a
result-commit/export window does not repeat a game. A batch interrupted during
initialization before a durable attempt can be initialized again safely.

The deterministic policy waits for the whole saved cohort to exhaust requested
jobs and bounded retries, then commits one decision identified by stage identity,
with candidates sorted by identity. Caps/missing gates/unresolved evidence produce
inconclusive decisions. Duplicate delivery is idempotent at the game commit seam.
Completion order and worker count never drive proposals or selection. Real
wall-clock games can nevertheless differ with machine load; this policy promises
logical determinism for equal evidence, not identical timing outcomes.

Execution-condition segments label hardware/runtime/worker/contention changes
and preserve earlier provenance. Moving the entire run directory to compatible
source/runtime installations preserves logical identity. The retained engine
commits must be locally available. Source or runtime changes require a new run.

Incumbent/history stay immutable. A committed decision records `promotion: false`
and the retained incumbent, providing an unambiguous input to the later promotion
transaction. No candidate becomes champion based on screening.

Abrupt owner death releases OS owner locks, but cannot guarantee orderly worker
or descendant cleanup. Running attempts are marked interrupted on resume and
receive new IDs; uncommitted work can repeat. Inspect and terminate orphan workers
before restart, especially on Windows. Reports and checkpoints preserve known
interruption evidence but cannot reconstruct uncommitted player calls or claim
zero exposure after abrupt death. Atomic replacement uses file fsync; directory
fsync is used where supported, with the existing Windows durability limitation.

```sh
python -m unittest tests.test_optimizer tests.test_batches -q
python -m mypy omok offline --follow-imports=silent
```
