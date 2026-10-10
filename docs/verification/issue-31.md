# Issue #31 acceptance

AI-written by OpenAI Codex. Context: master #1, phase 4 #24. No LLM usage records
were created, as requested. Engine, evaluation and search policy are unchanged.

The already agreed complete runner/replay operation is the acceptance seam.
Tests first demonstrated rejection of the old output version and the absent
inspection module, then passed with implementation. See [the API/schema and
commands](../replay.md). New supervised traces use v4; valid v1–v3 readers remain.

[Saved evidence](issue-31/summary.json) includes 16 unchanged v3 games from issue
#30 replayed without agents, three fresh v4 supervised exception/exit/timeout
traces and their preceding-position exports, and independently checked normal,
capture-induced opponent-win and simultaneous-win rule fixtures. Each execution
failure exported ply 1 with an ongoing board; none fabricated a board winner.
All three fixture expectations agreed with the independent reference.

Verification:

```powershell
python -m unittest tests.test_loss_inspection tests.test_replay tests.test_supervised -q
python -m verification.loss_inspection --output docs/verification/issue-31
$env:PYTHONPATH='.scratch/typecheck-tools'
python -m mypy omok offline verification/loss_inspection.py --follow-imports=silent
python -m compileall -q omok offline verification tests
python -m unittest discover -s tests -q
```

Targeted checks passed **31 tests**, mypy passed **34 modules**, and compilation
passed. Export tests cover saved identity/options, preceding moves, clocks,
diagnostics evidence, strict selection bounds, corrupted/truncated evidence and
rejection of unchecked or execution-only board expectations. Automatic tags are
hypotheses; there is no alternative search or best-move assertion. Fixtures use
an independent oracle to check an explicitly supplied recorded-move rule result.

Independent [two-axis review](issue-31-review.md) passed with **Standards 0;
Spec 0** remaining findings. Review found and corrected unattributed infrastructure
selection and cleanup evidence with unavailable timing/exit status. The public
trace regression includes a started, unreaped worker; null/missing lifecycle
observations require an explicit cleanup-error explanation.

Final full-suite run passed **238 tests in 186.814 seconds** with source files
stable. Compilation, typechecking and staged whitespace checks passed. Earlier
full runs passed 237 tests before the infrastructure regression and 238 tests
before the final started-worker cleanup refinement. The final run includes all
fixes. CLI export, explicit rule confirmation and standalone fixture verification
also passed against the saved evidence. No candidate tuning or holdout play was
performed.
