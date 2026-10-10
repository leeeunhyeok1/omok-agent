# Frozen synthetic opponents

Issue #30 adds nine locally authored benchmark entries to the default registry.
All are offline-only, standard-library players with explicit constructor color.
They share the simulator's placement/capture/terminal semantics, never candidate
search, tactics, or evaluator code. No external strategy was copied. Source
acknowledgment is OpenAI Codex; no classmate or hidden TA source is required.

| ID suffix (`synthetic-`) | Decision rule | Family | Pool |
| --- | --- | --- | --- |
| local | Most own neighbors in a 3x3 neighborhood | local-density | training |
| aggressive | Own longest maximal run, excluding overlines | line-pattern | training |
| pattern | Most unblocked four/three windows of five, including gaps | line-pattern | training |
| capture | Most cells actually removed by a legal capture | capture-collection | training |
| search1 | One-ply cubic maximal-run balance | reply-minimax | training |
| search2 | Worst opponent reply at two plies | reply-minimax | training |
| random | Uniform seeded adjacent-frontier choice | frontier-random | training |
| defensive | Fewest actual winning opponent replies, then least opponent run pressure | reply-denial | validation |
| space | Greatest distance from occupied cells | space-filling | holdout |

Local density ignores tactics. Aggressive, pattern and capture first prefer an
actual own rule win and avoid moves producing an opponent rule win; among other
results they use their named policy. Pattern windows are heuristic opportunities,
not verified forced threats. Defense checks all adjacent legal replies after
captures, allowing capture defenses as well as direct blocks. No capture-count
victory condition is used. Ties prefer Manhattan distance to the center, then
stable row/column order. Draws have neutral value in minimax.

Except space, candidates are all empty cells adjacent (Chebyshev radius one) to
an occupied cell, with center on the empty board. Search ranks these with its own
static evaluator and keeps eight plus every immediate own-win/opponent-win cell.
It does not import candidate search. Search1 and search2 are depth variants of
one design, **not independent designs**. Aggressive/pattern share line-oriented
ancestry and are grouped conservatively. The search family also reuses maximal-run
measurement; both families stay in training. Random uses its own `Random(seed)`,
with sorted candidates, independent of process-global RNGs. Existing `smoke` is
uniform whole-board random and already development-exposed, not a reserved design.

There are seven declared families across the nine new entries, six accessible in
development. This is limited local coverage: shared authorship, rules, source
bundle, simple line utilities and center ties create correlations even across
different families. Family labels do not establish statistical independence or
simulate hidden TA behavior. These opponents are deliberately small behavioral
probes, not promised strong agents. The single reserved space-filling family has
limited strength coverage and remains unused by the acceptance run. Defensive
fixtures/games are disclosed validation exposure; they are not optimizer fitness.

`Entry.local` freezes exact source hashes, strategy configuration, dependency list,
Python runtime, adapter identity, acknowledgment and variant. Each source bundle
contains offline code and only the simulator and package initializer from `omok`.
Frozen JSON is an identity, not an archived source distribution: preserve the
commit/tree (and retained Git objects). Source or adapter edits require a new
registration and cannot replay as the old immutable opponent. There are no third
party dependencies. Keep `offline/`, `verification/`, opponents and benchmark
records outside eventual submitted agent imports/artifacts.

The default registry includes real holdout metadata. Default development plans
exclude it; explicit development selection (including as candidate) is rejected.
Only `final-evaluation` permits competitive selection. Metadata freeze is allowed;
do not run tactical tests or smoke games against space during development. Do not
interpret tests of the pool exclusion rule as exposure of its strategy.

```powershell
python -m offline.registry_cli freeze --output .scratch/synthetic-registry.json
python -m offline.experiment_cli plan --registry .scratch/synthetic-registry.json --candidate phase2 --opponent synthetic-local --opponent synthetic-defensive --mode screening --games 2 --total-ms 5000 --move-cap 12 --output .scratch/synthetic-plan.json
python -m offline.experiment_cli run --plan .scratch/synthetic-plan.json --output .scratch/synthetic-run
python -m verification.synthetic --output .scratch/synthetic-evidence
```

Use new output paths for each freeze/evidence run. The verification command checks
ten controlled moves (including a nonterminal pattern/aggression contrast), then runs the unchanged retained Phase 2 candidate against
all eight development synthetic entries twice, swapping colors, seed 20261010,
5,000 ms cumulative clocks and a 12-move cap. It preserves the frozen registry,
plan, raw supervised records, replay checks and summary. Capped games are recorded
as caps, never draws or strength wins. Deterministic repeated empty-board games
with the same colors are duplicates; new seeds do not make them independent.
