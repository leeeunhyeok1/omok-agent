# Phase 4 acceptance and Phase 5 handoff

AI-written by OpenAI Codex for #34, under Phase 4 #24 and master #1. This
handoff preserves infrastructure decisions; it does not choose fitness,
mutation bounds, promotion rules or a stronger candidate.

The framework keeps the actual Phase 3 material candidate and opt-in effects
configuration distinct. Material remains the default. Phase 3's competitive
acceptance is still unmet: its retained evidence includes eight SimplePlayer
losses for each candidate. Phase 4 acceptance checks infrastructure and makes
no claim of official qualification, hidden TA wins or class rank.

| Contract | Public boundary and documentation |
| --- | --- |
| Registry and frozen pools | `Entry.local`, `Entry.checkpoint`, `PoolSnapshot.freeze`; [registry](registry.md) |
| Manifest and jobs | `ExperimentPlan.resolve`, `save`, `load`, `record`; [experiments](experiments.md) |
| Execution and results | `run_experiment(plan, output=..., workers=1, max_seconds=..., resume=...)`; [bounded runner](runner.md), [experiments](experiments.md) |
| Game and match outcomes | Replayable `omok-game-v4`; [eight-game scoring](matches.md) |
| Persistence and retries | `omok-batch-checkpoint-v1`, owner lock, atomic commits, additive attempts; [checkpoint policy](experiments.md#stop-checkpoint-and-resume-issue-29) |
| Reports and ratings | `report_experiment(plan, raw)`; [denominators, metrics and deferred ratings](reports.md) |
| Loss positions and checked fixtures | `inspect_loss`, `checked_fixture`, `verify_fixture`; [replay and export](replay.md) |
| Frozen synthetic opponents | [strategies, families and limits](synthetic.md) |

The committed [acceptance record](verification/issue-34.md) maps controlled
scenarios to executed tests and lists actual smoke results. Its adjacent
`issue-34/smoke/registry.json.gz` is an immutable registry and complete pool
snapshot, not a recipe that silently substitutes today's source. Each run
preserves the exact plan, raw results, attempts, exposure records, runtime
segments, matchup report and representative candidate loss exports.

Training includes retained versions, supplied bots and local synthetic designs.
Validation contains `synthetic-defensive`, already exposed during Phase 4
development; it is available for periodic checks, excluded from training-purpose
selection. Holdout contains `synthetic-space`, reserved with zero played-game
or tactical exposure. This single simple design provides limited coverage.
Shared source/authorship and related strategy variants limit independence.
Classmates and hidden TA agents are unavailable. Preserve those facts when
selecting a Phase 5 league, rather than calling every labeled family independent.

To consume saved evidence, decompress the registry/plan/results gzip files with
Python's `gzip` module and pass the resulting JSON to `Entry.from_record`,
`PoolSnapshot.from_record`, `ExperimentPlan.from_record` and `report_experiment`.
Reports and replay do not construct agents. To execute again, source/configuration
digests, adapter sources, exact Python runtime and retained Git objects must
match; otherwise register a new version and manifest. Source drift is not resume.

For a new candidate configuration in Phase 5, use the existing
`offline.worker_players.create` search factory: `Entry.local` with
`module='offline.worker_players'`, `factory='create'`, options containing
`name='search'`, resolved `settings`, canonical `evaluation` JSON and optional
`profile_every`. Include `omok`, `offline`, `players` and any configuration assets
in `source_paths`. `offline.measurement.search_settings` supplies the current
resolved settings format; `EvaluationConfig.canonical_json()` supplies evaluation
identity. Each configuration creates a new immutable entry. Do not mutate a
saved candidate or an opponent midway through a batch.

```python
from pathlib import Path
from offline.experiments import ExperimentPlan, run_experiment
from offline.registry import default_catalog
from offline.reports import report_experiment

catalog, pools = default_catalog()  # Explicitly registers the current sources.
plan = ExperimentPlan.resolve(catalog['phase3-material'], pools,
    purpose='training', opponents=['random', 'synthetic-capture'],
    mode='screening', games_per_opponent=2, total_ms=5000, move_cap=20)
plan.save(Path('new-plan.json'))
raw = run_experiment(plan, output=Path('new-run'), workers=1, max_jobs=1,
    max_seconds=30, contention='local development; external load uncontrolled')
raw = run_experiment(plan, output=Path('new-run'), resume=True,
    workers=1, max_seconds=60)
report = report_experiment(plan, raw)
```

Default selection permits training and validation, excluding holdout. Optimizer
fitness must use `purpose='training'`; periodic validation must be explicit.
`purpose='final-evaluation'` is reserved for a later authorized phase. Metadata
freezing/import preflight does not constitute played-game exposure.

Each player has a separate cumulative clock. The authoritative monotonic timer
encloses dispatch through response; player-call time and transport overhead are
separate fields. Remaining public milliseconds are floored. Startup, cleanup and
scheduler queue time are observed separately. Official mode means eight empty-board
games and 60,000 ms per player; screening uses saved reduced budgets. A move cap
is an unresolved experiment stop, never an official draw. No new repetition rule
or per-turn official limit is introduced.

Resume retains committed completed, failed and capped jobs, interrupts uncommitted
attempts, and preserves seeds/colors/configurations with new attempt IDs. The
default retry allowance is zero. Optional bounded infrastructure retries retain
all previous attempts; genuine player failures are never automatically retried
away. Changed workers/hardware produce labeled execution segments. Graceful
stops clean up workers; abrupt owner death cannot guarantee cleanup. Preserve
the checkpoint with its manifest and exports when moving output.

Use one game worker for final wall-clock comparisons, with other experiments
stopped and power/load conditions recorded. The measured one/two-worker screening
probes in the acceptance record inform local development only; they do not select
a universal worker count or imply GPU acceleration. Start development with one
worker, consider two after inspecting measured timing and resource use, and retain
each segment's contention description. No games-per-hour gate is specified.

Ratings and confidence intervals remain explicitly deferred: the pool is small,
paired and related. Reports expose micro, equal-opponent macro, clean and all-attempt
denominators, per-color outcomes, reliability failures, unavailable diagnostics,
duplicate evidence and segment timing. Caps/infrastructure/pending results do not
earn official match coins. The assignment's crash-loss override is separate from
the documented local non-crash execution-forfeit policy.

The fixed tactical/rules/public-player suites remain regression gates. Loss export
contains positions before moves, clocks, recent history and available diagnostics;
automatic categories are hypotheses. Checked exports prove one recorded move's
rule result through an independent oracle, not that it was optimal. Keep
unverified evaluation/horizon explanations out of assertions about best moves.

The passing framework checkpoint is
`5e1c51247b84512682526d9a1b6784512518b344`, restored and tested independently.
The complete Phase 4 acceptance-tool/evidence checkpoint is the commit titled
`Verify Phase 4 acceptance and preserve its handoff (#34)`; locate it with
`git log --format='%H %s' --grep='Verify Phase 4 acceptance and preserve its handoff (#34)'`.

```powershell
$phase04Commit = git log -1 --format='%H' --grep='Verify Phase 4 acceptance and preserve its handoff (#34)'
git worktree add --detach ../omok-phase04 $phase04Commit
Set-Location ../omok-phase04
python -m verification.league_acceptance restore --ref HEAD --output .scratch/new-restoration
python -m verification.league_acceptance gates --output .scratch/new-gates
python -m verification.league_acceptance smoke --output .scratch/new-smoke
```

New code and synthetic strategies are AI-written and attributed accordingly.
Supplied RandomPlayer/SimplePlayer and the recovered Player base remain unchanged;
their provenance is in #7. No classmate strategy or external algorithm code was
incorporated. No new LLM prompt/response records were created, per the user's
instruction. Final disclosure completeness, team suffixes, actual professor
manager/runtime, grading hardware and submission packaging remain later work.
Evolution, tuning, promotion, final holdout execution and packaging require their
subsequent phase specifications.
