# Phase 3 handoff

AI-written by OpenAI Codex for issue #22. No LLM-usage records were created.

The complete evaluator is **experimental**. The default remains Phase 2 material
(black occupied cells minus white), because the full evaluator regressed against
the immutable Phase 2 opponent and frequently failed to complete depth one at the
existing clock allocation. See [comparison evidence and limitations](verification/issue-22.md).
This is engineering acceptance with a conservative default decision, not hidden
TA or competitive-strength acceptance. Tiny-clock reliability remains partial.

[Evaluation contract](evaluation.md) defines each family, overlaps, context,
provisional integer weights/ranges, inspection and configuration identity.
`configs/effects-v1.json` preserves the complete checked feature schema: material,
lines, smaller potential, capture opportunities/vulnerabilities, capture effects,
and endpoint multiplicity. Geometric endpoint counts do not prove independent
threats; verified captures/outcomes use actual rules. Positional influence remains
deferred. All older versioned configurations remain available.

Scores are black-centric, negated for white by search; nonterminal values clamp
symmetrically to [-4000, 4000], below terminal magnitude 10000. Terminal draws score
zero and bypass heuristic calls. Canonical configuration SHA-256 plus existing
search policy identity segregates cached values; installing a configuration clears
scores and hints. Immutable positions and cooperative cancellation remain intact;
there is no incremental feature cache. All families remain implemented even
though none of the new families contributes to the material default.

[Measurement contract](measurement.md) explains evaluation-call and cancellation
counters, sampled cost attribution and frozen-tree versus real-clock routes.
Capture-effect recomputation is the measured bottleneck. Shared lines/potential
scans and multiplicity's endpoint dependency prevent independent attribution of
all scan costs. No measurement-driven engine optimization was made.

`python3 -m verification.evaluation_acceptance` provides gated, bounded development,
real-clock, ablation and replay-summary commands, with per-game checkpoint/resume.
There is no opponent registry, league, promotion service, holdout consumption, or
optimizer. Future infrastructure must preserve these feature definitions,
configurations, clock/search settings and the distinction between experimental
and default behavior. Parameter tuning is future work, not evidence already shown.

The retained Phase 2 checkpoint is
`798963cae696eead8353232d1cc8c289cce473a9`. Restore an immutable engine with
`git archive <checkpoint> omok`; the comparison tool isolates its imports in a
subprocess and reports charged IPC overhead. The issue #22 implementation commit
is the Phase 3 engineering checkpoint, obtainable via `git log --grep='(#22)'`.
Supplied RandomPlayer/SimplePlayer and recovered Player inheritance were checked;
the actual grader Python/runtime and concrete manager remain unverified. Final
team suffixes, submission metadata, packaging and disclosure are deferred.
