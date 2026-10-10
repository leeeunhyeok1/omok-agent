# Immutable candidate proposals (#37)

AI-written by OpenAI Codex. This ticket consumes the phase 4 registry and runner.
It implements proposal generation and execution, not fitness, selection or promotion.
The incumbent, engine sources, evaluator feature semantics, fixed tactical checks,
total-clock enforcement, outcome accounting and pool restrictions stay fixed.

Save a policy before generating any candidates, using fresh paths:

```sh
python -m offline.proposals policy --output .scratch/material-policy.json --batch evaluation --groups material
python -m offline.proposals generate --policy .scratch/material-policy.json --seed 37 --count 3 --output .scratch/material-proposals
python -m offline.proposals policy --output .scratch/search-policy.json --batch search-time --groups candidates time --repair clip-domain
python -m offline.proposals generate --policy .scratch/search-policy.json --seed 37 --count 3 --output .scratch/search-proposals
```

The default parent is the retained `phase3-material` checkpoint. `--parent` accepts
a JSON registry Entry record; generation accepts repeated `--parent` flags.
Parents must be registered `omok.player.IterativePlayer` versions with the exact
supported engine bytes. Ordinary parents support resolved depth/node settings
and an optional registered `evaluation_path`; generated parents contain complete
`candidate_configuration` values. Other factories/settings are rejected.
An unconfigured retained material parent is resolved to the equivalent explicit
`material-v1` coefficients for offspring. The original callback and parent entry
are retained unchanged; offspring use the configured evaluator and fresh caches.

Policies pin engine and registry adapter source hashes, runtime and dependencies
before generation. Changed adapters require a new policy. They
record schema/version, domains, defaults, identity transformations, per-group
scales, diversity probability, repair and retry rules. Evaluation groups use only
enabled, implemented feature families. Feature version and enabled families are
frozen categories, never genes. No extension or new ordering mechanism is tunable.
Each attempt chooses one coherent group. Evaluation-only and search/time batches
cannot cross their declared boundary.

Implemented evaluator coefficients retain their integer [-4000, 4000] domains.
The frozen evaluator clips at 4000, below the 10000 terminal score, and uses
black-centric feature differences with the existing Negamax perspective conversion.
Search domains are deliberately conservative local screening choices around
the #36 baseline (8 plies, 10000 nodes, radius 2, cap 24, table capacity 4096,
100 ms maximum per turn). They are not strength-optimal values or previously
agreed thresholds:

| Setting | Domain |
| --- | --- |
| depth / nodes | integers 1..16 / 100..100000 |
| candidate radius / ordinary cap | integers 1..4 / 4..64 |
| table capacity | integer 0..8192 entries |
| maximum turn time / return margin | 5..250 ms / 2..20 ms |
| reserve / turn / soft fractions | 0.25..0.75 / 0.02..0.20 / 0.50..0.95 |

The table's existing bounded payload and count limit memory growth; this is not
a measured byte/RSS memory ceiling. Radius/cap apply only to ordinary moves;
mandatory tactics remain protected. Incoming remaining game time still controls
allocation and the harness enforces cumulative clocks independently. Larger
settings need new policy domains and separately measured resource evidence.

Integer mutation adds a uniform integer step; real mutation adds a uniform step
rounded to six decimal places. Group scales multiply each documented gene step.
Diversity samples uniformly within the selected group's domains. By default an
out-of-domain proposal is rejected; `clip-domain` deterministically clips numeric
values and records proposed and actual values. There is no type coercion, hidden
normalization or repair of categorical/semantic fields. Each requested slot gets
at most 12 attempts by default (policy limit 1..100). Duplicates consume retries;
exhaustion leaves the slot empty rather than looping indefinitely.

The output has the exact saved policy, parent entries/resolved configurations,
and `proposals.json`. The latter records actual proposals, changed values,
repairs, rejection reasons, accepted immutable entries, parent IDs, per-attempt
seed/state digest, complete outer RNG states and exhausted slots. Parent order
does not affect generation; no worker completion events drive proposals.
Output paths are write-once. Engine parameters and artifacts are JSON and require
only the standard library. Generation requests no opponent games.

Exact actual configuration values plus engine sources/runtime/dependencies form
the genotype identity; display names and ancestry do not. One batch produces
one entry per accepted genotype, records duplicate attempts and merges ancestry.
Unchanged parent genotypes are also deduplicated. Candidates use deterministic
genotype IDs, so aliases are not extra population members. Downstream selection
must consume this unique list and retain the existing runner's duplicate-evidence
groups; this ticket assigns no fitness or statistical weight. Pass known candidates
as parents to deduplicate against them in a subsequent proposal batch.

Load each `candidates[*].entry` with `Entry.from_record`, then use the existing
`ExperimentPlan.resolve`/`run_experiment` or `run_registered_game` with a training
purpose. Registry construction rejects invalid serialized types, nonfinite values,
unknown categories, unsafe time/resource settings and unsupported parameters
before jobs can be scheduled. Workers reconstruct the complete configuration
using the verified restored engine, create fresh per-game player/search/table
instances, and preserve source/configuration identity in diagnostics and traces.
Changing an evaluator uses the existing incompatible-cache clearing mechanism.
No holdout execution or promotion is performed by proposal generation.

Verification:

```sh
python -m unittest tests.test_proposals -v
python -m verification.proposals --output .scratch/proposal-pilot
```

The bounded pilot records evaluation and search/time candidates, repeatability,
both-color real games against a training opponent, and independently replayed
traces. Its caps and small sample do not establish improvement or promotion.
