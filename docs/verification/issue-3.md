# Issue #3 acceptance report

Verified 2026-10-08 against GitHub issue #3, with rule authority from issue #2
sections 5–6 and the agreed simulator seam in issue #1 section 8.

## Environment and commands

Python 3.14.3; macOS 13.7.8 x86_64; Intel Core i5-7360U at 2.30 GHz; one worker.
No third-party runtime or test dependency. From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q omok verification tests
python3 -m verification.differential
python3 -m verification.benchmark
python3 -S -c 'import omok.simulator'
```

Results: **36 tests passed**, Python compilation passed, engine import with site
packages disabled passed. Engine imports no verification/opponent modules and has
no network dependency. Strict static type checking also passed for `omok/` and
`verification/` using a local offline-tool environment with mypy (not an engine
dependency). To reproduce that optional check:

```sh
python3 -m venv .scratch/typecheck-env
.scratch/typecheck-env/bin/python -m pip install mypy
.scratch/typecheck-env/bin/python -m mypy --strict omok verification
```

## Deterministic evidence

17 public position/transition tests run with identical literal expectations against
each implementation. Two further tests exercise seeded differential verification
and verify that a deliberately mismatching comparison saves its seed/sequence.

| Category | Evidence |
| --- | --- |
| Placement, ownership, validation | Empty black move, row/column order, explicit color with unbalanced stone counts, detached input, malformed boards/colors/moves, bounds and occupied-cell rejection, integer protocol normalization |
| Captures | All eight rays for both colors, multiple pairs, all eight pairs together (16 captured stones still ongoing), edge endpoints, exiting rays and negative-index wrapping, gaps, longer groups, missing endpoint, middle placement, unrelated/nonrecursive pairs, vacancy reuse |
| Exact five | Both colors/four orientations at edges, static five becoming six, runs of six/seven/19, live groups joined into six, gaps, separate five alongside overline, static simultaneous wins |
| Capture-induced results | Issue #2's exact coordinates for opponent victory and simultaneous draw, also with colors swapped; starting positions asserted live |
| Dense boards | Modulo-four full-board construction, final placement without capture, final placement reopening exactly two cells; color-complemented versions; independent geometric proof and grouped-line verification |
| Child isolation | Complete four-field snapshots, external input, multiple siblings, nested children, consecutive captures with prior values, rejected moves and changed exported snapshots |

The [contract](../simulator.md) records the dense-fixture construction/proof,
primary representation, prior values, and terminal-side convention.

## Differential evidence

[Machine-readable results](issue-3-differential.json) contain per-sequence seeds,
move/capture counts, outcomes, reasons, stop labels, and elapsed time.

- Ordinary seeds: **20261008–20261023**, 16 sequences, 2,336 mainline moves,
  78 captured stones; 6 black wins, 10 white wins.
- Capture-biased seeds: **20361008–20361023**, 16 sequences, 1,883 mainline moves,
  986 captured stones; 5 black wins, 9 white wins, 2 verification-capped sequences.
- Cap: 240 moves per sequence, explicitly a verification limit; the two capped
  positions remain `ongoing`, never relabeled as game draws.
- Including sampled sibling/nested exploration every 20 plies: **5,561 checked
  transitions**, **zero mismatches**, elapsed **12.783 seconds**.

Every move compares cells, captured sets/prior values, outcome, reason, and side,
plus complete parent state. Both modes begin with the empty board and stop at
terminal outcomes. Capture-biased sampling prioritizes available captures and
otherwise samples near existing stones; ordinary sampling is uniform over vacancies.
Seeds reproduce sampling and exploration. Every detected transition discrepancy
saves initial state, seed, mode, move prefix (including sampled branches), and the
pre-error states under `.scratch/differential/mismatch-<mode>-<seed>.json`.

## Measured transition speed

[Benchmark results](issue-3-benchmark.json): best of three batches of 1,000 repeated
child transitions from each fixed parent, excluding construction/reference checks.

| Parent fixture | Transitions/second |
| --- | ---: |
| Empty | 23,814 |
| Sparse two-stone capture | 20,256 |
| Dense capture | 1,510 |

These are local rules-transition timings, not search throughput or strength claims.

## Scope and handoff

Issue #3's rules/reference/isolation acceptance categories pass. The supplied
professor bots retain their original source; both visibly use `__init__(color)`
and `take_turn(board, time)` and tuple integer coordinates. Their base `player`
module is missing, so official player integration is pending. Game timings, runner,
clock enforcement, playable agent, search, tournaments, and packaging are outside
this bounded ticket. This report does not claim full Phase 01 completion.

The engine's immutable child-copy API is ready for future search. Check explicit
outcomes before expanding a child; terminal children retain the mover's side.

AI attribution and checkpoint interaction records are in `llm-usage/`.

The [two-axis code review](issue-3-review.md) found no standards violations or spec
findings, with one optional sampling-predicate duplication retained intentionally.
