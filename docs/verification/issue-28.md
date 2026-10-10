# Issue #28 acceptance — eight-game scoring

Spec: GitHub #28, “Score eight-game matches without hiding failures,” within
Phase 4 (#24), with master context #1. Starting commit:
`54242836a5915c99a37db301cd60d7e7ef2ffb2f`.

The implementation adds a separate versioned `eight-game-local-v1` scoring policy,
`offline.matches.score_experiment`, saved `match-scores.json`, and CLI rescoring.
Existing raw manifests/results retain their formats and identities. The engine,
evaluation configuration, search and agent time allocation were not changed.
The [scoring contract](../matches.md) records every local interpretation and the
[two-axis review](issue-28-review.md) records no remaining findings.

## Acceptance coverage

- All saved slots remain visible, with four assignments of each color required;
  short schedules, missing records, caps and infrastructure errors are explicit.
  Duplicate/foreign/misassigned records are rejected. Counts derive from the plan
  and actual records, rather than trusting supplied aggregate counts.
- Five strict wins and tournament win comparison are separate. Independently
  specified expectations cover 5–3, 4–3 plus draw, 4–4, 3–4 plus draw, and eight
  draws. These use one live tactical start and actual simulator moves, labeled
  fixture evidence; they do not claim official empty-board playing strength.
- Candidate and opponent crash overrides preserve both the rules scoreboard and
  recognized game wins. Both-crash ambiguity and infrastructure errors have no
  tournament coins. Candidate crashes still disqualify in unresolved matches.
- Two real supervised official-format eight-game batches verify candidate
  exceptions and opponent process exits, with all eight failure slots retained.
  Timeout, illegal move, mutation and recorded protocol failures follow the
  documented local game-forfeit interpretation, without a crash match override.
- A late exception remains a crash despite primary timeout classification.
  Cleanup infrastructure errors preserve preceding crash facts without coins.
- Available traces are replayed and matched against actual saved starts, clocks,
  cap and provenance. Unvalidated `prior_result` fields cannot fabricate crashes.
- Saved-run output, CLI partial rescoring and refusal to overwrite evidence are
  exercised through the public tournament operation.

## Prerequisite corrections found by verification

The first full run exposed three existing environment-sensitive failures:

1. Checkpoint source keys used Windows backslashes while lookups required forward
   slashes. `as_posix()` fixes report portability. The original failing checkpoint
   restoration test then passed; restored engine sources remain unchanged.
2. The batch-identity test reused historical engine byte hashes. This checkout's
   engine files differ from the frozen evidence (including checkout line endings),
   causing the source gate to reject before the intended batch-identity check.
   Only its temporary test fixtures now use current engine hashes; durable
   historical evidence and production source gates remain intact.
3. An early socket timeout could produce a timeout reason with elapsed time below
   the authoritative deadline, making replay reject the ledger. A controlled
   socket-boundary event reproduced the defect through the real supervised runner
   (0.085 ms charged against a 40-ms budget). The receiver now retains partial
   frames and continues until its monotonic deadline; no elapsed time is invented.
   The regression and all 14 supervised tests passed afterward.

The guarded optional `os.sysconf` access also uses `getattr` so the existing
Windows fallback can pass native-platform typechecking. No engine dependency was
added. Test tooling was installed under ignored `.scratch/typecheck-tools`.

## Validation

- Focused match suite: 12 tests passed, including real eight-slot process runs.
- Focused supervised suite: 14 tests passed.
- Original checkpoint restoration and batch-identity repro tests: passed after
  the narrow corrections.
- Native Windows mypy: all 30 `omok`/`offline` source files passed using
  `PYTHONPATH=.scratch/typecheck-tools python -m mypy omok offline --follow-imports=silent`.
- `python -m compileall -q omok offline verification tests`: passed.
- `git diff --check`: passed.
- Final `python -m unittest discover -s tests -v`: **212 tests passed**, no
  failures or errors. The saved final log is `.scratch/issue-28-suite-final.txt`.

No strength tuning,
class rank, rating, promotion, retry or resume claim is made by these checks.
Code and tests are AI-written by OpenAI Codex; no LLM usage was recorded at the
user's request.
