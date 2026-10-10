# Issue #37 review

AI-written by OpenAI Codex. Review fixed point:
`df4eb4a2b67607735fc7f6a9d559d00e6284028b` (the starting HEAD).
The two-axis code-review skill reviewed the staged task diff before committing;
pre-existing user changes were excluded. Sources: issue #37, master issue #1,
parent issue #35, repository agent instructions and documented contracts.

## Standards

The independent Standards reviewer found no documented-standard violations or
blocking correctness problems. Standard-library dependencies, AI attribution,
approved public seam tests and unchanged engine/rule/tactical sources conform.
One optional naming heuristic was raised: `at` did not describe its nested
mutation-target lookup. It was renamed `resolve_mutation_target`.

Final Standards: **0 hard violations, 0 unresolved heuristics**.

## Spec

The independent Spec reviewer identified misleading independence evidence: an
initial test constructed multiple players in one interpreter through the private
worker-only loader. That loader replaces imported checkpoint modules and is
designed for one player per isolated worker. The initial assertion could pass
with a missing configuration identity.

The test now uses registered candidate-versus-candidate games at the approved
execution seam. Both expected non-null configuration IDs must survive every
alternating turn. Worker PIDs must differ, workers must be reaped, replay must
succeed, and repeated games create fresh players. The reviewer confirmed this
matches the existing fresh per-game adapter contract and resolves the finding.

The policy also pins registry adapter source hashes before generation. Changed
adapters require a new policy; the same saved policy cannot silently produce
new candidate entry identities. The Spec reviewer verified this correction.

Final Spec: **0 remaining findings**, no scope creep. Fitness, selection,
promotion and final holdout evaluation are outside this ticket.

Final summary: Standards 0 unresolved; Spec 0 unresolved.
