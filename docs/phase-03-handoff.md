# Phase 3 acceptance and handoff

AI-written by OpenAI Codex for issues #22–#23. Implementation choices here and in
[the evaluator contract](evaluation.md) are separate from the supplied Phase 3
specification; neither the master nor supplied specification was rewritten.

**Engineering verification passes; competitive acceptance does not.** Keep the
Phase 2 material evaluator as the default. Both it and full evaluation v1 lost
all eight supplied SimplePlayer games in #22. The assignment requires at least
five strict wins out of eight; this target is unmet. Full v1 also lost all eight
against the immutable Phase 2 agent and frequently completed no search iteration.
Passing feature checks is not evidence of a stronger playable agent.

## Feature inventory and acceptance map

The opt-in `effects-v1` preset implements all six families below. The default
uncustomized player uses the retained material callback: **none of the five new
families contributes to the default**, despite remaining implemented and tested.
Inspection computes raw disabled-family features; production skips disabled work
except dependency scans (multiplicity needs line endpoints).

| Required capability | Definition / implementation / preset status | Fixed fixtures and verification | Retained evidence |
| --- | --- | --- | --- |
| Retained evaluator | Material = black stones minus white; `omok/evaluation.py`, `material-v1.json`; default callback remains `omok/search.py:material_evaluation` | `tests.test_evaluation`: saved material reproduces Phase 2, round-trip, bounds, isolation | [#16](verification/issue-16.md), [restoration](verification/issue-23-restoration.json) |
| Exactly-five potential and fours | `omok/lines.py`; `lines-v1` and later presets; open/closed/broken fours, deduplicated geometric and verified completions, overline warning | `tests.test_lines`: row 9 columns 6–9, blocked/edge/gapped fours, six-stone trap, intersecting endpoints, all eight symmetries/both colors; independent outcome oracle | [#17](verification/issue-17.md), [timing](verification/issue-17-timing.json) |
| Open/broken threes and smaller potential | `omok/lines.py`; `potential-v1` and later; canonical same-axis stone sets in exact-five-compatible development windows | `tests.test_potential`, `verification.potential`: `XXX`, `XX_X`, `X_XX`, `XX`, `X_X`, `X__X`, blocked/edge/overline-adjacent and dense boards | [suite](verification/issue-18-suite.json), [#18](verification/issue-18.md) |
| Captures and vulnerable pairs | `omok/captures.py`; `capture-v1` and later; legal capture coordinates and unique unordered pairs, multiple-pair moves, actual vulnerable pairs | `tests.test_captures`, `verification.captures`: all eight rays, multiple/edge/occupied/absent-endpoint/gapped rays, opponent exact five, simultaneous draw, independent enumeration | [suite](verification/issue-19-suite.json), [#19](verification/issue-19.md) |
| Capture attack/defense and exposed opponent five | `omok/threat_effects.py`; `effects-v1`; full before/after changes of four/potential units and opponent exact fives, removal-specific geometric counterfactual | `tests.test_threat_effects`, `verification.threat_effects`: capturable open four/control, reopened broken three, intersecting affected lines, exposed five and draw | [suite](verification/issue-20-suite.json), [#20](verification/issue-20.md) |
| Double threats, offensive opportunity, defensive urgency | `omok/threat_effects.py`; `effects-v1`; distinct geometric/strict-win endpoints, context-dependent opportunities/urgency; inspection checks shared defenders | Same effects tests/oracle: capture defense `(7,7)`, shared endpoints/defenders, move-created intersecting endpoints, side context and color transforms | [suite](verification/issue-20-suite.json), [#20](verification/issue-20.md) |
| Positional influence | Conditional on measured benefit in the master; deferred and absent from schema. Ordinary Phase 2 adjacency/center ranking remains separate | No influence score or utility claim | [decisions](evaluation.md) |

Double-threat implementation is **endpoint multiplicity plus immediate shared-reply
inspection**, not a general forced-win solver. Smaller exactly-five potential is
static geometry with no intervening defender or hypothetical captures. Required
semantics are explicit approximations where documented, not silently proved tactics.

| Acceptance gate | Observable check / runnable command | Status and evidence |
| --- | --- | --- |
| Independent exact rule labels | `python3 -m unittest tests.test_lines tests.test_captures tests.test_threat_effects tests.test_replay -q` | Verified strict mover/opponent wins, draws, overlines and retained loss; existing reference oracle remains separate |
| Color/perspective/symmetry/context, determinism and configurations | `python3 -m unittest tests.test_evaluation tests.test_lines tests.test_potential tests.test_captures tests.test_threat_effects -q` | Passed; extreme integer bounds, malformed/unknown/duplicate JSON, interleaving and enablement included |
| Terminal precedence / tactical protection / public input safety | `python3 -m unittest tests.test_tactics tests.test_iterative tests.test_player tests.test_provided tests.test_integration -q` | Passed; terminal ±10000/0 bypass leaves, mandatory wins/defenses survive caps, negative heuristic weights cannot override exact results |
| Cancellation / cache invalidation / fixed-tree search | `python3 -m unittest tests.test_transposition tests.test_search tests.test_measurement tests.test_threat_effects -q` | Passed; canceled leaf work is not exact, changed configs match fresh engines, cold/warm/uncached alpha-beta agree with reference on frozen trees |
| Controlled costs and strength comparisons | `python3 -m verification.evaluation_acceptance summary` | 76 traces hash-checked/replayed; [development](verification/issue-22/development.json), [integration](verification/issue-22/integration.json), [ablations](verification/issue-22/ablations.json) |
| Saved configuration, independent agents, restored versions | `python3 -m verification.checkpoint --output .scratch/restoration.json` | Verified from fresh temporary Git archives under isolated `-I -S` Python; [record](verification/issue-23-restoration.json) |
| Standard-library/offline engine | `python3 -I -S verification/offline_engine.py --iterative` | Passed; no site packages and Python socket operations denied |
| Public timing | 48 probes in [development evidence](verification/issue-22/development.json) | **Partial:** four dense 0.5 ms calls exceeded their incoming budget; neither evaluator has unconditional tiny-clock acceptance |
| Competitive SimplePlayer gate | Eight empty-board games, four per color, 60000 ms cumulative per player | **Failed: 0/8 for both versions.** Full v1 remains experimental; TA/class-rank performance is unknown |
| Provenance/disclosure | AI source comments, supplied-source hashes, Git history and attribution below | User explicitly waived new prompt/response recording; complete local submission transcripts are **not verified** |

Fresh #23 oracle commands and validation are recorded in
[acceptance](verification/issue-23.md) and [oracle checks](verification/issue-23-oracles.json).
Earlier complete oracle outputs remain retained at the links above. No expected
labels were changed to fit the new evaluator.

## Actual schema and provisional parameters

Saved JSON contains exactly `feature_version`, `coefficients`, `enabled_families`.
Five backward-compatible versions exist: `material-v1`, `lines-v1`, `potential-v1`,
`capture-v1`, `effects-v1`; each later version includes prior families. Full v1
requires these **24** coefficient names; each is a built-in integer in [-4000,4000].
Booleans/floats/NaN/infinity/unknown/missing/duplicate names are rejected. Negative
weights are supported experiments, not approved strategic preferences.

| Family | Full-v1 coefficients (provisional) |
| --- | --- |
| material | `material=1` |
| lines | `open_four=300`, `closed_four=100`, `broken_four=150`, `geometric_completion=0`, `verified_win=300`, `overline_trap=-20` |
| potential | `open_three=40`, `broken_three=25`, `two_stone=5` |
| captures | `capture_move=30`, `capture_pair=10`, `multi_pair_move=20`, `vulnerable_pair=-40` |
| effects | `capture_break_four=120`, `capture_break_potential=20`, `capture_create_four=80`, `capture_create_potential=15`, `capture_remove_blocker=25`, `capture_expose_five=-300` |
| multiplicity | `geometric_multiple=0`, `verified_multiple=50`, `offensive_opportunity=60`, `defensive_urgency=100` |

Full v1 enables all six families. Any supported subset is valid; categorical
enablement differs from setting a weight to zero, including runtime and identity.
Legacy versions reject non-default unsupported fields. Full feature definitions,
inspection shape and caveats are in [the versioned contract](evaluation.md).

Canonical maximal lines run right, down, down-right and down-left once, never also
in reverse. Edges block endpoints. Four units count runs/gaps rather than sliding
five-window substrings; completions deduplicate coordinates across axes. Potential
counts canonical stone sets on one axis, not every supporting window. Captures
check eight rays and deduplicate sorted unordered pairs; capture effects count
unique legal moves per condition rather than captured stone multiplicity. Fours,
verified endpoints, material, capture opportunities/risks and multiple effect
bonuses overlap deliberately. In this geometry, signed vulnerability is the
negative of signed captured pairs, so their weights combine algebraically.
Multiplicity counts endpoints, not independent threats. A shared capture defense,
own defender win or draw refutes independence at the immediate-reply horizon.

Scores are black-centric family differences, with side-sensitive opportunity/
urgency definitions preserving color/context inversion. Search negates for white.
Exact integer weighted sums clamp symmetrically to [-4000,4000]; inspection exposes
raw total and saturation. Terminal winner/loser scores are ±10000 and draws zero,
resolved after captures and before heuristic evaluation. There is no mate distance
or capture-count victory condition. A scalar is neither a probability nor solved
minimax value.

Canonical JSON sorts keys, uses compact separators and ASCII, and includes every
supported coefficient and enabled family. `identity` is SHA-256 of canonical JSON,
excluding the newline appended by saving. Whitespace/key order do not change it.
Frozen configs can be shared; engines, tables and per-turn diagnostics cannot.
Config installation changes evaluator identity and clears cached scores/hints;
invalid installation leaves the prior engine intact. Switch between searches,
not concurrently inside one. Side/depth/policy and existing namespace identities
also govern table compatibility. No incremental feature cache was adopted.

## Evidence, limitations and next work

[Issue #22](verification/issue-22.md) is authoritative for profiles, scores,
completed depths, evaluation calls, fallback frequency, starts/seeds/source hashes,
color outcomes, duplication, public timing and measured adapter coupling. Fixed
reference trees, iterative node budgets and equal real-clock games are separate
routes. The rich evaluator had roughly 37–187 ms selected fixed-tree cost versus
0.4–0.7 ms for material; capture effects dominated sampled cost. Shared scans are
not independent family timings. Removing effects reduced fixture cost but did not
improve selected bounded game outcomes. There was no measured engine optimization.

Both evaluators won 8/8 against supplied RandomPlayer and lost 0–8 against
SimplePlayer. Full v1 lost 0–8 against immutable Phase 2. Deterministic repeated
sequences are duplicate evidence. All 76 games terminated without observed cap,
crash, illegal move, mutation or clock exhaustion; this does not erase tiny-clock
probe failures. The Phase 2 subprocess incurs charged import/JSON/diagnostic costs,
so comparisons are not a perfectly symmetric strength estimate.

Representative successes: both-color RandomPlayer wins; checked strict wins and
capture-based defense `(7,7)` survive candidate caps. Representative failures:
retained `issue-15/official-simple-black-20261009.json.gz` and the newer SimplePlayer
losses; v1's many zero-completed-depth returns. Replay proves final exact-five
loss, not the decisive strategic mistake. Evaluation weakness and horizon limits
remain hypotheses. **Prioritize bounded SimplePlayer loss diagnosis and useful
completed search before spending on larger experiment volumes.** This guidance
does not start diagnosis, tuning, a tournament framework or packaging in #23.

Input and ancestor positions remain immutable through captures, nested search,
cancellation and exceptions. Interrupted expensive inspection publishes no partial
score/features; production propagates `SearchCancelled`. Completed siblings may
remain cached, but unfinished work is never exact. Keep these invariants during
later profiling or infrastructure changes.

Recovered Player inheritance, explicit color, `(row,column)` and nested board
indexing were checked against supplied sources. Pending: actual professor game
manager and its concrete board/runtime; how unlimited CLI `-1` reaches the player;
grader hardware/Python; final team suffixes/metadata and submission packaging.
Locally `-1` is bounded by the existing time policy. No Renju/repetition rules,
search extensions, new ordering, league, holdout or evolution were introduced.

## Restoration and portable use

Verified Phase 2: `798963cae696eead8353232d1cc8c289cce473a9`.
Verified Phase 3 engine/evidence checkpoint:
`105a8f64edaeb86082425c1fecb12932c06c4367` (#22).
The #23 acceptance-tool/docs checkpoint is its implementation commit, locatable
with `git log --format='%H %s' --grep='Verify Phase 3 acceptance and preserve its handoff (#23)'`.
All are immutable Git objects; avoid restoring over a working tree with user edits.

```sh
# From the repository root; this removes no existing files.
python3 -m verification.checkpoint --output .scratch/restoration.json
# Optional: verify a later checkpoint that still contains the Phase 3 engine.
python3 -m verification.checkpoint --phase3-ref HEAD --output .scratch/current-restoration.json
# Restore the entire documented environment to a separate checkout.
git worktree add --detach ../omok-phase03 105a8f64edaeb86082425c1fecb12932c06c4367
cd ../omok-phase03
python3 -m unittest tests.test_evaluation tests.test_threat_effects -q
python3 -m verification.evaluation_acceptance summary
```

The default restoration command needs local Git objects and Python standard
library only. It archives `omok`, `players`, and Phase 3 `configs` into fresh
temporary directories, hashes their contents, verifies unchanged provided sources,
loads/inspects all five presets, round-trips identities, and exercises legal
zero-clock calls for both colors plus separate-agent config switching. This
restoration probe is a bounded compatibility check; tactical strength and
cancellation have the separate tests listed above. Temporary files are cleaned.

To load and inspect without writing a board file:

```sh
python3 - <<'PY'
from omok.evaluation import EvaluationConfig, ConfiguredEvaluator
from omok.player import IterativePlayer
from omok.simulator import Position
config = EvaluationConfig.load('configs/effects-v1.json')
print(config.identity, config.canonical_json())
print(ConfiguredEvaluator(config).inspect(Position.empty()))
black, white = IterativePlayer(0, evaluation_config=config), IterativePlayer(1, evaluation_config=config)
# Each player owns its engine/table; sharing the immutable config is safe.
PY
```

For a board JSON with `board` and explicit `side_to_move`, run
`python3 -m verification.evaluation --config configs/effects-v1.json --position board.json`.
For new bounded comparisons use a fresh output directory; never combine changed
configurations/opponents with resumed evidence. The next phase must load frozen
configs, preserve feature meanings and retain the material baseline.

## Attribution and disclosure

Engine, verification and offline tooling carry AI-written-code comments. Supplied
RandomPlayer/SimplePlayer remain unchanged; `players/player.py` is the unchanged
base recovered byte-for-byte from their local supplied release (provenance in
[issue #7](verification/issue-7.md)). The assignment rules and public API come from
the user-supplied Project1 and Tips materials/master specification; the Tips'
Othello examples are not Omok++ rules. No classmate agents or external algorithm
source code were incorporated in this phase.

Earlier visible interaction records remain in Git history. At the user's explicit
request, #16–#23 created no new prompt/response files. Existing local transcript
deletions were left untouched; complete local transcripts and final disclosure
are not claimed verified. Do not invent or reconstruct exchanges for submission.
Resolve the required disclosure under the user's direction before final packaging.
