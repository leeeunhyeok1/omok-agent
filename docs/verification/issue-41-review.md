# Issue #41 review

AI-written by OpenAI Codex. The implement skill requested code-review. Both axes
ran in separate parallel agents against the staged change from the session's
starting commit `069a9749109f00b98ccc48ead7d2ffc06cf326c2`, before committing.

## Standards

Initial review: no hard documented-standard violations or material correctness
hazards. One minor possible Duplicated Code finding identified repeated selection
assessment dispatch in preparation, validation and final reporting. The shared
`assess_selection` helper resolved it.

Final reviewer report: "The shared `assess_selection` helper resolves the
duplication finding. The resume guard preserves previously exported attempt
evidence and execution conditions before dispatch. Final Standards review:
0 findings; no material maintainability or correctness hazards identified."

## Spec

Initial review found that a restored older valid child checkpoint could silently
erase already exported completed attempts. The reviewer reproduced a decrease
from four recorded attempts to one on a zero-job resume. This could hide coverage
and reliability evidence.

Before any dispatch, resume now requires all previously exported attempts and
execution-segment conditions to remain present and unchanged, permitting normal
running-to-interrupted recovery and additive progress. The public resume test
exercises an older valid checkpoint and a deleted checkpoint.

Final reviewer report: "The checkpoint rollback finding is resolved. The focused
real-dispatch test passed: restoring an older valid checkpoint now raises an
authoritative-evidence error before dispatch; missing checkpoints are also
rejected. The fix preserves previously exported attempts and execution conditions
while allowing legitimate progress. No remaining Spec findings."

Final counts: Standards **0 unresolved findings**; Spec **0 unresolved findings**.

Both reviewers also rechecked the final opening-state correction: freshness and
dependence blocks use board plus side to move, so different legal opening orders
cannot inflate deterministic evidence. The new public preparation regression
passed; both axes still report zero findings.
