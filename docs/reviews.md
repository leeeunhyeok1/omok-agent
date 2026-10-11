# Optimization reviews and checked regressions

AI-written by OpenAI Codex for #44, under Phase 5 (#35) and master #1.

Reviews assess saved training evidence through the existing screening/scoring and
replay interfaces. They never construct competitors or schedule validation or
holdout games. `batch` emits a compact Markdown summary and a JSON evidence
companion. Read authoritative optimizer and child checkpoints, even when reports
are missing or stale:

```sh
python -m offline.reviews batch --run saved-optimizer-run --output review.json
python -m offline.reviews batch --stage saved-stage --raw saved-raw.json --max-failures 6 --max-positions 3 --output review.json
```

The JSON companion preserves configuration/source identities, source attribution,
all-attempt reliability, coverage, caps, opponent/color scores, diagnostic timing,
execution segments, and selected traces. The summary reports available p95/max
turn time and optimizer attempts per recorded wall second. Missing measurements
remain unavailable. Controlled fixture games do not establish ordinary strength.
Incumbent verification is unknown when stage gates/coverage are incomplete;
screening advances alone cannot verify a new champion.

Optionally add `--checks saved-eligibility-directory` to reassess saved promotion
eligibility and reasons. This consumes already recorded validation/official-clock
evidence; it does not probe those pools. Add `--champion-store saved-store
--transaction transaction-identity` to include an actual committed promotion or
retention decision from #43. The transaction must match the review incumbent and
candidate cohort. Eligibility alone is never reported as a performed promotion.

Sampling greedily covers candidate identities, opponent versions, colors and a
clock-pressure hypothesis (remaining clock at or below 10% of starting budget).
Sampled positions spread across the game's plies, retaining up to 1,000 prior
moves, the complete source trace, clocks and available diagnostics. A player who
loses before taking a turn has no pre-turn positions. Automatic tags and phase,
evaluation, horizon or opening explanations remain hypotheses. Sampling does
not claim to locate the decisive mistake.

The review itself performs no deeper analysis. For a selected turn, declare a
separate analysis budget explicitly:

```sh
python -m offline.reviews analyze --trace loss.json --color 0 --ply 12 --kind immediate-win --max-transitions 361 --max-seconds 30 --output analysis.json --fixtures regressions
python -m offline.reviews analyze --trace loss.json --color 1 --ply 13 --kind immediate-defense --max-transitions 131000 --max-seconds 120 --output analysis.json
```

Analysis exhaustively plays legal moves through the independent reference rules.
Immediate wins require a strict win after captures; immediate defenses require a
current opponent threat and prevent every strict win on their next turn, allowing
an immediate mover win or draw. This is one/two-ply tactical search, not a claim of
strategic optimality. Both transition count and wall time are bounded. Partial
analysis exports no allowed set and stays unknown. An unavoidable loss, a safe
chosen move or absent threat is not a confirmed missed tactic. Longer-horizon and
best strategic moves remain unknown. Record richer explanations externally as
hypotheses until separately checked.

`--fixtures` requires a complete confirmed failure and independently rechecks
the source replay, analysis and expected moves before writing. Ordinary observed
rule outcomes use the existing independent rule checker:

```sh
python -m offline.reviews rule --trace loss.json --color 0 --ply 12 --outcome white_win --reason exact_five --fixtures regressions
python -m offline.reviews verify regressions/fixture-identity.json
```

Fixture filenames identify the position and assertion. Writes use exclusive
creation; existing expected answers cannot be replaced. Repeated identical
expectations preserve the original provenance. Fixtures store checked expectations,
analysis budget, trace history and source/AI attribution. Reverification is a
correctness gate independent of tuned configurations. Existing tactical tests
retain their expected outcomes; no engine/default parameter changes are included.

If evidence calls for an engine mechanism, pass `--engine-change proposal.json`.
The proposal must contain `problem`, `scope`, `behavior`, `correctness_gates`,
`comparison_plan`, `parent_engine_lineage`, `new_engine_lineage`,
`compatible_incumbents`, and `new_run`. Keep lineages distinct; describe rebenchmarking
compatible incumbents before a new comparable run. This records a bounded proposal
with its source review identity; it does not mix engine changes into parameter
results or execute the proposed experiment.

Reproduce the controlled examples (fabricated scoring outcomes, not strength):

```sh
python -m verification.reviews --output .scratch/review-example
python -m offline.reviews batch --stage .scratch/review-example/stage --raw .scratch/review-example/raw.json --output .scratch/review-example/cli-review.json
python -m unittest tests.test_reviews.ReviewTests -v
```
