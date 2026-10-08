# Issue #15 — Phase 2 acceptance evidence

AI-written by OpenAI Codex. Scope and authority: GitHub issues #15, #9 and master
#1. Search/rules correctness passed; local gameplay reliability passed. **Blanket
public timing acceptance is partial:** 48 of 336 probes exceeded incoming 0.001 or
0.1 ms clocks. No evidence establishes a hard deadline on this or grader hardware.
Do not describe this checkpoint as unconditionally passing every timing criterion.

## Reproduction and evidence

Run from the repository root using Python 3.14.3, standard library only:

```sh
python3 -m unittest tests.test_simulator tests.test_reference tests.test_differential tests.test_search tests.test_iterative tests.test_tactics tests.test_transposition tests.test_integration -v
python3 -m verification.differential
python3 -I -S verification/offline_engine.py --iterative
python3 -m verification.acceptance measure
python3 -m verification.acceptance screening
python3 -m verification.acceptance official
python3 -m verification.acceptance replay
python3 -m compileall -q omok offline verification tests
python3 -m unittest discover -s tests -v
```

The evidence collector is a bounded serial batch using the existing CLI/runner,
not a tournament or promotion framework. Each game has an external 180-second
process deadline; a killed process is a failure with unknown offending player,
never an official draw. Partial summaries are saved after each game. Rerunning a
mode replaces that mode's evidence. Preserve existing results before reruns.

[Evidence directory](issue-15/) contains timing probes/distributions, structured
cProfile results plus raw local stats, differential summary, isolated execution,
two game summaries and all 48 compressed replayable traces. Trace hashes are in
summaries. `replay` validates recorded transitions and independently replays every
complete PV through the simple reference rules. Trace replay invokes no bots.
Engine and provided-source hashes, immutable per-turn configuration snapshots,
seeds, colors, clocks, nodes, depth distributions and timing are retained.

Optional development types:
`/tmp/omok-issue14-types/bin/mypy omok offline verification/acceptance.py verification/offline_engine.py --ignore-missing-imports --follow-imports=silent`.
This passed for 15 files. The temporary mypy environment is not a submission or
restoration dependency. Without `--follow-imports=silent`, following the imported
older `verification.integration` script reports two pre-existing inferred-variable
assignment errors; engine/runner types pass without that flag. Compilation is
syntax/import verification, not a replacement for type checking.

## Correctness and deterministic interruption

The first targeted run passed 90 tests; the updated integration file passed 10,
including red-before-green isolation of the integrated player. The final full
suite passed 119 tests. The master #1 pre-agreed simulator, public-player and runner
seams were reused. No fixture expectation was weakened or rule/search implementation
changed. Only the verification dependency guard now offers `--iterative`.

- Independent rules agreement: 32 sequences, 16 per ordinary/capture-biased mode,
  seeds 20261008–20261023 and 20361008–20361023, cap 240 placements per sequence;
  5,561 checked transitions and 1,064 captured stones. Thirty reached a rule
  terminal, two reached the verification cap. Placement, all capture rays,
  simultaneous captures/noncaptures, exact five/overlines, capture-exposed opponent
  wins, simultaneous/full-board draws and immutable parent/sibling/caller state pass.
- Matched trees: `test_search` seeds 0–9, controlled four-cell trees depths 1–4,
  both colors, signed evaluators; full-width late boards depths 1–3. `test_tactics`
  and `test_integration` repeat cached/uncached/unpruned tactical trees at depths
  1–3. Compare exact values and membership in the reference optimal set, not merely
  selected moves. Candidate membership and evaluator match; extensions are absent.
- Table: `test_transposition` covers both sides, exact/lower/upper bounds and
  tightened-window classification, depths 0–4 including changing-depth order,
  config/evaluator changes, malformed/excluded hints, collisions, FIFO eviction,
  capacities 0/1/4/16/128 and default 4096, cancellation before ancestor writes,
  and clean subsequent searches. A 65-ply line verifies the 64-ply payload bound.
- Required tactical fixtures: both colors/all four axes, strict wins versus draw
  or overline, direct defenses, multiple endpoints, capture defense `(7, 7)`,
  cap-one/poor-order preservation, locality-empty legal fallback, capture-induced
  loss and simultaneous draw, and incomplete scans retaining unknown responses.
  Independent reply enumeration establishes tactical truth. Existing fixtures
  are in `test_search`, `test_tactics`, and `test_integration`.
- Deterministic cancellation: every node limit across iterative commits, fake
  clocks inside preprocessing/scans/sort/order/evaluation/recursion, every public
  checkpoint in tactical selection, and pre-table-write interruption. Tests verify
  legal fallback before a completion, whole move/score/depth/PV retention afterward,
  unchanged caller/root, absence of incomplete exact ancestor entries, propagation
  of unexpected errors and clean reusable search. No sleep-based injection is used.

## Actual timing and isolated local profiling

Machine: Intel Core i5-7360U @ 2.30 GHz, 2 physical/4 logical CPUs, 8 GiB RAM,
macOS 13.7.8 x86_64, CPython 3.14.3; one serial worker, no GPU. Other OS activity
was not controlled. Runs were sequential, with no parallel game workers. Profiling
here means a separate serial local workload, not CPU affinity or a dedicated host.

336 public calls: four live boards (empty/sparse capture/tactical/dense), two colors,
11 incoming budgets (-2, 0, 0.001, 0.1, 1, 3, 5, 20, 200, 60000, -1 ms), three
repeats = 264 independent probes, plus 72 board-updating calls starting from actual
40 ms cumulative clocks. Clocks decrease by measured public elapsed time, rather
than resetting per move. Boards/moves pass independent legality/input checks.
Per-budget and cumulative-clock distributions record min/median/p95 nearest-rank/max.

| Incoming clock | Calls | Median public ms | Maximum public ms | Clock overruns |
| --- | ---: | ---: | ---: | ---: |
| 0.001 ms | 24 | 0.108 | 0.579 | 24 |
| 0.1 ms | 24 | 0.115 | 0.641 | 24 |
| 1 ms | 24 | 0.114 | 0.551 | 0 |
| 20 ms | 24 | 0.960 | 1.282 | 0 |
| 200 ms | 24 | 9.951 | 10.011 | 0 |
| 60000 ms | 24 | 100.067 | 100.686 | 0 |

The remaining probes had no positive-incoming-clock overrun. Negative/zero budgets
are fallback contract probes, not available-time promises. Zero legality/mutation
failures were observed. Forty-eight tiny-clock time failures remain explicitly
recorded; conversion/fallback alone consumes more than those clocks. The 2 ms
return margin is provisional. Atomic simulator calls and OS scheduling remain
nonpreemptible. No historical timing spike is erased by this smaller measured run.

Separate cProfile: ten sparse-capture turns, 60000 ms incoming, warm table retained,
about 1.002 seconds total public work, depth one completed in each call. `_moves`
accounts for about 0.941 seconds cumulative, tactical `analyze` 0.816 seconds,
exact-five geometric scans 0.429 seconds; these nested times must not be summed.
This profile supports investigating tactical/candidate cost before adding expensive
leaf features. Instrumentation changes timing; this is not a minimum-throughput gate.

Counter definitions: nodes count budget-approved root/recursive entries including
leaves, summed over all attempted iterations; completed depth counts placements in
the last full iteration, attempted depth includes interrupted work. Cutoffs count
closed alpha-beta windows, including table bound closures. Table probes count
recursive value lookups, hits compatible exact-depth entries, value cutoffs avoided
expansions; ordering hints are excluded. Reported table size is retained entries,
bounded at 4096; root candidate count is selected membership, not full legal width.
Elapsed ms includes conversion through move selection; allocated ms starts at public
entry. Timing never counts only inner recursion as the public result.

## Color-balanced game outcomes

Each batch starts empty, four seeds 20261009–20261012 per search color per opponent,
24 games, one worker. Both players receive independent cumulative clocks. The runner
still exposes failures after return and does not repair illegal moves or suppress
clock overruns. Screening uses 1000 ms/player and a 120-ply cap; official-clock checks
use 60000 ms/player and a 1000-ply resource cap. These are local official-clock
checks, not grading results. Deterministic duplicate games are not independent
samples; seeds do not make time-bounded search reproducible across machines.

| Budget | Opponent | Search black W/L/D | Search white W/L/D | Total W/L/D |
| --- | --- | --- | --- | --- |
| Screening | Phase 1 baseline | 4/0/0 | 0/4/0 | 4/4/0 |
| Screening | Professor RandomPlayer | 4/0/0 | 4/0/0 | 8/0/0 |
| Screening | Professor SimplePlayer | 0/4/0 | 0/4/0 | 0/8/0 |
| 60-second total | Phase 1 baseline | 4/0/0 | 4/0/0 | 8/0/0 |
| 60-second total | Professor RandomPlayer | 4/0/0 | 4/0/0 | 8/0/0 |
| 60-second total | Professor SimplePlayer | 0/4/0 | 0/4/0 | 0/8/0 |

All 48 games completed by rules, zero caps and zero observed crashes/illegal moves/
mutations/timeouts. Screening: 638 applied moves, 311 complete PVs, max public
search 50.143 ms, completed depths 0–2. Official clocks: 596 applied moves, 300
complete PVs, max public search 100.420 ms, completed depths 1–3. All 1,234 moves
and 611 complete PVs passed replay. Any crash would invalidate the opponent match
under assignment scoring; none occurred. No arbitrary win-rate/depth/node gate was
introduced. RandomPlayer results are local evidence, not a hidden-TA/rank claim.

## Representative failures and remaining limits

All SimplePlayer games are preserved failures of playing strength. For example,
`issue-15/official-simple-black-20261009.json.gz` is a replayable strict loss.
Material-only judgment and horizon limits are plausible hypotheses, not confirmed
loss diagnoses; the final move alone is not causal proof. Do not change the tactical
suite to excuse them. Raw tiny-clock failures are in `measurements.json` under
`incoming_clock_overruns`, with board name, color, move, depth and elapsed time.

The actual supplied base/bot inheritance works locally with explicit color. Grader
runtime/board types, official unlimited-sentinel translation, hidden TA agents,
final team naming/metadata and packaging remain external gates. External deadlines
bound whole games, not individual blocking player calls. No mature evaluator,
league/optimizer, hard per-turn process isolation or final package was built.
See [Phase 3 handoff](../phase-02-handoff.md) and [review](issue-15-review.md).
