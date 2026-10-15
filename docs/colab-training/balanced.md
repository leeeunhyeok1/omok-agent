# Balanced fresh experiment

The notebook defaults to `TRAINING_PROFILE = "balanced"`,
`RUN_NAME = "balanced-search-v3"`, and one 30-minute segment. Initialize a fresh
experiment; do not change the source or policy of the saved search-v2 run.

This profile preserves the original all24 recipe's evaluator, search/time
settings, mutation groups, opponents, equal family weights, openings, sample
counts, and every champion gate. Its only policy change is the explicit
exploratory parent selection described in [the targeted profile](simple-focused.md).
Reliable screening survivors can contribute mutations despite a league strength
regression, while champion promotion still requires every original check.

The five screening families are SimplePlayer, RandomPlayer, synthetic-aggressive,
synthetic-capture, and synthetic-search1. Equal family weighting prevents a
SimplePlayer-only objective; this small pool does not establish general strength.
Selected incumbent/history opponents are added in the broader league.

```sh
python3 docs/colab-training/initialize-all24-colab.py \
  --profile balanced --output .scratch/balanced-search-v3
```

Inspect wins/losses by opponent and color, search coverage, selected parents, and
champion decisions after the first segment. Keep final holdout opponents out of
training. If classmate agents are added, register a new frozen opponent pool,
keep related designs in the same family, and reserve separate opponents or
versions for evaluation. The current profile includes only the existing bots;
no classmate agents have been supplied or added yet.

The optional `simple-focused` profile emphasizes the current known weakness.
The `all24` profile retains the old parent policy for comparisons. None of these
profiles guarantees promotion, SimplePlayer qualification, or general wins.
