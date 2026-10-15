# SimplePlayer search repair and fresh training profile

October 16, 2026. AI-written implementation and analysis. No existing optimizer
run, champion artifact, or frozen policy was changed.

## Confirmed problem and change

The uploaded run showed both limited candidate coverage and repeated selection
from the initial champion. The fixed-position investigation reproduced one
avoidable fatal move with its actual coefficients. This establishes a concrete
engine problem rather than assuming the optimizer merely needs more time.

`omok/lines.py` now verifies the exact-five completion coordinates already found
by its line scan, avoiding another full tactical geometry scan. Every possible
win still goes through the simulator, preserving capture-induced opponent wins
and simultaneous draws. `omok/captures.py` enumerates existing own-stone anchors
for own–opponent–opponent–empty patterns rather than testing every empty square
in eight directions. Grouping by placement preserves simultaneous captures.

Feature definitions, coefficient values, score bounds, candidate membership,
rules, and search/time settings are unchanged. This is an engine-source change;
start a new optimization experiment rather than resuming the old run with it.

## Deterministic evidence

See [the saved-loss diagnosis](simpleplayer-saved-loss-diagnosis.md) for the exact
position, independently checked continuations, ranked hypotheses, and baseline
reproduction command.

At the same 100,000 cooperative-check limit:

- Baseline selected `(6, 8)`, evaluated four children, and allowed the demonstrated
  undefendable SimplePlayer threat.
- Updated evaluation selected `(11, 8)`, evaluated fourteen children, and avoided
  that continuation. Both results have completed depth zero; the regression
  checks actual move consequences, not depth alone.

The new regression was run against the isolated pre-change source and failed
with the expected losing move; it passes against the updated source. This work
budget is deterministic and is not a claim about an exact millisecond deadline.

Complete line reports, capture reports, and configured-evaluation inspection
reports matched exactly on 29 positions: fourteen captured fixtures and fifteen
seeded generated positions. Existing tests additionally cover capture rays,
symmetries, independent rule outcomes, simultaneous wins, cancellation, score
bounds, cache isolation, and both colors. The cancellation regression now sweeps
every checkpoint rather than relying on checkpoint numbers that exceeded the
optimized execution length.

Command executed successfully: 84 tests, 15.461 seconds locally:

```sh
python3 -m unittest tests.test_saved_simpleplayer_loss tests.test_evaluation_cost \
  tests.test_captures tests.test_lines tests.test_potential tests.test_threat_effects \
  tests.test_evaluation tests.test_search tests.test_iterative tests.test_tactics \
  tests.test_transposition
```

## Bounded complete-game comparison

The schedule was frozen before either revision played: four SimplePlayer jobs,
two openings crossed with both candidate colors, 60,000 ms per player, original
250 ms move cap, original full evaluator and coefficients. Runs were serial and
each resulting trace was replay-verified. The baseline is Git commit
`d44f054b38c073d30b7550746c76811a34d9232d`; updated source hashes and the identical
plan hash are recorded in the results.

| Metric | Baseline | Updated |
| --- | ---: | ---: |
| Wins / losses | 1 / 3 | 2 / 2 |
| Black wins / games | 1 / 2 | 0 / 2 |
| White wins / games | 0 / 2 | 2 / 2 |
| Failures / caps / pending | 0 / 0 / 0 | 0 / 0 / 0 |
| Recorded search turns | 60 | 51 |
| Turn-weighted mean completed depth | 0.5167 | 1.2549 |
| Depth-zero turns | 31 / 60 | 5 / 51 |

These are eight local development games, not statistical evidence of a strength
gain or qualification. Black results regressed in this tiny schedule while White
results improved. Local Python is 3.14.3 on macOS; the uploaded Colab run used
Python 3.13.16 on Linux. External load and power were uncontrolled. Do not equate
these local results with a Colab rerun, nor apply an independent-game confidence
interval to two deterministic opening pairs.

The [frozen plan](verification/simpleplayer-repair/plan.json),
[source/runtime identities and results](verification/simpleplayer-repair/results.json),
and eight compressed raw traces alongside them are preserved. To run the same
development schedule deliberately against another source checkout:

```sh
python3 verification/simpleplayer_development.py --source-root . \
  --plan docs/verification/simpleplayer-repair/plan.json \
  --output .scratch/simpleplayer-repair/another-revision
```

The harness refuses to overwrite earlier results. No further games were launched
after this fixed eight-game comparison, and no optimization/training was run.

## Training change and concrete next experiment

The optional exploratory parent policy preserves a verified champion as elite
but allows feasible screening survivors to contribute mutations after a league
strength rejection. Known reliability/correctness or incomplete evidence still
blocks ancestry. Validation strength does not select parents. Champion promotion
still requires all original league, confirmation, validation, and official gates.

Eight additional optimizer/profile checks passed: seven focused tests cover
selection exclusions, validation separation, both profile initializers, distinct
jobs, and unchanged champion gates. The integration test below uses fabricated
scripted-worker outcomes through the real optimizer/proposal/league/checkpoint
path. It proves a league-rejected candidate contributes actual offspring ancestry
after interruption/resume while the champion and its transactions remain intact:

```sh
python3 -m unittest tests.test_exploration_parents.ExploratoryAncestryIntegrationTests -v
```

The integration test passed in 56.803 seconds. A preliminary invocation rejected
resume because source files were edited during its execution; rerunning after
source stabilized passed. This was the expected source-compatibility guard, not
an override or removal of that guard. Combined with the engine checks above,
92 focused tests passed. These mechanics fixtures are not real strength games.

The new [SimplePlayer-focused profile](colab-training/simple-focused.md) weights
SimplePlayer at half the initial screening objective, uses eight balanced jobs
over four distinct opening pairs, and separates confirmation openings. It retains
the original full evaluator and search/time settings. The old profile remains
available. Following the user's general-strength requirement, the notebook
defaults to the [balanced profile](colab-training/balanced.md), a fresh
`balanced-search-v3` experiment with one segment. It keeps equal weights for the
original five families and enables exploratory parents. The SimplePlayer-focused
profile remains optional. The notebook displays exploratory parents separately
from the champion.

Next inspect the new run's SimplePlayer wins/losses, move coverage, and parent
selection after one segment. An unchanged champion alone remains inconclusive;
parent movement alone is also not evidence of stronger play. Local initialization
and notebook command construction were checked; execution inside Colab remains
unverified. No LLM integration was necessary for this confirmed repair.
