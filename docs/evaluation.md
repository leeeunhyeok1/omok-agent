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

## Smaller line potential (`potential-v1`, issue #18)

AI-written by OpenAI Codex. These are selected definitions and provisional
parameters, separate from the supplied specification. `configs/potential-v1.json`
extends the frozen `lines-v1` semantics and coefficients with the independent
`potential` family. The default engine stays on Phase 2 material. Both older JSON
schemas and identities are preserved; they reject non-default potential settings.

A development window has four interior cells and an existing empty cell on each
end: `.abcd.`. Its interior contains only own stones and empties. Filling all
interior empties must produce a contiguous four whose **both** endpoint placements
would make a maximal run of exactly five on this axis. Thus an own stone directly
beyond either empty endpoint rejects that window; an opponent or board edge beyond
an endpoint does not. An edge in place of an endpoint, an occupied endpoint, or an
opponent inside the window blocks development. No off-board space is open.

| Feature | Counted unit | Provisional weight |
| --- | --- | ---: |
| `open_three` | Three contiguous own stones with at least one qualifying one-placement development window | 40 |
| `broken_three` | Three own stones spanning four cells with one internal empty gap in a qualifying window | 25 |
| `two_stone` | Two own stones spanning two, three or four cells in a qualifying two-placement development window | 5 |

Count each **stone-coordinate set on one axis** once, regardless of how many
windows or development moves support it. Inspection exposes sorted coordinate
sets under `potential.black.units` and `potential.white.units`, alongside counts.
Three stones occupying a window exclude counting its two-stone subsets. Four
stones exclude its three/two subsets. Distinct axes are distinct units even when
sharing stones; pairs on other axes may coexist with a three or four. Material
also overlaps intentionally. Four/completion and potential families can overlap
across axes, but no potential unit is a subset of a qualifying four on the same
axis: a fourth existing own stone either occupies an interior cell or blocks an
endpoint/development. These counts do not assert independent threats.

Examples (with surrounding empty space): `XXX` counts one open three, `XX_X` and
`X_XX` one broken three, `XX`, `X_X` and `X__X` one two-stone unit. `X_X_X` is outside
this chosen development definition. `OXXX`, a three beginning at the board edge,
and `X_XXX` have no qualifying three development. A three one cell in from an
edge can qualify. Requiring two exact-five endpoints deliberately excludes some
weaker one-ended or broken-four-only development; their geometry is not silently
called an open/broken three by this version.

Feasibility here is **static, pre-capture, same-axis geometry**: imagine filling
interior cells with own stones, with no intervening opponent turn. Captures,
defender moves, cross-axis overlines and simultaneous/opponent wins are not
verified by these counts. A capturable three may still qualify geometrically.
The existing verified-win family and mandatory tactical machinery continue to
resolve actual rules. Potential labels are heuristics, not forced-win facts.

Each signed feature is black count minus white count; contributions multiply
these by their coefficients, with no side-to-move asymmetry. Material remains a
small separately switchable black-minus-white count at weight 1; no center or
influence term is added. Clamp the combined sum to [-4000, 4000], below terminal
10000. The provisional open-three > broken-three > pair preference is a scoring
hypothesis, not a theorem about position strength.

`potential-v1` requires material, all six line coefficients and all three potential
coefficients, each integer in [-4000, 4000]. Its enabled families are any subset of
`material`, `lines`, `potential`. `potential_enabled=False` skips potential windows
in production; inspection still shows raw geometry, zero potential contributions,
and an enabled-family list excluding potential. Disabling `lines` preserves
potential while skipping four/completion verification in production. Config
switching retains automatic table invalidation. Checks in each development window
cooperate with search cancellation; inspection publishes no partial counts/score.
The traversal reuses canonical maximal lines, without new recursive search, clock,
ranking, tactical, rules, or mutable-position behavior.

Reproduce the quiet/blocked/edge/overline-adjacent/dense suite:

```sh
python3 -m verification.potential --config configs/potential-v1.json --repetitions 10
python3 -m unittest tests.test_potential -q
```

The suite embeds every board and explicit side, canonical configuration, raw
per-color units/counts, signed counts, weighted contributions, disabled-family
inspection and local timing. Its positions are nonterminal. It distinguishes
chosen score-order hypotheses from exact-five development facts. The persisted
report is `docs/verification/issue-18-suite.json`; timing is local static-evaluator
evidence, not a league result, promotion claim, or official-clock guarantee.

## Capture configuration (`capture-v1`, issue #19)

AI-written by OpenAI Codex. These definitions and provisional parameters are
implementation choices, separate from the supplied Phase 3 specification.
`configs/capture-v1.json` includes all earlier families and adds `captures`.
The Phase 2 default/checkpoint and all earlier JSON identities remain unchanged.

Full recomputation visits every empty coordinate for both hypothetical movers
regardless of the actual side to move, and checks all eight rays for the exact
`empty–enemy–enemy–own` pattern. It resolves every matching move through the
immutable simulator, with cooperative checks before/after hypothetical work.
Terminal input has no legal capture continuations. Adjacent stones alone,
occupied completion cells, missing endpoints, gaps, triples and truncated rays
are not opportunities. Captures resolve simultaneously before either color's
exact-five outcome is classified.

| Feature | Counted unit per color | Provisional weight |
| --- | --- | ---: |
| `capture_move` | Unique legal empty coordinate capturing at least one pair | 30 |
| `capture_pair` | Unique unordered pair of enemy coordinates captured by any such move | 10 |
| `multi_pair_move` | Unique capture coordinate removing at least two pairs | 20 |
| `vulnerable_pair` | Unique unordered pair of this color currently capturable by an opponent legal move | -40 |

One multi-pair opportunity counts as one move, with explicit pair/cell multiplicity.
Pair coordinates are sorted; sets deduplicate pairs and cells across rays/moves.
Inspection adds `captures.black`/`white`, per-color counts, sorted `moves`,
`captured_pairs`, `captured_cells`, `vulnerable_pairs`, and `vulnerable_cells`.
Each move includes its coordinate, pairs/cells, pair/cell counts, resolved
`outcome`, and classification `win`, `opponent_win`, `draw`, or `continuation`.
Only a strict mover victory receives `win`; capture-induced opponent victory and
simultaneous-win draws retain their correct labels. No cumulative capture totals
are stored or treated as a victory condition.

Vulnerability describes current capture geometry, including a legal capture
that would lose for its mover. It does not mean inevitable capture or proved
loss. Likewise the opportunity coefficients are geometric preferences: they
can reward a prospective losing capture, whose outcome remains explicitly
visible. Search terminal scores and protected tactics decide exact outcomes.
Capture-based attack/defense effects beyond these labels remain issue #20 work.

All scalar features are black minus white and independent of side to move.
Opportunity and risk contributions overlap deliberately. In this symmetric
one-move definition the signed vulnerable-pair feature is the negative of the
signed captured-pair feature; their independently configurable coefficients
therefore combine algebraically. This is not evidence of independent threats.
Weights are built-in integers in [-4000, 4000]; `captures_enabled` is a boolean
family switch. Ablation skips production capture work but inspection still
exposes raw counts with zero capture contributions. Other families can be
independently disabled. Configuration replacement retains table clearing and
identity isolation. Scores remain bounded to [-4000, 4000], below terminal values.

Cancellation publishes no partial inspection family or exact leaf cache score.
All hypothetical children own their boards; input and parent state remain intact.
No new derived feature cache, ranking, recursion, extension or clock policy is
introduced. Production omits per-move outcome explanations; development
inspection is separate and uses the same full rule recomputation.

```sh
python3 -m verification.evaluation --config configs/capture-v1.json --position position.json
python3 -m verification.captures --repetitions 5
python3 -m unittest tests.test_captures -q
```

The capture suite enumerates every legal move with the independent rules oracle
on empty, single/multiple, edge, capture-defense, opponent-win, draw, strict-win
and seeded dense boards. It records raw inspection, enabled/disabled totals and
static evaluation timings. This is correctness/cost evidence, not a playing
strength comparison or full Phase 3 acceptance.
