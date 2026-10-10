# Validation and practical official-clock eligibility (#42)

AI-written by OpenAI Codex under Phase 5 (#35), master #1.

`offline.promotion` saves the eligibility policy and complete paired schedule before
dispatch. It checks fresh-confirmation finalists, or audits the retained incumbent.
It reports `eligible`, `reject`, or `inconclusive`; it never changes the champion.
The separate promotion transaction remains later Phase 5 work.

```python
from pathlib import Path
from offline.promotion import PromotionPolicy, prepare, run

PromotionPolicy.create(validation={'synthetic-defensive': 4},
    official_opponents=['smoke']).save(Path('promotion-policy.json'))
prepare(Path('promotion-policy.json'), incumbent, frozen_pool, output=Path('checks'),
    confirmation=Path('fresh-confirmation'), confirmation_raw=committed_raw,
    prior_exposures=[{'source': 'phase-04-report', 'details': 'Already played; counts in archived report'}],
    openings=[[], [[9, 9], [9, 10]]])
report = run(Path('checks'), max_jobs_per_plan=8, conditions={
    'power': 'observed AC/battery and power setting, including unknowns',
    'load': 'observed machine load and stopped experiments',
    'other_experiments_stopped': True})
```

Omit confirmation to audit only the incumbent; supply the saved restoration,
score and mandatory-tactic gate evidence. Missing or inconclusive gates prevent
eligibility. Finalists retain their confirmed gates, incumbent, full pool snapshot,
source selection and fresh training evidence. Confirmation must originate in a
broader league to support promotion eligibility. At least two training families
outside incumbent/history, all recorded historical versions, balanced colors,
and at least sixteen recognized incumbent-comparison games are required.
One eight-game head-to-head win, rating or aggregate score cannot satisfy this.

The policy declares validation cadence as every selected finalist before
eligibility, plus the incumbent at each check. Validation budgets, coverage,
variation, seed, caps, retries and every promotion margin are saved before jobs.
Validation game points remain check evidence and never enter candidate fitness or
ordinary mutation selection. Coverage must complete in both colors. The existing
paired-effect accounting collapses deterministic/unsupported-seed duplicates and
requires two distinct paired blocks per validation opponent by default.
Different declared execution conditions and conflicting duplicates are inconclusive.

The initial numeric choices follow the existing screening/confirmation scale and
the bounded budget; they are explicit conservative implementation choices, not
preapproved thresholds or a claim of statistical significance:

| Criterion | Initial saved value |
| --- | --- |
| Fresh confirmation sensitivity lower bound and broader league gain | At least 0.05 game points |
| Incumbent comparison | At least 16 games, game-point score at least 0.55 |
| Validation, family, worst matchup, historical and per-color allowable regression | 0.05 game points |
| Rules/mandatory tactics/score/restoration and reproduced reliability | All gates pass; zero observed candidate failures in retained attempts |
| Validation and practical official completion | 100% requested recognized validation games; 100% official games complete under the rules |
| Practical clock reserve | At least 2 ms remaining, consistent with the supported player's return-margin floor |
| Official residual-clock regression relative to incumbent | At most 1,000 ms (1/60 of the official clock) |

Family comparisons respect saved opponent weights within each family. Color
regressions are checked for each matchup, which is stricter than only checking
league-wide color averages. Training regressions outside these margins reject even
when an earlier, looser selection policy allowed advancement. The fresh-confirmation
robustness method and its independence limitations remain applicable. Residual clock
differences also depend on game length and opponent behavior: this conservative
timing veto can reject useful candidates and needs investigation, not automatic
interpretation as a timing bug. Inadequate evidence retains the incumbent.

Every official plan has exactly eight empty-board games, alternating colors,
60,000 ms per player and cumulative dispatch-through-response clocks. Execution
uses one game worker and requires stopping other experiments and recording actual
power/load conditions. CPU, runtime, memory and execution segments are also saved.
Matching declarations are required across candidate/incumbent jobs but cannot prove
machine isolation. A fixed 10,000-move safety ceiling bounds pathological capture
games; reaching it is capped, incomplete evidence and never an official result.
Reduced-clock validation, artificial fixtures and caps cannot establish practical
official evidence. Completed checks inspect returned legal moves, total-clock
reserves, setup/configuration compatibility, diagnostics and failures. The incumbent
pilot is a timing/reliability audit against a smoke design, not general strength or
qualification evidence.

Optimizer declarations forbid final-evaluation purposes and holdout jobs. Candidate
identity and related origin/family membership cannot bypass a reserved pool by
switching roles or display names. Training members can be candidates in explicit
validation checks; the generic Phase 4 final-evaluation API remains available for
the later freeze workflow, outside the optimizer. Saved plans are rebuilt and
compared on load, so rehashing a forbidden optimizer plan does not authorize it.

`prior_exposures` records known earlier evidence with source pointers and honest
unknown counts. Phase 4 already exercised validation. Every check logs results,
attempt exposure and segments; `previous_checks` embeds earlier declarations and
results, retaining candidate failures even after a successful recheck. Repeated
validation is always described as development-influenced, with limited design
independence, never as untouched final evidence. Persist previous check paths when
continuing a validation history; hashes detect alteration, not omitted external runs.

Write-once `eligibility.json` contains the declaration. Child checkpoints are
authoritative and resume under the same jobs and bounded infrastructure retries.
The identity-bound `eligibility-results.json` exports raw evidence after each
completed plan; `eligibility-report.json` can be regenerated. Missing or rolled-back
child attempts/conditions cannot erase earlier exported evidence. Abrupt process
death has the existing Windows checkpoint/worker-cleanup limitations.

```sh
python -m offline.promotion --output .scratch/checks --conditions conditions.json --max-jobs-per-plan 2
python -m verification.promotion --output .scratch/eligibility-pilot --power "observed power policy" --load "observed load; other experiments stopped"
python -m unittest tests.test_promotion -q
python -m mypy omok offline --follow-imports=silent
```

Controlled tests supply replay-valid legal traces to demonstrate possible eligibility
and veto/inconclusive decisions. Those fabricated outcomes/clock observations are
decision-mechanics evidence; actual restored-player execution is recorded separately.
