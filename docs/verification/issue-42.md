# Issue #42 acceptance evidence

AI-written by OpenAI Codex under Phase 5 (#35), master #1.

Implemented [validation and practical official-clock eligibility](../promotion.md)
at the agreed optimizer execution/results boundary. The incumbent stays retained;
an eligible candidate is only an input to the later promotion transaction.

| Acceptance requirement | Evidence |
| --- | --- |
| Policy saved before decisions | Write-once promotion policy and `eligibility.json`: validation cadence/coverage, incumbent sample and score floor, diverse-league gain, family/matchup/history/color limits, failure/completion and clock margins |
| Explicit balanced validation outside fitness | Separate validation-purpose jobs for confirmed finalists and incumbent; duplicate-aware pairing and score scope exclude validation from routine fitness/mutation |
| Prior exposure and limited independence | Required source-pointer exposure history, retained previous checks and per-attempt logs; Phase 4 validation use disclosed; always `untouched_final_evidence: false` |
| Eight-game practical official checks | Actual restored incumbent: eight empty-board alternating-color games, 60,000 ms per player, one game worker, stopped Python experiments, recorded power/load and execution segments |
| Screening/completion/clock distinction | Reduced-clock validation and artificial fixtures explicitly distinguished; official jobs require rules completion and residual clock reserves; caps remain unresolved |
| Reliability and tactical veto | Saved restoration/score/mandatory-tactic gates, all candidate failures in current/prior validation and retained training stages, including historical rounds |
| Generalization/regression rejection | Final saved margins apply to both broader selection and fresh confirmation, plus validation, per-color and practical timing evidence |
| Optimizer holdout and role protection | Training-only proposal/evaluation declarations; check declarations only allow training/validation purposes; snapshot identity and family/origin guard reject reserved candidate role switches |
| Feasible and adverse controlled scenarios | Seventeen promotion-boundary tests demonstrate eligible-without-promotion, validation/history/family/color/timing regressions, earlier training failures, tactical failures, sparse/capped/missing/incomparable evidence, policy integrity and stop/resume |

The two-axis [review](issue-42-review.md) corrected two evidence-retention defects:
fresh-confirmation regressions could use looser earlier margins, and old training
round failures could disappear from final eligibility. Both reviewers rechecked the
corrections and reported zero remaining findings.

The final-source pilot completed in **36.596 seconds**. Four balanced validation
games against the already exposed `synthetic-defensive` design completed, with
**2/2 black wins and 0/2 white wins**. This is limited development evidence with a
visible color weakness, not an untouched generalization claim. The incumbent audit
checks completion/reliability; it does not declare improvement from these results.

The eight empty-board official-clock games against `smoke` all completed under the
rules, with **4/4 wins in each color**, zero observed candidate failures in eight
committed attempts, and minimum incumbent remaining clock **58,880.750 ms**.
All twelve validation/official traces replayed successfully. This smoke opponent
audit demonstrates practical total-clock execution and completion, not diverse
official-budget strength, professor-bot qualification or tournament rank. No
candidate was promoted and no holdout was executed.

Execution used CPython 3.14.8 on Windows 10 / AMD Ryzen 3 3300X, one game worker
and fresh player subprocesses. The Windows Balanced power scheme was recorded;
no battery was reported and AC-line telemetry was not independently available.
Observed CPU load was 7% before dispatch, with no other Python experiment processes.
Other desktop activity remained uncontrolled. Complete segment conditions and
diagnostics are retained. The earlier pre-correction pilot also passed, but the
delivered artifacts contain the rerun on corrected source.

See the [summary](issue-42/pilot-summary.json) and compressed
[policies, declarations, gates, checkpoints, attempts, reports and traces](issue-42/pilot-evidence.json.gz).

```sh
python -m unittest discover -s tests -v
python -m mypy omok offline --follow-imports=silent
python -m compileall -q omok offline verification tests
git diff --check
```

At resumed handoff, the focused promotion suite passed **17 tests in 354.114
seconds**, and the full regression suite passed **323 tests in 850.099 seconds**.
Typechecking passes all 40 `omok`/`offline` modules; compilation and diff checks
pass. No LLM-usage records were created, as requested. The implementation is on
the current branch; no push or final-holdout evaluation is part of this issue.
