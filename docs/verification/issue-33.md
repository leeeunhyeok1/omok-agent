# Issue #33 — trustworthy matchup reports

Implemented in phase 4 (#24), using master #1 and the existing complete tournament
operation as the agreed test seam. No LLM usage records were added.

The saved-evidence API and CLI produce separate latest-job, all-attempt and clean-game
views with per-color outcomes, match scoring/coins, explicit denominators, micro and
equal-opponent macro rates, weak matchups, source/family/pool coverage and duplicate
limitations. Available game length, turn/call/overhead timing, clocks and numeric
search/evaluation diagnostics retain missing values. Runtime segments have separate
timing summaries. Ratings and confidence intervals are explicitly deferred because
local samples may be small and dependent. See [the contract](../reports.md).

Seven focused tests exercise public reporting from runner-produced traces and saved
batch output: candidate crash with incomplete match, separate clean denominators,
retry retention, interrupted attempts, duplicate deliveries/conflicts, unequal
micro/macro weighting, deterministic duplicate coverage, missing/nested diagnostics,
turn-event accounting, invalid traces and changed runtime segments. The CLI test
runs a bounded batch, resumes under a changed worker count, and reports its persisted
manifest/results without invoking players during reporting.

The committed [known evidence](issue-33/known-results.json.gz),
[full generated report](issue-33/known-report.json.gz) and
[readable summary](issue-33/summary.json) use controlled rule fixtures and explicitly
synthetic segment metadata. They verify accounting, not candidate strength or measured
hardware performance. The seven observed slots contain four clean completions,
one candidate crash, one cap and one setup failure; the eighth slot remains pending.
Recognized win rate is 2/5; clean win rate is 2/4. Nine unique attempts retain an
earlier setup failure and interrupted pending job; one repeated delivery is disclosed.
The match is unresolved, candidate qualification is false due to the crash, and no
coins are awarded. Missing search diagnostics remain unavailable. The known-evidence
test reconstructs the report from the committed bytes and checks literal expectations.

Validation commands:

```powershell
python -m unittest tests.test_reports -v
$env:PYTHONPATH='.scratch/typecheck-tools'
python -m mypy omok offline --follow-imports=silent
python -m unittest discover -s tests -v
python -m compileall -q omok offline verification tests
git diff --cached --check
```

Independent [standards/spec review](issue-33-review.md): **0 remaining findings**
on each axis after removing repeated trace replay work.

Final validation on Python **3.14.8**, Windows:

- Full suite: **253 tests passed**, 240.640 seconds.
- Focused reporting tests: **7 passed**, including the persisted-result CLI check.
- All **34** `omok`/`offline` modules passed mypy.
- Bytecode compilation and staged whitespace checks passed.
- Standards **0** and Spec **0** remaining findings.
