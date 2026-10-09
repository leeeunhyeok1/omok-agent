# Saved evaluator configuration (issue #16)

AI-written by OpenAI Codex. These are provisional implementation decisions for
#16, separate from the supplied Phase 3 specification. The default player still
uses the unchanged Phase 2 material callback; no strength promotion is claimed.
Phase 2 checkpoint: `798963cae696eead8353232d1cc8c289cce473a9`.

## Contract and bounded scope

`FixedDepthSearch.score` accepts a built-in black-centric integer in [-4000, 4000]
on ordinary leaves and negates it for white perspective. Terminal values bypass
evaluation: winner +10000, loser -10000, draw zero. No mate-distance encoding
exists. `material_evaluation` is retained unchanged: black stones minus white
stones on the resulting board, in [-361, 361]. Captures affect this board count;
there is no cumulative capture reward or capture-count win rule.

Feature semantics `material-v1` count each occupied cell once, ignoring side to
move. They are immutable and independent of per-agent coefficients. The only
implemented family in this ticket is `material`. Line/threat families and capture
opportunity/vulnerability/effect families are pending #17–#20, not disabled
implementations or claimed Phase 3 acceptance. No new family is advertised without
a checked implementation. Positional influence remains deferred pending utility.

The coefficient is a built-in integer in [-4000, 4000], default 1; bools, floats
(including NaN/infinity), strings and unknown names are rejected. Negative values
are supported experimental parameters, not sensible competitive defaults. Family
enablement is explicit, default enabled; a zero coefficient and a disabled family
have distinct identities. Disabled production evaluation skips the scan. Inspection
still shows the raw feature for explaining ablation.

The exact integer product is symmetrically clamped to [-4000, 4000]. Inspection
reports the raw product, bounded total and whether clamping occurred; equality to
the bound is not saturation. This is a static heuristic, not a win probability.
On terminal positions inspection still explains that static heuristic and labels
the outcome; search separately supplies the terminal value above.

## Loading and switching

```python
from omok.evaluation import EvaluationConfig, ConfiguredEvaluator
from omok.search import FixedDepthSearch
from omok.player import IterativePlayer

config = EvaluationConfig.load('configs/material-v1.json')
engine = FixedDepthSearch(evaluation_config=config)
player = IterativePlayer(0, evaluation_config=config)
# Existing search, candidates, tactics, clocks and coordinate return are preserved.
player.set_evaluation_config(EvaluationConfig(material=2))
engine.set_evaluation_config(EvaluationConfig(material=-1))
config.save('my-material.json')
```

JSON requires exactly `feature_version`, `coefficients` (exactly `material`) and
`enabled_families` (either `[]` or `["material"]`). Missing/extra/duplicate keys,
unknown versions, duplicate/unknown families and malformed types fail before
search. `canonical_json()` emits sorted keys, compact separators and ASCII JSON;
`identity` is SHA-256 of its UTF-8/ASCII bytes, excluding any trailing newline.
Saving appends one newline; whitespace/key order in a loaded file does not change
identity. Frozen configs own primitive values, with no shared mutable weights.

The existing engine namespace, compatibility token, callback/policy object
identities, score bounds and extension version segregate table values and hints.
Installing an immutable configured callback replaces both ordinary/cooperative
callbacks, changes their identity, and clears all table scores/hints immediately.
An invalid installation leaves the old engine intact. Player switching also resets
stale last-turn diagnostics. Switch between searches/turns; concurrent mutation of
a running engine is unsupported. Distinct agents can share a configuration safely.

Ordinary ranking remains the independent Phase 2 adjacency/center rule; it does
not consume evaluation coefficients. Tactical membership/protection and recursion
are unchanged. No derived feature/scalar cache is added. Cooperative evaluation
checks before, during each row and after work. Cancellation propagates to search,
which never stores the interrupted leaf or a completed partial score. Previously
completed children/iterations retain the existing semantics.

## Development inspection

`ConfiguredEvaluator(config).inspect(position, check=...)` reports feature version,
configuration identity, side/outcome/black perspective, features, coefficients,
enabled families, contributions, raw/bounded total and saturation/incomplete status.
Cancellation returns an incomplete report with null features/totals and its reason;
production evaluation raises the existing `SearchCancelled` signal. Neither path
mutates the immutable position. Public player diagnostics add the configuration
identity and canonical configuration without changing `(row, column)`.

For a JSON position containing `board` (19 x 19) and explicit `side_to_move`:

```sh
python3 -m verification.evaluation --config configs/material-v1.json --position position.json
```

Report generation is development-only and does not run at production leaves.
Submission imports remain standard-library-only. No league, evolution, clock
policy change, feature-cost profiling or packaging is included in this ticket.

## Line configuration (`lines-v1`, issue #17)

AI-written by OpenAI Codex. These definitions and provisional coefficients are
implementation choices, separate from `03_EVALUATION_SPEC.md`. Load
`configs/lines-v1.json` through the same search/player APIs and inspection command
above. The default remains Phase 2 material; this ticket makes no strength claim.
The material-v1 file, schema, identity, and checkpoint remain available unchanged.
Threes, twos, multiple-threat independence and capture feature families remain
pending their separate tickets.

Full recomputation uses maximal board lines in the four simulator axes: horizontal
right, vertical down, diagonal down-right and diagonal down-left. The board line
starts where its predecessor is outside the board; it is visited once, never also
in reverse. An opponent or board edge blocks an endpoint. Empty cells are open.
Definitions are independent of side to move; signed features are black minus white.

| Feature | Counted unit | Provisional weight |
| --- | --- | ---: |
| `open_four` | Maximal contiguous run of four with two adjacent empty endpoints | 300 |
| `closed_four` | Maximal contiguous run of four with exactly one adjacent empty endpoint, including an edge four | 100 |
| `broken_four` | Four own stones in a five-cell span with one internal empty gap, whose filling makes a maximal run of exactly five on this axis | 150 |
| `geometric_completion` | Unique empty coordinate that makes a maximal own run of exactly five on at least one axis before capture/outcome verification | 0 |
| `verified_win` | Unique legal coordinate whose resolved outcome is a strict mover win, using the existing tactical detector | 300 |
| `overline_trap` | Unique empty coordinate whose filling makes a maximal own run of at least six on at least one axis | -20 |

A contiguous four is counted once, rather than once for each endpoint/five-cell
window. A four with no open endpoints is omitted. Broken fours are counted per
line/gap; different axes may share their completion cell. Completion, strict-win,
and trap counts deduplicate coordinates across all axes. A gap joining five stones
into six is a trap, not a broken four or exact-five completion. A six-stone run
contains neither several fours nor several wins in this representation.

An open endpoint beyond which another own stone lies can be an overline trap:
`XXXX_X` is still a geometric open four if the other endpoint is empty, but its
right endpoint is not an exact-five completion. These fours describe geometry,
not verified tactics. Different families deliberately overlap: a single open
four can contribute one run and two verified coordinates. A move can be both a
trap on one axis and a strict win on another. The trap term is therefore a
provisional geometric warning, not a forbidden move or a verified losing outcome.
No approximate multi-move exactly-five potential is represented here.

Strict wins resolve captures and check both colors through `immediate_wins`.
Simultaneous-win draws and capture-induced opponent wins are excluded. Two strict
winning endpoints do not establish independent threats or a forced win: a shared
capture defense can break the line. Terminal input has zero verified legal
continuations while inspection can still describe its static geometry.

The lines-v1 JSON coefficient object requires `material` and all six names above.
Each coefficient is a built-in integer in [-4000, 4000]. Families may contain
`material`, `lines`, both or neither; order is canonicalized and unknown/duplicate
names are rejected. `EvaluationConfig(feature_version='lines-v1',
lines_enabled=False)` disables all line scans in production but inspection still
exposes their features with zero contributions. Individual weights can also be
zeroed. Material-v1 rejects non-default line settings so an ignored coefficient
cannot silently share its persisted identity. Configuration replacement retains
the existing table clearing/identity contract.

Inspection adds `lines.black` and `lines.white`, including per-color counts and
sorted `geometric_completions`, `verified_wins`, and `overline_traps`. `features`
contains signed counts; `contributions` contains the enabled weighted terms.
The exact sum is clamped to [-4000, 4000], below terminal magnitude 10000.
Cooperative checkpoints cover line traversal, candidate scans, and both sides of
hypothetical move verification. Each simulator move is a bounded immutable board
copy; interruption discards local work and inspection reports null features and
score with `incomplete=true`. There is no feature cache or recursion/ordering change.
