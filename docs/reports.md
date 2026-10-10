# Saved matchup reports

Issue #33 adds the standard-library `offline.reports.report_experiment(plan, raw)`
API and a CLI that reads persisted evidence without running players:

```sh
python -m offline.experiment_cli report --plan run/manifest.json --results run/results.json --output matchup-report.json
```

The output is `omok-matchup-report-v1`. The CLI creates a new file and refuses to
overwrite it. Reports rebuild scoring from the saved plan and replay-validate
traces; cached counts and match scores are not trusted. Foreign, duplicate or
misassigned job results are rejected. Invalid traces become explicit infrastructure
evidence with validation errors and supply no timing or search measurements.

`jobs` counts each planned slot once, using its latest committed result. It includes
planned/completed/failed/capped/infrastructure-failed/pending counts and candidate
wins/losses/draws under the separately recorded local execution-forfeit policy.
`clean_games` includes only validated, rules-completed games. Both views include
black/white counts. `matches` preserves raw rules scores, recognized outcomes,
qualification, crash overrides, unresolved flags and coins from the existing
[eight-game scoring policy](matches.md). Partial matches and caps receive no coins.
Development comparisons and official-format interpretations remain separately labeled.

`all_attempts` retains every unique attempt, including superseded infrastructure
failures, with separate committed/interrupted/running counts. Interrupted and running
attempts have no recognized game result. Identical repeated attempt deliveries are
counted once and disclosed; conflicting deliveries, assignments or latest-result
disagreements are rejected. Older results without attempt history explicitly say
`history_available: false`; their latest results are the available attempt evidence.
No failure is overwritten or retried by reporting.

Every rate has a numerator, denominator and value; an empty denominator yields null.
Win rates divide strict recognized wins by recognized wins + losses + draws, excluding
unresolved/capped/pending jobs. Failure rates divide failed + infrastructure-failed
records by observed records; completion rates divide rules-completed records by all
slots (by committed records in the attempt view). Failure violations by role may
overlap within a game. Crash counts are numbers of affected games/attempts, not unique
players. Micro win rate pools recognized games; equal-opponent macro win rate averages
the available version-level opponent rates equally. Unavailable opponents are counted
and excluded from that macro denominator. The corresponding clean summaries use only
rules-completed games. None of these denominators imply independent trials.

`opponents` exposes immutable versions, source origins, design families, pools,
all-attempt and clean views, and game/timing measurements including by candidate color.
`weak_matchups` sorts recognized win rate ascending, with unavailable results last;
it also exposes color scores and denominators rather than claiming statistical weakness.
`coverage` counts requested and observed jobs per family/origin/pool and lists version
identities, planned deterministic duplicate groups and seed limitations. Related versions
are not independent designs. Duplicate groups are warnings, not automatic reweighting.
`ordinary_strength_evidence` is false for artificial fixture schedules: their outcomes
verify accounting and must not be interpreted as ordinary tournament strength.

`metrics` describes latest jobs and all committed attempts separately. Game length is
the number of applied moves after the recorded opening. Turn timing uses each returned
event once, including failed calls; applied and failure events do not count again.
Authoritative caller-envelope elapsed time, optional player-call time and overhead
remain separate. End-of-record clocks include failures/caps; unlimited clocks are null.
Numeric search diagnostics, including nested evaluation profiling fields, are summarized
by field rather than substituting zero. Unsupported/missing values remain null with
sample and missing counts. Each distribution includes mean, min, max and nearest-rank
p50/p95/p99 (`ceil(p*n)`, one-based). Each field uses its own available sample denominator;
there is no fabricated precision or inferred search work for missing fields.

`execution_segments` retains complete recorded runtime/hardware/worker/contention and
changed-condition evidence with separate all-attempt metrics. Unassigned older evidence
is reported separately. Overall timing distributions are descriptive mixtures, **not**
controlled hardware comparisons; inspect segment metrics before interpreting timing.

Ratings are explicitly deferred: a calibrated independent opponent pool is not established,
and descriptive reports satisfy this phase. No initialization/update/order/outcome unit
is invented for a rating that is not computed. Caps and unresolved matches never become
rating draws. Uncertainty intervals are also unavailable: small, paired, deterministic
duplicates and shared-source opponents violate an assumed independent Bernoulli sample.
Reports do not infer actual class rank, qualification against hidden agents, statistical
promotion thresholds or generalization to an unseen class population.
