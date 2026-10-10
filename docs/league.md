# Broader training league

AI-written by OpenAI Codex for #40, Phase 5 (#35), master #1.

`offline.league` advances the survivors of recorded screening rungs to a frozen,
balanced broader round. It reuses Phase 4 plans, supervision, durable attempts,
and the screening reliability/coverage accounting. An advance remains an input
to later fresh confirmation and validation; it never promotes a champion.

Prepare through the Python API before executing:

```python
from offline.league import LeaguePolicy, archive_history, prepare

history = archive_history(archive_directory, historical_entries)
policy = LeaguePolicy.create(
    screening=screening_policy.data,
    history_period=2,
    history_slots={entry.identity: slot for entry, slot in historical_schedule},
    max_family_regression=0,
    max_color_regression=0,
    max_matchup_regression=0,
)
policy.save(policy_path)
prepare(policy_path, incumbent, pool_snapshot, history=history,
        rungs=[(screening_directory, screening_raw_results_by_plan_identity)],
        output=round_directory, round_index=round_number,
        previous_rounds=preceding_round_directories, gates=recorded_gates)
```

The saved `screening` policy declares games per opponent, clock, move cap, seed,
draw credit, weights, distinct evidence minimum, gain and cap thresholds, and
bounded infrastructure retries. Include allocations for every historical entry,
the incumbent, and at least two other training design families. All named entries
must be training entries. Requested unavailable external entries remain named,
retain provenance, and block complete fitness. Validation and final holdout remain
protected by the registry, including aliases of related candidate families.

Save each historical identity's slot in `0..history_period-1`. The identity is due
when `round_index % history_period == slot`; both the incumbent and every survivor
play the due entries. Existing periods and slots cannot change or disappear in
later rounds. A later promotion adds an archived entry and a new slot without
removing older entries. Every previous round's durable evidence is required;
incomplete due historical coverage remains an explicit gap and blocks advancement
in later rounds. This deliberately conservative policy requires completing a
missing earlier round and preparing a new later round rather than erasing debt.

`archive_history` appends write-once JSON bundles of the exact Entry configuration,
source bytes and hashes. It verifies all existing artifacts on every call and
returns the full archive snapshot even when called with an empty additions list.
The archive includes source/configuration bytes permanently; execution uses the
existing registry loader and still requires compatible runtime/adapters and, for
checkpoint entries, the retained Git commit. Dependency/runtime limitations and
acknowledgments remain in each Entry. External dependencies are not invented.

Each round snapshots the complete pool, weights and selected historical subset,
schedules a fresh incumbent measurement and saves all plans before dispatch.
Round seeds are the declared base seed plus round index. Added opponents/history
change snapshot/job identity. Scores and regressions are compared only within
that round, never against an older pool's incumbent score. Repeated deterministic
positions remain labeled duplicate evidence, regardless of changed seed.

Every supplied screening rung embeds its stage and raw attempt evidence. The
next rung must evaluate exactly the preceding rung's survivors. The broader
cohort contains exactly the final rung's advances and the same incumbent.
Reports retain every rung's separate score, requested coverage, elimination
reasons, attempts, color cells and matchup evidence.

```sh
python -m offline.league --output .scratch/broader-round --max-jobs-per-plan 2
```

Repeat the command to resume. The bound applies per candidate/opponent plan to
dispatched attempts in that invocation, including infrastructure retries. The
number of plans and per-job clocks are saved, so execution is bounded. Existing
Phase 4 checkpoints remain authoritative. Incompatible versions, corrupt attempts
or deleted previously reported checkpoints are rejected before any dispatch.
`league-results.json` preserves stage plus raw evidence for the next round;
`league-report.json` is its descriptive assessment. `assess(directory, raw)` is
the controlled-result seam and does not dispatch or persist games.

Fitness normalizes colors, opponents within families, then families using the
saved weights. Sample volume does not multiply family influence. Reports expose
family scores, balanced color scores, worst matchup, and each regression against
the newly measured incumbent. Default regression margins are zero; this is an
implementation choice, configurable before execution. Advancement requires
positive gain meeting the saved minimum, complete recognized coverage, distinct
evidence, passing gates, acceptable censoring, and no family/color/matchup
regression beyond the saved margins. A candidate beating the incumbent while
losing to history or diverse styles is not sufficient.

These are descriptive training decisions. No uncertainty significance, hidden TA
success, class percentile, official-clock strength, or final holdout result is
claimed. Supplied/classmate agents are optional and remain externally attributed.

```sh
python -m unittest tests.test_league tests.test_screening -q
python -m mypy omok offline --follow-imports=silent
```
