# Issue #23 — Phase 3 acceptance and checkpoint

AI-written by OpenAI Codex. Ticket: “Verify Phase 3 acceptance and preserve its
handoff.” Master context: GitHub issue #1. No new LLM-usage records were created,
following the user's explicit instruction. Existing local changes were preserved.

## Outcome

The [handoff](../phase-03-handoff.md) now maps every required family and acceptance
gate to definitions, code/presets, fixed fixtures, runnable commands and retained
evidence. It records the actual 24-coefficient schema, provisional weights/ranges,
orientations/counting/overlap, enablement, context/sign/bounds, serialization and
cache identity without rewriting the specification.

**Engineering verification passed; competitive acceptance remains unmet.** The
default remains Phase 2 material; all five new families remain implemented and
verified, but only contribute when explicitly enabled in a configured evaluator.
Both tested versions lost all eight SimplePlayer games. No improvement against
SimplePlayer is implemented or claimed by this documentation/checkpoint ticket.

## Fresh verification

[Restoration evidence](issue-23-restoration.json) comes from actual fresh Git
archives of Phase 2 `798963cae696eead8353232d1cc8c289cce473a9` and Phase 3
`105a8f64edaeb86082425c1fecb12932c06c4367`. Isolated `-I -S -B` subprocesses import
only the restored engine path plus standard library. Archive and extracted source
hashes are recorded; all three supplied-source hashes agree across checkpoints.
The probe loads/inspects all five configs, round-trips canonical identities,
checks one open four/two strict completions, terminal score 10000, independent
agents/config switching, and legal immutable-input calls in both colors. Those
calls deliberately use zero-clock fallback; stronger tactical/cancellation tests
remain separate and are linked in the handoff. Restoration is not packaging.

A new public verification-command regression was written before the command
implementation. It first failed because the module did not exist; the implemented
command then passed its literal feature labels, retained material score and public
isolation expectations. The targeted evaluation file passes six tests.

[Fresh oracle command record](issue-23-oracles.json) records successful potential,
capture and capture-effect/multiplicity verification with one timing repetition,
serially. Their assertion-backed independent labels and full previously retained
suite outputs are linked in the handoff. Timing durations here describe command
execution, not calibrated engine-family cost. Existing #22 sampled profiles are
retained without pretending they were remeasured in #23.

`verification.evaluation_acceptance summary` again hash-checked/replayed all
**76** saved traces. #22's controlled trees, node-budget results, both-color
60000 ms cumulative-budget games, ablations, duplicate counts, default decision
and source/settings/hardware remain the strength/cost evidence. Those games were
not rerun or counted as additional independent samples. In-process versus
checkpoint-subprocess charged IPC remains explicit.

Engine/offline imports passed isolated execution with site packages disabled and
Python socket operations denied. Typechecking passed for 21 files; compilation
passed. The full suite and two-axis review are recorded in
[the review report](issue-23-review.md).

```sh
python3 -m verification.checkpoint --output .scratch/restoration.json
python3 -m verification.potential --repetitions 1
python3 -m verification.captures --repetitions 1
python3 -m verification.threat_effects --repetitions 1
python3 -m verification.evaluation_acceptance summary
python3 -m unittest tests.test_evaluation -q
python3 -m unittest discover -s tests -q
python3 -m compileall -q omok offline verification tests
python3 -I -S verification/offline_engine.py --iterative
# A development-only mypy environment is available locally; it is not an engine dependency.
.scratch/issue-21-tools/bin/python -m mypy omok offline verification/checkpoint.py --follow-imports=silent
```

Commands run from the repo root; the restoration command needs local Git objects
and standard-library Python, not the original machine's absolute paths or network.
Source extraction is temporary and does not overwrite the working tree. A detached
worktree command in the handoff restores the full existing evidence environment.

## Limitations and next-phase boundary

Cancellation, input restoration, table invalidation and tactical protection pass
the retained regressions. Zero observed game failures do not establish tiny-clock
reliability: dense 0.5 ms calls exceeded incoming clocks in #22. Actual professor
manager/board/runtime, unlimited-time translation and grader hardware remain
unverified. Team suffixes, metadata, packaging and full disclosure are deferred.

Earlier prompt/response records remain in Git history; the user waived new
recording and has local transcript deletions. No missing conversations were
fabricated and complete local disclosure is not claimed verified. AI code comments
and accurate supplied Player/RandomPlayer/SimplePlayer acknowledgments remain.

The next work should prioritize bounded diagnosis of SimplePlayer losses and
completed-search utility before scaling batches. This issue does not start that
work or implement leagues, evolution, extensions, tuning or packaging. Engine,
clock/ranking/tactics, rules, configurations and supplied bots are unchanged.
