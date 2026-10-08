# Issue #13 acceptance — bounded transpositions

AI-written by OpenAI Codex. Implements GitHub issue #13,
“Reuse compatible search results through a bounded transposition table,” under
master issue #1. No LLM-usage records created, as requested.

## Decisions

Full immutable position keys with explicit side and Python equality collision
checks; exact remaining depth in production as well as verification; per-engine
policy namespaces plus explicit version tokens for mutable callbacks; terminal
checks before probes; fixed win scores without mate distance; no incremental hash;
FIFO replacement with protected exact values, 4096 default entries and 64-ply PV
payload limit. New-game/config resets use `table.clear()` or a new player. Complete
API and cache-contract documentation is in [../search.md](../search.md).

## Evidence

`python3 -m unittest tests.test_transposition -v` passes 10 tests at the existing
search/public-player boundaries agreed in master issue #1:

- Cached, uncached alpha-beta and unpruned scores and accepted optimal move sets
  agree across six weighted-tree seeds, both sides, depths 1–4 (including decreasing
  depth), with capacities 4 and 128. Saved lines replay legally to the horizon or
  terminal and yield the reported root score.
- Exact, lower and upper entries, bound cutoffs and effective-window classification
  are exercised through public searches. A zero lower tightening yields an upper
  entry; a zero upper tightening yields a lower entry, never a false exact result.
- Evaluator replacement/versioning, candidate replacement and tactical-policy
  changes segregate values; illegal, occupied, excluded and Boolean hints are
  ignored. Hash-colliding compatibility tokens remain distinct.
- Every node limit before a four-depth iterative completion on a capture fixture
  preserves input and committed score/move, leaves no incomplete root entry,
  retains completed children, and permits a clean reference-matching later search.
- Controlled evaluator errors propagate and callback cancellation returns a legal
  fallback; both retain only completed entries and recover on subsequent search.
- Zero capacity, small-capacity eviction, explicit resets, hint release and oversized
  PV rejection verify storage limits and correctness. The default iterative player
  uses the table and returns a legal opening move.

A local four-cell material tree at depth four took 28 node visits cold and 5 warm
(24 retained entries, score zero in both). One sequential measurement was 3.86 ms
cold and 0.29 ms warm. This tiny deterministic fixture establishes reuse, not
playing strength or a universal speedup; candidate/tactical work still runs on
nonleaf probes. Python 3.14.3 was used.

Validation commands:

```sh
python3 -m unittest tests.test_transposition -v
PYTHONPATH=/tmp/omok-issue11-typecheck python3 -m mypy --follow-imports=silent omok/search.py omok/transposition.py omok/player.py omok/tactics.py
python3 -m compileall -q omok verification tests
python3 -m unittest discover -s tests -v
python3 -m verification.search
python3 -I -S verification/offline_engine.py --search
```

The optional mypy installation is external development tooling, not an engine
runtime dependency. Final validation: **109 tests passed** in 8.95 seconds; all four
affected engine modules passed mypy; compileall, search verification, and isolated
standard-library-only execution with Python socket operations denied passed.
The isolation command exercises the fixed-depth public player and imports the new
table through the guarded engine dependency path. Review evidence is in
[issue-13-review.md](issue-13-review.md).
