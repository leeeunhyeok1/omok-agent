# Issue #36 — frozen optimizer baseline

AI-written by OpenAI Codex. Scope: prerequisite #36 under #35, consuming Phase 4
#24/#34 and master #1. Earlier phase specifications #2/#9/#24, Phase 3 tickets
#16–23, configuration contracts, fixed suites and Phase 3/4 handoffs were read.
This ticket does not implement an optimizer or choose an optimization policy.
No new LLM usage records were created, per user instruction.

The repeatable [baseline collector](../optimizer-baseline.md) freezes the actual
retained material engine, verifies exact restoration, gates measurement on
correctness/reliability and measures bounded serial screening. The engine,
evaluator, supplied bots and configuration values are unchanged.

```sh
python -m verification.optimizer_baseline collect --output .scratch/issue-36-baseline --contention "one agent game worker; other agent experiments stopped; external Windows load uncontrolled"
python -m verification.optimizer_baseline verify --output docs/verification/issue-36
python -m unittest tests.test_optimizer_baseline -v
python -m unittest discover -s tests -v
```

The [frozen basis](issue-36/baseline.json) identity is
`e101b2fc11cd53d21247dcd48fad82e2224333a71961ec58adee35e6d9dcb49f`.
Its exact incumbent entry identity is
`f5f912035b0acbdf4bd9b996c50ce5a3415698449fbb547cd8ebb354acba25c1`,
loading immutable #22 commit `105a8f64edaeb86082425c1fecb12932c06c4367`.
Both compressed archives are retained beside the manifest; each has a checked
digest. The input archive retains source, fixtures, configuration contracts and
complete #22/#34 performance evidence, including the earlier loss traces.
The tactical-suite source identity and every input hash are saved in the basis.

[Exact isolated restoration](issue-36/restoration.json) reproduces the original
material callback rather than replacing it with a configured evaluator. Depth 8,
10,000 nodes, candidate radius 2/cap 24, bounded 4,096-entry table, no profiling
and original time policy are resolved from the restored public player.
The policy retains 100 ms maximum allocation, 2 ms return margin, 0.5 reserve,
0.1 turn and 0.8 soft fractions. Both-color legal fallback, unchanged caller
boards and the known material score are checked under `-I -S -B`. The retained
five preset assets are hashed with compatible engine sources. Verification of
the copied committed evidence also passed.

The frozen pool identity is
`915ff9ad333ec087ccd4cbda851e052e6edd98d342ce9ff668904f75abc36c93`.
Every training/validation/holdout entry preserves source, configuration, runtime,
family and provenance identity. Validation's `synthetic-defensive` already had
Phase 4 development exposure; no new validation games were scheduled. Reserved
`synthetic-space` received **zero game or tactical exposure**. Classmates and
hidden TA agents remain unavailable; pool labels do not establish independent
designs or class rank.

| Executed gate | Tests | Result | Wall seconds |
| --- | ---: | --- | ---: |
| Simulator, differential, public player, iteration, evaluation, effects, search | 64 | Passed | 8.964 |
| Runner, supervision, registry, jobs, matches, resume, synthetic strategies, replay, loss export, concurrency, reports | 106 | Passed | 201.727 |
| Fixed tactics, table, line/potential/capture features, provided integration, measurement, reference, saved baseline artifacts | 85 | Passed | 26.999 |

[Gate logs](issue-36/gates.json) and
[fixed-suite logs](issue-36/fixed-suite-gates.json) preserve commands and actual
results. Existing tests check independent cumulative clocks, remaining-time
rounding, late responses, bounded nonreturning players, crashes/mutations,
subsequent games, stable schedules, stop/resume and known separate qualification/
match/coin cases. No measurement defect was observed and no fitness comparison
was made. The new artifact test first failed because the collector did not exist,
then passed after implementation; changed archives and repeated output paths
are rejected. Expected tactical outcomes were preserved.

The [actual probe](issue-36/probe.json) scheduled six empty-board training games,
two per opponent with exchanged colors: supplied SimplePlayer, capture-focused
and pattern designs. Seed is 20261010, total clock is **5,000 ms per player**,
move cap is **20**, game workers **1**, dispatch budget **60 seconds**.

| Planned | Rule completed | Player failures | Caps | Infrastructure failures | Pending | Wall seconds |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 | 4 | 0 | 2 | 0 | 0 | 14.456 |

Observed slot throughput is **0.415 slots/second** and completed-rule throughput
is **0.277 games/second**, for this capped reduced-clock screening workload
only. Official completed-game throughput is explicitly unavailable; neither
rate is extrapolated to official games per hour. All four completed games were
candidate losses. The two capped games have no result. The single completed
SimplePlayer game was a loss; the other was capped. Retained Phase 3 official
evidence remains **0/8 SimplePlayer strict wins for material and effects**, with
competitive acceptance unmet and effects experimental. Four earlier dense
0.5 ms public calls exceeded their budgets; tiny-clock acceptance remains partial.

Each probe trace passed regular replay and the independent full-board reference.
All player and preflight workers reported reaped; the post-probe Windows process
snapshot found no Python processes. Compressed exact plans, results, reports
and four representative loss exports are under `issue-36/throughput-1/`.
The complete resumable batch remains `.scratch/issue-36-baseline/throughput-1/run`;
compressed exports do not replace its checkpoint.

Measured machine: CPython **3.14.8**, Windows 10 build 19045, AMD Ryzen 3 3300X,
four cores/eight logical processors, **25,700,585,472 bytes visible RAM**,
monotonic QueryPerformanceCounter resolution 0.0000001 seconds. The
[before](issue-36/resource-before.json)/[after](issue-36/resource-after.json)
snapshots observed approximately 12.3/13.0 GiB free physical RAM. These are
point observations, not peak game-process memory measurements. External load,
frequency/temperature and power conditions were uncontrolled. No other agent
game experiments ran during the probe. Retain **one worker** as the portable
baseline and for comparable wall-clock checks; this short probe supplies no
reason to require more workers, GPU, Colab, cloud or continuous availability.
It does not select population size, mutation rate or screening volume.

The final full-suite/typecheck/compile/whitespace commands and results are saved
in [final checks](issue-36/final-checks.json): **255 tests passed in 238.455
seconds**, mypy passed all **35 source files**, bytecode compilation and staged
whitespace checks passed. Independent
[Standards and Spec reviews](issue-36-review.md) found no implementation issues.
Final packaging, grader hardware/runtime, team metadata, untouched final
evaluation and broader competitive strength remain later work.
