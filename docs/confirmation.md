# Fresh training confirmation (#41)

AI-written by OpenAI Codex under Phase 5 (#35), master #1.

`offline.confirmation` consumes an already assessed screening stage or broader
league round. It retains the exact incumbent, selected finalists, training pool,
selection evidence and external gates. A league source retains its earlier rungs
and historical evidence. Confirmation estimates use only the new jobs.

```python
from pathlib import Path
from offline.screening import ScreeningPolicy
from offline.confirmation import ConfirmationPolicy, prepare, run

# Declare actual budgets, variation, margins and evidence minima before dispatch.
policy = ConfirmationPolicy.create(screening=ScreeningPolicy.create(
    opponents={'smoke': 8, 'synthetic-random': 8},
    opponent_weights={'smoke': 1, 'synthetic-random': 1},
    family_weights={'random-smoke': 1, 'frontier-random': 1},
    seed=41001, min_gain=.05).data)
policy.save(Path('confirmation-policy.json'))
prepare(Path('confirmation-policy.json'), selection=Path('broader-league'),
        selection_raw=raw_by_plan_identity, output=Path('confirmation'),
        openings=[[], [[9, 9], [9, 10]]])
partial = run(Path('confirmation'), max_jobs_per_plan=1)
final = run(Path('confirmation'), max_jobs_per_plan=8)
```

The CLI resumes a prepared stage:

```sh
python -m offline.confirmation --output .scratch/confirmation --max-jobs-per-plan 2
python -m verification.confirmation --output .scratch/confirmation-pilot
python -m unittest tests.test_confirmation -q
python -m mypy omok offline --follow-imports=silent
```

`ConfirmationPolicy` saves a validated screening execution policy plus the fixed
decision method, stopping rule, minimum distinct paired blocks per opponent,
minimum families and allowed family/color regressions. Defaults of two blocks,
two families and zero regression are implementation choices, not requirements
invented by the master spec. The underlying policy saves opponent game counts,
weights, clock, cap, draw credit, gain margin, retry bound and color evidence
minimum. The current execution policy uses reduced clocks; official-clock checks
and promotion are later stages. Predeclared openings and seeds are resolved into
every job before dispatch. Policy and manifest files refuse overwrite and verify
content identities on load.

Freshness is checked against every retained selection rung and prior league round
for the same candidate/incumbent identity and opponent, color and effective
variation. Deterministic roles do not earn freshness from changed seeds. If either
role has unsupported seeding, seeds earn no variation credit at all; use fresh
openings instead. Reimported selection results have foreign manifest/job identities
and are rejected. Different legal move orders reaching the same board and side to
move count as the same opening state; move history remains provenance only.
A new clock or cap alone cannot disguise reused samples.

The effect is a paired candidate-minus-incumbent game-point comparison against
each frozen training opponent. Pairing matches the same opening, game seed and
color; Phase 4 intentionally derives candidate role seeds from candidate identity,
so equal game seeds do not promise equal random streams between configurations.
Both colors form one variation block. Known deterministic or unsupported repeats
collapse to a single block. Conflicting outcomes inside one duplicate block make
the decision inconclusive. Every raw job, strict win/loss/draw count, attempt,
failure, color and seed limitation remains visible in the reused execution reports.
`distinct_pairs` counts dependence blocks, not proven independent observations.

Each block contributes once to its opponent/color mean. Declared color weights
combine colors; opponent weights normalize within each family; family weights
combine families. Thus repeated deterministic games and numerous related variants
cannot automatically inflate influence or evidence count. `effect` is this
duplicate-collapsed comparison. The inherited screening `fitness`, `partial_score`
and `gain` remain descriptive raw-job displays and do not determine confirmation
advancement.

Uncertainty uses explicit practical sensitivity: recompute the weighted effect
after omitting each block where full opponent coverage remains, and after omitting
each family where another remains. `sensitivity_range` covers these values and
the full effect. Advancement requires eligible full coverage, the saved minima,
no candidate reliability failure, allowed family/color regressions, and a
strictly positive effect meeting `min_gain` across the sensitivity range. Sparse
evidence or a gain dependent on one block/family is inconclusive. Complete
unfavorable evidence or a reliability/regression veto rejects the finalist.
The incumbent stays retained in every case; advancement only feeds later checks.

This is a conservative descriptive robustness rule, not a confidence interval,
p-value, independent-trial claim or statistical correction that eliminates all
selection noise. It may reject useful candidates. Small family counts, shared
source/rules, unsupported seeding, deterministic opponents and uncontrolled machine
load limit conclusions. Artificial fixture reports explicitly set
`ordinary_strength_evidence: false`; reduced clocks never establish qualification.

Latest results are paired with execution-condition segments. Different declared
hardware/runtime/worker/contention conditions within a comparison make it
inconclusive. Segment IDs, full conditions, metrics and interruptions remain in
the reports. Missing segment assignments block ordinary strength evidence;
controlled artificial fixtures may omit segments. Matching declarations do not
guarantee equal load or reproducible wall-clock behavior.

Stopping is fixed-budget: complete the saved jobs with only the declared bounded
infrastructure retries. Intermediate checks report pending coverage as
inconclusive; they cannot terminate on a favorable score or add games until passing.
The invocation limit bounds attempts per plan, including retries. Candidate
failures, caps, missing opponents and unresolved outcomes retain the screening
reliability/coverage gates. No validation or holdout games are scheduled.

`confirmation.json` is the write-once declaration. Each plan uses Phase 4's durable
authoritative checkpoint. `confirmation-results.json` binds exported raw evidence
to the declaration; `confirmation-report.json` is a regenerable decision report.
All child versions/checkpoints are verified before any dispatch. Saved exported
evidence prevents missing or rolled-back checkpoints from erasing prior work;
all recorded attempts and segment conditions must be retained unchanged, allowing
the normal running-to-interrupted transition. Interrupted jobs
retain attempt history and resume under the same fixed declaration. The existing
Windows durability and abrupt-worker-cleanup limitations still apply.

The bounded verification pilot uses a **controlled artificial selection winner**
to exercise the seam, followed by actual restored engine/configuration instances
in supervised fresh artificial games. It demonstrates execution and retention,
not measured strength improvement, generalization or champion promotion.
