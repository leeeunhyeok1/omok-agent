# Issue #34 — Phase 4 acceptance

AI-written by OpenAI Codex. Scope: #34 under Phase 4 #24 and master #1. The
existing complete runner/tournament seam was agreed by the specifications;
existing behavior tests supply the regression and controlled scenario gates.
No LLM usage archive was added. Engine, evaluator, supplied sources, search
configuration and time policy were unchanged.

Framework acceptance passes. This is infrastructure evidence, not competitive
acceptance or authorization to tune. Material remains the default; effects-v1
remains experimental. See the [Phase 5 handoff](../phase-04-handoff.md).

| Controlled requirement | Executed acceptance coverage |
| --- | --- |
| Rules, ownership, cancellation, search, evaluation | 64 prerequisite tests: simulator, differential, player, iterative, evaluation, threat effects, search |
| Eight slots, four per color, stable IDs/seeds/openings | `tests.test_experiments`, `tests.test_concurrency` |
| Stop/resume, commit-window interruption, idempotence, corrupt/truncated output and source drift | `tests.test_batches`, `tests.test_experiments` |
| Active player's cumulative clock, floor/precision, zero/exhaustion, late response, startup/queue separation | `tests.test_supervised`, `tests.test_concurrency` |
| Loop/sleep/raise/exit/malformed/mutation/flood, subsequent game, bounded setup and cleanup | `tests.test_supervised`, `tests.test_registry` |
| Per-game fresh state, per-turn persistent state, same-module isolation and seeds | `tests.test_supervised`, `tests.test_registry`, `tests.test_concurrency` |
| Supervisor faults and owner/reporting errors remain infrastructure facts | `tests.test_supervised`, `tests.test_concurrency` |
| All five known scoreboards; crash override, opponent crash, both-crash ambiguity, missing/capped slots, coins | `tests.test_matches` |
| Normal/capture-induced opponent win/simultaneous draw, old formats, invalid replay, bounded pre-move exports and checked expectations | `tests.test_replay`, `tests.test_loss_inspection`, `tests.test_supervised` |
| Holdout defaults, explicit development rejection, related families and role-switch protection | `tests.test_registry`, `tests.test_experiments`, real registry selection check |
| Per-color counts, clean/latest/all-attempt denominators, runtime segments, missing diagnostics, duplicates, macro/micro | `tests.test_reports` |
| Independent synthetic behaviors and reserved design | `tests.test_synthetic` |

All **106 framework tests passed in 209.031 seconds** after the 64 prerequisites
passed in 8.884 seconds. [Full commands and per-test logs](issue-34/gates.json)
preserve results rather than merely asserting a checklist. Existing #25–33
evidence retains additional controlled artifacts. The final full-suite and
typecheck/compile results are recorded in `issue-34/final-checks.json`.
The final suite passed **253 tests in 239.645 seconds**; mypy passed all **35**
engine, offline and acceptance-tool modules. Bytecode compilation and whitespace
checks passed. No new tests were needed for this evidence/documentation work;
the agreed seam's existing behavior tests remained fixed throughout validation.

```powershell
python -m verification.league_acceptance gates --output .scratch/issue-34-gates
python -m verification.league_acceptance restore --ref 5e1c51247b84512682526d9a1b6784512518b344 --output .scratch/issue-34-restore
python -m verification.checkpoint --phase3-ref HEAD --output .scratch/issue-34-engine-restoration.json
python -m verification.league_acceptance smoke --output .scratch/issue-34-smoke
python -m unittest discover -s tests -v
$env:PYTHONPATH='.scratch/typecheck-tools'
python -m mypy omok offline verification/league_acceptance.py --follow-imports=silent
python -m compileall -q omok offline verification tests
git diff --cached --check
```

The collector's public API calls and concrete resolved definitions are preserved
in each compressed plan/results pair. It refuses existing output directories,
uses bounded durable batch execution, validates every trace and independently
replays its moves, emits reports and bounded representative candidate loss
positions, and records supplied availability. Genuine player failures are
retained as reliability evidence; infrastructure failures, pending slots,
invalid replay or unreaped workers reject complete smoke collection.

Actual machine: CPython **3.14.8**, Windows 10 build 19045, AMD Ryzen 3 3300X
(4 cores, 8 logical processors), **25,700,585,472 bytes observed RAM**. Monotonic
clock: Windows `QueryPerformanceCounter`, reported resolution 0.0000001 seconds.
No other agent experiments ran during the smoke measurement; external OS load,
power/frequency and temperature were not controlled. These are local observations,
not grader characteristics. Supervision uses fresh Python subprocesses, with
two persistent player workers per active game and separately bounded preflight.

| Actual saved run | Workers | Planned | Rules completed | Player failures | Caps | Infra/pending | Wall seconds | Observed slots/second |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Actual Phase 3 material vs eight opponents | 1 | 16 | 7 | 0 | 9 | 0 / 0 | 46.387 | 0.345 |
| Actual Phase 3 experimental effects vs Phase 2 and SimplePlayer | 1 | 4 | 2 | 0 | 2 | 0 / 0 | 10.588 | 0.378 |
| Retained Phase 2 throughput schedule | 1 | 4 | 0 | 0 | 4 | 0 / 0 | 7.946 | 0.503 |
| Identical retained Phase 2 throughput schedule | 2 | 4 | 0 | 0 | 4 | 0 / 0 | 4.296 | 0.931 |

All runs use empty-board screening, seed 20261010, two games per opponent with
exchanged colors and separately derived role seeds, and **5,000 ms total per
player**. Material's move cap is 20; effects' cap is 12; throughput's cap is 8.
The material opponents are retained Phase 1 and Phase 2, capture-focused,
pattern, two-ply search, defensive validation, supplied RandomPlayer and supplied
SimplePlayer. Supplied files were available and frozen with acknowledgments.
Both Phase 3 entries load the actual immutable #22 checkpoint
`105a8f64edaeb86082425c1fecb12932c06c4367`, rather than a recreated strategy.

**28 slots were observed: 9 rule completions, 19 caps, zero player or
infrastructure failures, zero pending.** Every trace passed replay and an
independent full-board rules replay; every game and preflight worker reported
`reaped: true`. A post-smoke `Win32_Process` query found no remaining Python
processes. This proves observed managed-worker cleanup, not malicious-descendant
containment or abrupt owner-kill guarantees.

The material candidate lost all seven completed games; effects lost both
completed games against SimplePlayer. Caps have no outcome, so the clean win
rates are respectively **0/7** and **0/2**. These short samples are not eight-game
qualification checks. No match coins, confidence interval, rating or class rank
is inferred. Material diagnostics completed depth 1–3 across 124 candidate calls;
effects completed depth 0–1 across 21 calls. This preserves the known performance
limitation and makes no new causal claim about its losses.

The two-worker throughput probe processed the same four capped slots about
1.85 times as fast as the serial probe. This measures setup, short play, cleanup
and persistence for that reduced-clock workload. It completed **zero rule games**,
so it supports no full-game throughput estimate. Start with one worker; two is
a reasonable local development experiment. Use one for final wall-clock checks
with explicit contention controls. No throughput or strategic-win threshold
was invented. Timings from concurrent screening cannot establish playing strength.

[The smoke summary](issue-34/smoke/summary.json), compressed registry and
per-run plan/results/report files preserve source/configuration IDs, exact
pool snapshot, job IDs/colors/seeds, timings, failure/cap facts, exposure and
search diagnostics. All nine representative candidate losses have bounded
pre-move exports alongside their complete traces. Full resumable run directories
remain in `.scratch/issue-34-smoke/*/run`; Git keeps their compact lossless
results/manifest copies. To resume, retain the original checkpoint and exports;
the compressed results alone are analysis evidence, not a replacement checkpoint.

Training/validation snapshots are immutable in the registry artifact. Defensive
validation received development exposure. Reserved `synthetic-space` received
**zero played-game or tactical exposure**; default exclusion and explicit
development rejection were checked without calling it. Metadata registration is
not competitive evaluation. Related families, deterministic duplicates, shared
sources and the one simple reserved design limit generalization claims.

[Restoration](issue-34/restoration.json) archived the passing framework checkpoint
`5e1c51247b84512682526d9a1b6784512518b344` into a fresh temporary directory,
removed inherited `PYTHONPATH`, and passed nine schedule/supervision/report checks.
[Engine restoration](issue-34/engine-restoration.json) separately confirmed
unchanged Phase 2 material, all five Phase 3 presets, terminal precedence, legal
both-color zero-clock calls, ownership and config isolation. Git retains the
engine/source identities and the completed #34 commit preserves the acceptance
tool, evidence and handoff. No packaging or clean submission verification is claimed.

Independent [standards/spec review](issue-34-review.md) has zero remaining
findings on both axes. Attribution and unresolved official manager/runtime,
classmate/TA availability, team metadata and final disclosure are documented
in the handoff. Evolution, tuning, promotion, final holdout and packaging remain
later phases.
