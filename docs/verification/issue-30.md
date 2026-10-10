# Issue #30 acceptance

AI-written by OpenAI Codex. Context: master #1 and phase 4 #24. No LLM interaction
records were created, as requested. Candidate code/configuration was unchanged.

Nine frozen synthetic entries cover local density, aggression, reply denial,
actual capture collection, pattern windows, one/two-ply minimax, seeded frontier
randomness and reserved space filling. Related variants stay together. See
[behavior, provenance and limitations](../synthetic.md) and
[the independent two-axis review](issue-30-review.md).

Evidence in [the summary](issue-30/summary.json) and its adjacent gzip artifacts
preserves the exact registry/pool snapshot, resolved plan and raw supervised
records. Ten controlled moves passed, including nonterminal local/aggressive,
pattern/aggressive and one/two-ply contrasts, a unique defense, an actual pair
capture and broken-four completion. Randomness repeatability/diversity is also
checked through complete trusted games. No internals are mocked.

The retained Phase 2 candidate played each of eight development opponents once
as each color: **16 games, 10 rule completions and 6 explicit caps**, no observed
crashes, invalid moves, mutations or timeouts. Every fixture/game replayed. These
are short screening probes (5,000 ms cumulative clocks, 12-move cap, seed 20261010),
not official eight-game qualification matches or strength estimates. Runtime
was CPython 3.14.8 on Windows with serial games and two persistent player workers.
Hardware/clock observations are in the saved plan and summary.

Validation `synthetic-defensive` was exposed through named fixtures and games.
Holdout `synthetic-space` received **zero played-game or tactical exposure**.
Default scheduling exclusion and rejection of explicit development selection
were verified without calling its strategy. Its single simple design limits
holdout strength coverage. Shared source/authorship/rules/line utilities also
limit independent family coverage; declared families are not independence claims.

Verification commands:

```powershell
python -m unittest tests.test_synthetic tests.test_registry -q
python -m verification.synthetic --output .scratch/synthetic-evidence
python -m unittest discover -s tests -q
$env:PYTHONPATH='.scratch/typecheck-tools'
python -m mypy omok offline --follow-imports=silent
python -m compileall -q omok offline verification tests
git diff --cached --check
```

The targeted registry/synthetic run passed 21 tests before the extra pattern
contrast; the final synthetic run passed all nine tests. All 32 `omok`/`offline`
modules passed mypy, and bytecode compilation passed. The evidence generator also
passed mypy (33 checked modules with that target included).

An initial full-suite run (232 tests) failed one registered crash-match test while
the tests source bundle was edited to add the review-requested pattern contrast.
These fixtures hash the entire tests directory, so edits during a run invalidate
their frozen identity. The isolated crash-match test subsequently passed. A final
full-suite run with all source files fixed passed **233 tests in 188.343 seconds**.
The staged whitespace check passed. Final independent review findings:
**Standards 0; Spec 0**.

All new strategies/dependencies live offline; the candidate imports no opponents.
Frozen definitions require the preserved source tree/runtime/retained Git objects;
later source edits need new registration rather than silently changing identity.
