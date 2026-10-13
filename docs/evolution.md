# Autonomous repeated optimization (#45)

Python 3.14.3 and the standard library run this optimizer locally. Retain the
repository, its Git engine checkpoints and the entire run directory. No GPU,
network service or scheduler is needed. `omok/` is engine code; `configs/` and
candidate declarations are parameters; the run directory contains opponent
snapshots, checkpoints, evidence and exports. Exports are development artifacts,
not the final submission package.

Initialize once, then launch a bounded invocation:

```sh
python3 -m offline.optimizer initialize --output .scratch/my-evolution
nice -n 10 python3 -m offline.optimizer run --output .scratch/my-evolution \
  --max-games 100 --max-seconds 1800 --max-rounds 2 --workers 1 \
  --stop-file .scratch/my-evolution/STOP --contention 'one game worker; external desktop load uncontrolled'
```

Initialization saves the complete resolved policy, pool, source identities,
incumbent archive, tactical-suite identity and proposal RNG before generating
anything. The starter has two material-coefficient mutations per round, incumbent
elitism plus one training survivor parent, one worker, two training families,
balanced colors, paired seed/opening variation, fresh confirmation openings,
validation every second round (also for confirmed finalists), historical rotation,
explicit margins, bounded proposal/retry handling and stage clocks/caps. Inspect
`evolution.json` for all values. For search/time mutations, create a complete policy
JSON using `starter_policy` and `ProposalPolicy.for_parent(...,
batch='search-time', groups=['time'])`, then pass `initialize --policy FILE`.
Only supported implemented settings change; the optimizer never rewrites code.
The saved policy deduplicates within a population and against its selected parents.
A later round may revisit a configuration using new round seeds; it records that
configuration identity and does not invent another independent genotype.

The small one-worker choice follows the measured #36 baseline (0.415 dispatched
slots/s, 0.277 rule-completed games/s, reduced-clock capped screening on its recorded
machine). That measurement is not an official-clock throughput promise. The #45
pilot measured 0.374 attempts/s on this Intel i5/8 GiB Mac under its small
near-win-opening workload, including gates and persistence; begin small and inspect
those timings before increasing budgets. `nice` is optional on Unix and is omitted
on Windows. One game worker runs two isolated player processes and a controller.

Every invocation shares its game-attempt and wall-time dispatch bounds across
rounds, training, validation, official games and infrastructure retries. A round
limit counts newly committed rounds in that invocation, including a pending round
that finishes. Exhausting a budget pauses the pending stage. Gate probes use the
remaining wall-time budget. A stop file observed during an already-running gate
is handled when that gate finishes, at most its saved timeout (30s in the starter). Plan verification, atomic persistence and supervised
cleanup can extend beyond dispatch limits: default player cleanup allows up to two
500ms process waits per player plus bounded output-thread joins; startup/callback
checks poll cancellation every 50ms. File verification/persistence overhead varies
with accumulated evidence and local disk speed. These are dispatch bounds, not a
hard process-kill deadline.

Stop and resume the same logical run:

```sh
touch .scratch/my-evolution/STOP
# The running command sees this file; Ctrl+C also requests graceful cleanup.
rm .scratch/my-evolution/STOP
nice -n 10 python3 -m offline.optimizer run --output .scratch/my-evolution \
  --max-games 100 --max-seconds 1800 --max-rounds 2 --workers 1 \
  --stop-file .scratch/my-evolution/STOP --contention 'one game worker; external desktop load uncontrolled'
python3 -m offline.optimizer status --output .scratch/my-evolution
python3 -m offline.optimizer review --output .scratch/my-evolution --round 0
python3 -m offline.optimizer export --output .scratch/my-evolution \
  --destination .scratch/champion-export.json
```

Before official-clock dispatch, stop other experiments, observe actual power/load,
and record them in a JSON file. Supply that file on the run/resume command:

```json
{"power":"actual observed AC/battery and power settings, including unknowns","load":"actual observed load and other applications","other_experiments_stopped":true}
```

```sh
python3 -m offline.optimizer run --output .scratch/my-evolution \
  --max-games 100 --max-seconds 1800 --max-rounds 1 --workers 1 \
  --conditions .scratch/actual-conditions.json --contention 'actual observed load'
```

The text above describes fields to fill from observation; it is not measured
conditions. Missing conditions pause at the pending official stage, retaining
already committed validation. Official games always use one worker and the
existing cumulative 60,000ms clocks. A larger training worker override is recorded
as provenance and does not make timing evidence comparable to serial play.

Rounds automatically persist immutable population/ancestry and gates, screen,
evaluate survivors plus the incumbent/history, confirm finalists on fresh training
jobs, perform due checks and attempt the existing atomic promotion transaction.
Training evidence alone ranks extra parents; validation values are excluded from
ordinary fitness. Qualification may change the incumbent elite. Final holdout is
forbidden in every candidate/opponent/role path. Failed, capped and missing games
remain explicit evidence. No survivors or rejected improvements retain the
incumbent and continue. Empty proposals stop; partial populations are recorded.
Unresolved due historical coverage stops after recording the decision.

`evolution-checkpoint.json` saves the round/stage, RNG, parents, gates, evidence,
reviews and decisions. Child plan checkpoints own attempts, pending jobs and
exposure. Resume reconciles child commits before dispatch; immutable directory
publication handles preparation interrupted before controller commit. A committed
promotion transaction is idempotent, and the next round uses saved parent selection.
Source, suite, policy, checkpoint or runtime conflicts reject dispatch. OS owner
locks prevent concurrent owners; do not run child plans independently. Abrupt
process death can leave orphan workers and uncommitted exposure, as described in
[the checkpoint contract](optimizer.md). Logical decisions are reproducible for
equal evidence; real clock outcomes depend on machine conditions.

Status gives rounds and retention reasons; per-round `review.json`, stage reports,
plans/results, raw attempts, execution segments and `champions/` give the evidence.
The old `create --proposals ... --stage ...` prepared-cohort API remains available.
It does not perform repeated evolution. See the [Phase 5 handoff](phase-05-handoff.md)
for actual results and limitations.
