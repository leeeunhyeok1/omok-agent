# Issue #22 — Evaluation v1 comparison

AI-written by OpenAI Codex. No LLM-usage records were created at user request.
Issue: “Compare evaluation v1 against Phase 2 and feature ablations.”

## Decision

Keep the unchanged Phase 2 material evaluator as the default. The complete
`configs/effects-v1.json` evaluator remains experimental: correctness checks pass,
but its provisional parameters and full-recomputation cost do not justify
promotion. All required implemented families remain selectable and checked.
No weights, rules, ordinary ranking, candidate protection, recursion, table policy,
clock formula, or submission dependencies were changed. Positional influence is
still deferred; geometric development and endpoint multiplicity remain explicitly
approximate, rather than claims of forced wins.

## Correctness and diagnostic evidence

The pre-strength [regression gate](issue-22/gate.json) passed 160 tests covering
independent labels, empty/sparse/edge/dense/capture fixtures, color/context/symmetry,
extreme bounds and invalid configurations, determinism, interleaved agents,
configuration switches versus fresh engines, cancellation, terminal precedence,
public immutability, tactics, inherited Player compatibility, and replay.
The new regression also compares reference Negamax, uncached alpha-beta, cold
cached alpha-beta and warm cached alpha-beta on the complete evaluator's identical
frozen tree. All configurations on all six selected trees agree in completed root
value with the reference. Timed fixed-tree search excludes candidate preparation;
ordinary ranking selects the tree once, independently of evaluation weights.

[Development evidence](issue-22/development.json) records canonical configurations,
complete frozen trees and identities, scores/moves/nodes/depths, evaluation calls,
paired sampling overhead, feature costs and raw feature inspection. Depth two,
candidate cap two, radius two; node-budget runs use twelve nodes with the existing
iterative recursion. Fixed-depth reference work and bounded iterative node results
are separate routes; neither is a real-clock strength estimate. Dense children
terminate without heuristic calls, explaining their cheap measurements.

The retained Phase 2 SimplePlayer loss
`issue-15/official-simple-black-20261009.json.gz` is replayed to establish the live
six-ply midpoint. A permanent replay regression independently reconstructs all
12 moves and checks the final white exact-five loss. All seven configurations
select `(8, 8)` at depth two/cap two on that midpoint, with changed scalar values.
This does not establish an earlier decisive mistake: material judgment and horizon
limits remain **hypotheses**. Existing confirmed rule and tactical fixtures remain
unchanged. No new strategic failure is claimed proved.

## Real-clock games

[Integration records](issue-22/integration.json) retain 48 traces, four games per
color for each evaluator/opponent pair. Each player starts with a cumulative
60000 ms; games start empty and have a 400-ply resource cap and a 150-second
external timeout. All 48 terminated by exact-five, with no cap, draw, illegal
move, mutation, crash, or timeout observed. Incoming clocks decrease between turns.
A crash in any supplied-opponent game would fail that opponent match, rather than
count as only one ordinary loss. These are integration/development checks, not a
strength guarantee or final holdout evaluation.

| Evaluator | Opponent | Wins / losses | Unique move sequences | Fallback turns / agent turns |
| --- | --- | --- | ---: | ---: |
| Phase 2 | Immutable Phase 2 | 4 / 4 | 1 | 0 / 60 |
| Phase 2 | RandomPlayer | 8 / 0 | 8 | 0 / 96 |
| Phase 2 | SimplePlayer | 0 / 8 | 3 | 0 / 58 |
| Complete v1 | Immutable Phase 2 | 0 / 8 | 2 | 76 / 80 |
| Complete v1 | RandomPlayer | 8 / 0 | 8 | 68 / 80 |
| Complete v1 | SimplePlayer | 0 / 8 | 2 | 32 / 36 |

[Summary](issue-22/summary.json) includes both-color outcomes and duplication counts.
Repeated deterministic move sequences are duplicate evidence. Clock cutoffs can
change moves/depths even with a fixed seed. The material mirror's first-player win
repeats the same sequence across both assigned colors. Do not interpret these
small, related samples as independent trials or impose a fabricated threshold.

The opponent is actually loaded from git checkpoint
`798963cae696eead8353232d1cc8c289cce473a9`, not relabeled current code. A persistent
subprocess isolates its absolute `omok` imports. Startup/import and JSON IPC on
the first/each turn are charged to that opponent's clock; its diagnostic JSON also
costs time, whereas current-agent diagnostics are collected after the charged
turn. This unavoidable adapter asymmetry prevents a precise strength estimate.
Both versions use the same depth eight/node limit 10000/radius two/cap 24/100 ms
maximum-turn policy, unchanged adjacency/center ranking, no extensions and table
capacity 4096. Feature profiling is disabled in clock games. Source hashes,
supplied-bot provenance, seeds, starts, runtime/hardware and worker count are saved.

## Cost and ablations

Full recomputation was profiled first. The complete evaluator's plain reference
search on selected live fixtures took roughly 37–187 ms versus 0.4–0.7 ms for
material in the initial pass (reruns differ; JSON is authoritative). Aggregate
sampled full-config development scans in the final pass measured about 736 ms in
capture effects, 250 ms in shared lines/potential, 82 ms in captures, 1 ms in
material, and 0.2 ms in multiplicity, out of 1072 ms evaluator total. These are
nested aggregate costs, not additive throughput estimates for games. Paired
instrumentation deltas include noise/order effects; negative deltas are retained.

The dominant measured cost is capture-effect recomputation. No incremental cache
or optimization was adopted: the evidence supports retaining the verified default,
not adding cache complexity to rescue these provisional parameters. Future work
can investigate this measured bottleneck separately.

All five new families have leave-one-family-out configurations with their other
weights fixed. Six fixture comparisons and [28 bounded ablation games](issue-22/ablations.json)
cover both colors, empty starts and the capture-defense board, with 60000 ms per
player and a 24-ply cap. All terminated without a cap or failure in this run.
Each experimental ablation lost both empty-start games against Phase 2, with
19 fallback turns out of 20. On the capture board all configurations won once and
lost once; the white-to-move context has an immediate win and is only a tactical
control. Removing effects reduces fixture compute cost substantially but does not
improve these bounded game outcomes. These negative results do not prove a family
has no value at different parameters or larger clocks.

Disabling lines does not eliminate line scanning while multiplicity still needs
its endpoints; `lines+potential` is explicitly a shared cost bucket. Disabling a
family skips its contribution, but dependency scans can remain. This coupling is
retained and reported, rather than attributed as independent family cost.

48 public timing probes cover four fixtures, both colors, both evaluators, and
60000/3/0.5 ms. All moves were legal and inputs unchanged. Four dense 0.5 ms calls
exceeded their incoming clock (approximately 0.54–0.58 ms). Tiny-clock acceptance
remains partial for both versions. Normal 100 ms search allocation is a turn cap,
not the full game clock; return/unwind can slightly exceed allocation without
exhausting a 60000 ms cumulative budget.

## Reproduction and validation

```sh
python3 -m verification.evaluation_acceptance gate
python3 -m verification.evaluation_acceptance development
python3 -m verification.evaluation_acceptance integration
python3 -m verification.evaluation_acceptance ablations
python3 -m verification.evaluation_acceptance summary
python3 -m unittest tests.test_measurement tests.test_replay -q
python3 -m unittest discover -s tests -q
.scratch/issue-21-tools/bin/python -m mypy omok offline verification/evaluation_acceptance.py --follow-imports=silent
python3 -m compileall -q omok offline verification tests
python3 -I -S verification/offline_engine.py --iterative
```

Use a new `--output-dir` for a new experiment. Game batches checkpoint after each
game and resume completed keys; engine-source, canonical evaluator, supplied-opponent and offline-source changes reject
stale runs. Batch manifests were added after review, after checking every saved trace
against its evaluator, supplied-source, checkpoint and settings identities. Summary
hash-checks and replays every saved trace (76 total). Runs are serial on the recorded
Intel i5-7360U, Python 3.14.3; external contention is uncontrolled. Full-suite and
review disposition are recorded in [the review report](issue-22-review.md).
No reserved opponents, league, evolution, search extensions or packaging were used.
