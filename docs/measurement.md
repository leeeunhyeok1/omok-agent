# Evaluator measurement (#21)

AI-written by OpenAI Codex. These measurement definitions are implementation
choices, separate from the supplied evaluation specification. No weights, rule
semantics, tactical membership, ordinary ranking, recursion, or clock allocation
policy are changed. The retained Phase 2 callback remains the default.

## Per-call counters

`FixedDepthSearch.search` and `.iterative` return counters in `SearchResult`.
`IterativePlayer.diagnostics()` exposes them without changing public coordinates.
Counters reset for each call; iterative counts include completed iterations and
work in an interrupted next iteration.

| Counter | Meaning |
| --- | --- |
| `evaluation_calls` | Nonterminal leaf scoring attempts that invoke the evaluator |
| `evaluation_completed` | Calls returning a valid bounded scalar through the score boundary |
| `evaluation_cancelled` | Calls interrupted by `SearchCancelled` inside that boundary |
| `evaluation_cache_hits` | Exact depth-zero transposition values reused without an evaluator call |

Terminal scores and cache reuse do not count as evaluator calls. A cancellation
at the checkpoint *after* a completed evaluator call leaves that evaluation
completed, even if the search does not commit the iteration. Other evaluator
exceptions propagate to the existing runner failure path; they never become
cancellation or a guessed score. No successful result is returned for those
exceptions. There is no feature/scalar cache; internal subtree reuse remains in
`table_value_cutoffs` and cannot honestly be converted to an inferred number of
saved evaluator calls. Direct `score` and explicit inspection do not contribute
to a search call's counters.

## Optional sampled production costs

Construct `FixedDepthSearch(profile_every=N)`; zero disables all cost timers.
Positive N samples call 1, then 1+N, 1+2N, etc., separately in each search call.
`evaluation_profile` is null when disabled. Reports aggregate actual production
scans, never call `inspect`, and retain no per-leaf explanation or position list.

Each measured family has `calls`, `completed`, `incomplete`, and `elapsed_ns`.
An interrupted scan contributes its elapsed time and an incomplete count; it is
not a completed feature vector. `evaluator_total` is inclusive of validation,
feature scans and contribution summation. It overlaps family times, so do not
sum it with them. Disabled scans have no entry. If multiplicity requires line
scanning while line scoring is disabled, the required scan is still measured.
Shared fours/potential work is reported as `lines+potential`; it cannot be
attributed independently without measuring another implementation. Other labels
are `material`, `lines`, `potential`, `captures`, `effects`, and `multiplicity`.
Custom/retained callbacks receive inclusive total timing only.

`instrumentation_bookkeeping_ns` measures timer-record initialization/update work;
it excludes timer and callback dispatch overhead. The comparison route also
reports one paired uninstrumented/sampled runtime delta and ratio per config.
This includes scheduling/cache/order noise and can be negative. It is neither a
calibrated overhead estimate nor strength evidence. Sampling changes elapsed
time and may change deadline-limited completed depth, but it cannot change a
completed deterministic score or swallow exceptions/cancellation.

## Saved configurations through the existing game runner

```sh
python3 -m offline --engine search --evaluation-config configs/material-v1.json \
  --diagnostics --profile-every 2 --agent-color black --opponent smoke \
  --seed 20261009 --max-depth 2 --max-nodes 40 --candidate-radius 2 \
  --candidate-cap 3 --max-time-ms 100 --black-ms 60000 --white-ms 60000 \
  --move-cap 6 --output .scratch/material-black.json
python3 -m offline --replay .scratch/material-black.json
```

Repeat with `--agent-color white`. `--fixture` and `--start` retain their existing
meaning; the trace records the complete initial state, not just its filename.
Provided RandomPlayer/SimplePlayer adapters also accept the evaluator/settings
flags, preserving official inheritance. Profiling requires `--diagnostics` so
measurements are not silently discarded. Configuration/profile flags require
`--engine search`. Omit `--evaluation-config` for the retained Phase 2 evaluator.
Without new flags, radius 2, cap 24, table 4096, depth 8, 10000 nodes and the
100 ms maximum turn allocation remain unchanged. `--max-time-ms` selects the
existing policy parameter; the allocation formula remains unchanged.

Trace metadata records canonical config/version/identity, agent color, opponent
version/source hashes, seed, initial state/opening, settings and source hashes
for all engine modules. Observed conditions include Python implementation/version,
OS/architecture, CPU model/logical CPU count, affinity where available, load
average where available, monotonic clock characteristics and one sequential
worker. External contention is explicitly uncontrolled. Source hashes identify
local modifications beyond a version label. Diagnostics errors and runner failures
retain the existing event/failure records. Real-clock games debit actual turn
time, including instrumentation, from each player's independent total clock.
`move_cap` truncation remains **capped**, never a terminal draw or a win.

## Controlled comparison routes

```sh
python3 -m offline.compare --configs configs/material-v1.json configs/effects-v1.json \
  --route fixed-depth --fixture empty --color black --depth 2 --cap 3 \
  --radius 2 --nodes 40 --profile-every 2 --output .scratch/fixed.json
python3 -m offline.compare --configs configs/material-v1.json configs/effects-v1.json \
  --route node-budget --fixture empty --color black --depth 2 --cap 3 \
  --radius 2 --nodes 40 --profile-every 2 --output .scratch/nodes.json
```

`--start position.json` accepts a board and side_to_move. `--color` explicitly
overrides that side if supplied. Configurations are loaded with the same strict
schema as production; all implemented versions/ablations can be compared.
No incomplete family is advertised as implemented.

Both routes first freeze one tactical candidate tree, preserving mandatory
wins/defenses and ordinary ranking independently of evaluator weights. The report
saves every selected state's board/side and moves plus a canonical tree hash.
Fixed-depth uses unpruned Negamax without table reuse or clocks, so all configs
visit the identical tree. Node-budget uses unchanged iterative alpha-beta,
fresh tables and a shared per-call node limit, with clocks disabled. Iterative
PV/table hints can reorder the frozen candidate sets; pruning/cancellation can
make visited nodes differ between configs. Its results are separately labeled
and do not establish equal runtime. Clock games use the same depth, node,
radius/cap and policy settings through the real player boundary, with normal
per-position candidate selection. They are explicitly not the frozen-tree run.

Tree construction is outside search timing: comparisons isolate evaluator costs
rather than measuring full production turn overhead. Depth 1–3, cap 1–8, radius
1–3 and at most eight configs bound development runs; tactical protection can
exceed the ordinary cap. There are no extensions, league, optimizer or promotion
rules. Timing comparisons are local diagnostic evidence, not independent games
or estimates of competitive strength.

Reproduce both colors, quiet/capture-defense comparisons, configuration reload,
cumulative-clock material games and replay checks:

```sh
python3 -m verification.measurement --output .scratch/measurement.json
python3 -m unittest tests.test_measurement -q
```

The evidence uses two six-ply empty-board games against retained Phase 2, plus
eight comparisons (two fixtures × both colors × two routes). The material and
experimental effects presets remain separate. See [acceptance](verification/issue-21.md).
