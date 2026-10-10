# Declared training screening (#38)

AI-written by OpenAI Codex. This bounded ticket consumes the Phase 4 execution,
results and reporting APIs. It screens an existing cohort; proposal generation,
broader confirmation, validation and champion promotion remain separate work.

`offline.screening.ScreeningPolicy` is immutable canonical JSON with a content
identity. Save it to a new file before `prepare` or dispatch. `prepare` reads that
saved file and writes a new `stage/stage.json` containing the exact policy,
incumbent/candidate entries, complete pool snapshot, requested opponents (including
unavailable versions), fixed external gates, and every resolved experiment plan.
It rejects validation/holdout opponents and related versions switched into the
candidate role. Policy/stage creation refuses overwrite; loading verifies identities
and reconstructs the plans and their common settings. There is no fitness purpose
other than training.

```python
from pathlib import Path
from offline.screening import ScreeningPolicy, prepare, run, assess

# incumbent/candidates: immutable registry Entries, e.g. unique #37 proposals.
# snapshot: frozen PoolSnapshot; gates: checks for each Entry identity.
policy = ScreeningPolicy.create(
    opponents={'smoke': 4, 'synthetic-aggressive': 8},
    opponent_weights={'smoke': 1, 'synthetic-aggressive': 1},
    family_weights={'random-smoke': 1, 'line-pattern': 1})
policy.save(Path('policy.json'))
prepare(Path('policy.json'), incumbent, candidates, snapshot,
        output=Path('stage'), gates=gates)
partial = run(Path('stage'), max_jobs_per_plan=1)
final = run(Path('stage'))  # resumes the same jobs and bounded retry policy
```

The predeclared objective is weighted game points: win 1, loss 0, draw
`draw_credit` (default 0.5). Each opponent/color cell divides points by recognized
games, including the Phase 4 documented execution forfeits. Color means use the
positive declared color weights (default equal). Within a family, opponent means
use declared opponent weights; family means then use declared family weights.
Thus unequal sample counts and multiple related versions do not automatically
receive more importance. Every cell exposes numerator, denominator, value,
distinct evidence, and planned/completed/failed/capped/infrastructure/pending counts.
These units are separate from strict wins, qualification, match coins and ratings.

The policy also saves the stage subset and balanced per-opponent game budgets,
seed, total clock, move cap, retry bound, draw treatment, evidence minimum,
gain threshold, completion policy and stopping/elimination rules. Defaults are
implementation choices: 5000 ms per player, move cap 1000, one infrastructure
retry (configurable 0..3), minimum two distinct observations per opponent/color,
gain at least 0.05 and strictly positive, and zero allowed excess cap rate over the
incumbent. Each color gets the same number of requested jobs, even when different
opponents receive different counts. Identical Phase 4 deterministic duplicate
groups count once toward the distinct-evidence requirement. Reports retain the
duplicate labels and avoid independence/confidence claims.

The fixed stage dispatches its saved jobs without outcome-driven resampling.
`run` uses serial supervised batches and the existing exclusive owner/checkpoints;
`max_jobs_per_plan` bounds attempts for **each** saved opponent/candidate plan.
Resume preserves results and attempts, including interruptions and changed runtime
conditions. Player failures are never eligible for infrastructure retries. The
fixed total job/clock/cap budgets bound work; no background automation is started.
Candidates with a saved failed external gate are skipped and fail screening.

`assess(stage_path, raw_by_manifest_identity)` supports controlled Phase 4 fixtures
or saved results. Each result set must belong to its exact saved plan. It uses
`report_experiment`, which replay-validates results and all committed attempts,
deduplicates repeated deliveries and rejects conflicting/foreign evidence. Keep
the raw result/attempt artifacts alongside the report, as `run` does automatically.

Every candidate player crash/exit, timeout, illegal move, input mutation or protocol
failure observed in any validated attempt vetoes eligibility. Cleanup errors retain
prior player failures. An earlier failure cannot be erased by supplying a later win.
Vetoes retain game/attempt identity, failure detail and the full failing result.
Reports expose committed-attempt and candidate-failure sample sizes; zero observed
failures is not a guarantee. Infrastructure failures stay separate and unresolved;
a successful allowed infrastructure retry retains its original evidence.
Imported attempt histories that exceed the saved retry bound or retry an already
resolved job are ineligible with `invalid_retry_history`; their evidence remains
visible. Repeated identical attempt deliveries count once rather than as retries.

External fixed gates supplement game observations for restoration defects, invalid
scores and mandatory-tactic regressions. Supply `gates[entry.identity]` containing
exactly one record per check (`restoration`, `invalid_score`, `mandatory_tactic`):
`check`, `status` (`pass`, `fail`, `inconclusive`), positive `samples`, and nonempty
`evidence` (prefer embedded probe results and fixed suite/configuration identities).
These are results of the caller's correctness checks, not assertions invented by
screening. They are bound to the immutable candidate and saved before dispatch.
A failed check vetoes; missing/inconclusive checks block advancement. Fixed expected
outcomes must never be rewritten for an unsuccessful candidate.

100% requested recognized coverage and available opponents are required for a
completed **stage-local** fitness. Pending/capped/infrastructure jobs and unavailable
opponents make `fitness` null. `partial_score` is a descriptive available-cell
display, never a completed league score. Caps receive no invented draw, points or
coins. Excess caps over the incumbent add `suspicious_censoring`. Minimum distinct
evidence and passed gates apply to both candidates and the incumbent.

`advance` means sufficient favorable evidence for the next training stage;
`fail` means a reliability veto or insufficient favorable gain in a completed
eligible comparison; `inconclusive` means insufficient coverage, evidence, gates,
or an ineligible incumbent comparison. Every result carries reasons. The incumbent
gets `retain` when its stage evidence is eligible and **always** stays the champion:
the report explicitly sets `promotion: false`. Advancement is not statistical
proof or promotion; fresh broader training confirmation, validation and official
wall-clock checks remain required in later tickets.

```sh
python -m unittest tests.test_screening -v
python -m verification.screening --output .scratch/screening-pilot
```

The pilot proposes two material candidates, saves six public gate probes per
version (both colors, interrupted fallback reuse, exact-five win, capture defense),
saves the policy/cohort, runs one job per plan, resumes, replay-validates all games,
and emits a compressed archive of every JSON artifact. It uses a legal opening
near an immediate win against two training designs to bound cost. Its small easy
subset is intentionally labeled and establishes no ordinary full-league strength.
No validation or final holdout games are scheduled.
