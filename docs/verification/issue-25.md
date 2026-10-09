# Issue #25 — bounded persistent player workers

AI-written by OpenAI Codex. No LLM usage records were created, as requested.

Implemented fresh per-game, persistent per-player Python subprocesses, bounded
setup/call/cleanup, separate bounded stdout/stderr, exact cumulative envelope
clocks, worker-observed input mutation, distinct execution/resource/setup reasons,
and replay-compatible v3 traces. The normal offline CLI uses this route. The engine,
provided source files, evaluator configurations and material default are unchanged.
See [the policy and API](../runner.md#supervised-games-issue-25).

Prerequisite verification: 86 rules/reference/differential, public-player ownership,
iterative cancellation, search, transposition, evaluator and supplied-player tests
passed. Both archived versions restored successfully using
`python3 -m verification.checkpoint --output .scratch/issue-25-restoration.json`:
Phase 2 `798963cae696eead8353232d1cc8c289cce473a9`, Phase 3
`105a8f64edaeb86082425c1fecb12932c06c4367`. No prerequisite defect was found.
Previously documented SimplePlayer qualification and tiny-clock limitations remain
separate from infrastructure acceptance; no strategy changes were made.

13 runner-seam tests cover fresh/persistent state, controlled cumulative accounting,
rounding, exact exhaustion, late replies, zero clock, terminal starts, capture-induced
opponent win and simultaneous draw, real looping/sleeping workers, exception, exit,
mutation, malformed/occupied moves, native stdout/stderr flood, setup timeout/import
errors, supervisor launch failure and a successful game after nonreturning workers.
Every exercised process was reaped. Late exceptions retain their diagnostics under
a timeout result; cleanup errors retain and replay the prior execution ledger. A flood retained 1,024 bytes per stream from
524,288 observed bytes per stream without corrupting the protocol.

Real CLI checks on Python 3.14.3/macOS, one sequential game with two player processes:
configured search against actual RandomPlayer on `mover-win` completed an exact-five
black win in one move; baseline against actual SimplePlayer on `dense` completed a
full-board draw in one move. These are artificial rules fixtures, not strength
measurements. Both traces replayed. An additional empty-board baseline-versus-seeded-smoke game
(seed 20261010) completed with a black exact-five win after 19 moves and replayed. There is no strategic win-rate gate in this ticket.

Commands:

```sh
python3 -m unittest tests.test_supervised -q
python3 -m unittest discover -s tests -q
python3 -m compileall -q omok offline verification tests
.scratch/issue-21-tools/bin/python -m mypy omok offline --follow-imports=silent
python3 -m offline --engine search --opponent random --fixture mover-win --max-depth 1 --diagnostics --move-cap 4 --output .scratch/issue-25-search.json
python3 -m offline --opponent simple --fixture dense --move-cap 4 --output .scratch/issue-25-simple.json
python3 -m offline --replay .scratch/issue-25-search.json
python3 -m offline --replay .scratch/issue-25-simple.json
```

Typechecking passed for 24 source files. The first full-suite run exposed a test
fixture import name that only worked with module-targeted unittest invocation;
using the canonical `tests.test_supervised` path fixes discovery mode as well.
Final full-suite and review results are recorded in the accompanying review report.

Windows execution is not measured in this session; subprocess/TCP/thread mechanisms
are portable, without Unix-only signal enforcement. This is not a security sandbox.
Tournament schedules, match scoring, registry management and batch persistence are
follow-up tickets under #24 and were not added here.

Final verification: **178 tests passed** (38.213 seconds), all 24 typechecked source
files passed, compilation and diff whitespace checks passed. Both independent
review axes have zero remaining findings after fixing two replay defects. See
[the review report](issue-25-review.md).
