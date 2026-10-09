# Issue #19 implementation review

AI-written by OpenAI Codex. The code-review skill ran independent parallel
Standards and Spec reviewers. Baseline:
`c7fe1216126f3dfc1dcc58fc434cac8e099ab10a`; comparison:
`git diff c7fe1216126f3dfc1dcc58fc434cac8e099ab10a...HEAD`.
Reviewed implementation commit: `9fb2736`.

## Standards

No hard documented-standard violations found. Immutable simulator transitions,
cooperative cancellation, score bounds, configuration isolation, and
separate development inspection follow the documented contracts.

One optional judgment call: possible Repeated Switches, `omok/evaluation.py`,
version/family validation, serialization, loading, feature collection and
inspection repeat `in (POTENTIAL_VERSION, CAPTURE_VERSION)` and
`== CAPTURE_VERSION` decisions. A single immutable version-to-supported-families
map could keep these synchronized when another family is introduced, preserving
older schemas and identities. This is a maintenance heuristic, not a correctness
defect or required change; the implementation follows the existing design.

Disposition: defer this optional schema refactor to the next feature-family
change. Keeping the current version checks avoids broadening #19 without a
correctness need. No unresolved hard violation.

Standards: 0 hard violations, 1 optional maintenance finding.

## Spec

No Spec findings for issue #19.

The implementation covers canonical capture moves/pairs/cells, multi-pair
multiplicity, actual vulnerability, both colors and eight rays, simulator-derived
outcome labels, independently configurable opportunity/risk weights, cancellation,
configuration isolation, matched-tree search and public turns. Definitions and
provisional parameters are recorded separately; Phase 2 remains available and
unchanged.

The reviewer independently ran `python3 -m unittest tests.test_captures -q`:
all 8 tests passed, and reviewed independent oracle verification and evidence.
Capture-effect scoring and broader Phase 3 strength comparisons remain explicitly
deferred; they are outside this issue's bounded scope.

Spec: 0 findings.

Validation: 27 focused tests, 146 full-suite tests, 18-file typecheck, syntax and
whitespace checks passed. The independent oracle checked 5,958 legal transitions.
Isolated standard-library-only iterative-player verification also passed.

Standards: 1 optional maintenance finding, no hard violation. Spec: 0 findings,
no outstanding correctness issue.
