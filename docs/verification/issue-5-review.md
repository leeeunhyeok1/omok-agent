# Issue #5 code review

Fixed point: `c10b3946bc18c45206f663a51c8608ddd32a2efc`, repository HEAD before work.
Implementation checkpoint: `c756458 Add verified one-ply baseline scoring and recovery checks (#5)`.
Diff command: `git diff c10b3946bc18c45206f663a51c8608ddd32a2efc...HEAD`.
The invoked code-review skill ran independent parallel Standards and Spec agents;
both reviewed subsequent fixes before the final commit was amended.

Standards sources: `AGENTS.md`, `docs/agents/issue-tracker.md`,
`docs/agents/domain.md`, `docs/simulator.md`, `docs/runner.md`, `README.md`,
the TDD skill's public-seam requirements, and the Fowler smell baseline.
Spec sources: GitHub issue #5, authoritative Phase 01 issue #2 and context issue #1.
The user's explicit instruction supersedes interaction-transcript recording.

## Standards

Initial documented breach: the deadline test overrode private `_score`, recorded
calls in `ObservingBaseline.evaluated`, and asserted that collection was empty.
The TDD skill requires tests to verify public behavior rather than internal
collaborators. The evaluator exception injection remains explicitly required by
issue #5, but the deadline test did not need this observation side channel.

Initial low-priority judgment call: possible Duplicated Code in the adjacent-own-
stone counting used by candidate priority and scoring.

Disposition: removed the deadline observation side channel, retaining controlled
clock injection and public returned-move, legal-transition, unchanged-input, and
owned-parent assertions. Shared `_own_neighbors` now centralizes neighborhood
geometry for ordering and scoring, excluding the candidate cell in both cases.

Reviewer confirmation: “Both findings are resolved. The deadline test now checks
public behavior and unchanged state, and `_own_neighbors` centralizes the repeated
neighborhood logic without changing candidate ordering or scores.”

Outstanding Standards findings: **0 documented breaches, 0 baseline smells**.

## Spec

No Spec findings. The diff satisfies issue #5's bounded one-ply scope: strict wins
use resolved simulator outcomes, simultaneous draws receive no win classification,
detected losses are excluded when a safe choice is known, scoring and ties are
deterministic, and timing includes conversion with an early legal fallback.
Exception and deadline injection verify parent/input preservation and later recovery.
Documentation identifies untuned constants, attribution, runner evidence, and pending
official integration without strength claims.

Reviewer confirmation after Standards fixes: no new Spec findings.
`_own_neighbors` preserves ordering because candidate cells are empty, and preserves
scoring by excluding the placed stone. Clock-controlled deadline tests still
demonstrate legal fallback and unchanged parent/input after conversion and child
exploration. The exception-recovery fixture remains intact.

Final validation: all **53 tests passed in 3.302 seconds** after the fixes; targeted
player/runner tests and the 18-file typecheck also passed.

Summary: Standards 0 outstanding findings; Spec 0 outstanding findings.
