# Issue #37 acceptance

AI-written by OpenAI Codex. Implements **Propose and execute valid immutable
candidates**, consuming the completed phase 4 registry and execution framework.
No LLM usage records were created, as requested. Existing user changes were
excluded from the implementation commit.

The saved policy pins the implemented engine and adapter sources, runtime,
dependencies, evaluator version/families, actual-value domains, defaults,
transformations, mutation-group scales, diversity behavior, deterministic repair,
constraints and bounded retries. Evaluation and search/time batches are distinct;
each attempt mutates one coherent eligible group. Rules, source code, protected
tactics, total clocks, outcome accounting and pool restrictions are not genes.

Actual serialized configurations are validated at the registry-entry boundary
before scheduling. Unsupported/missing settings, malformed integer/categorical
types, boolean coefficients, nonfinite values, huge integers, unsafe resources
and unsafe time settings are rejected. Existing clipping at 4000 and terminal
scores at 10000 remain protected by the frozen source/schema basis; evaluation
retains the existing black-centric differences and Negamax conversion. Table
capacity is bounded to 8192 entries with the existing bounded payload. This is
not an OS byte-memory guarantee.

Saved parents, seeds and RNG states reproduce accepted proposals and all
repair/rejection records exactly. Canonical actual configurations plus source,
runtime and dependency identity deduplicate genotypes across aliases. Repeated
parent genotypes and duplicate offspring retain ancestry without adding candidate
entries. Empty exhausted slots remain explicit. Candidate records have complete
resolved settings and immutable source/configuration identity; parent entries
remain unchanged. The registry creates fresh restored player/search/table objects
inside separate per-game worker processes.

Seven focused tests cover the agreed proposal and registry execution seams:
reproducibility, write-once artifacts, parent immutability, malformed configurations,
fixed policy semantics/source identity, rejections/repairs/retries/deduplication,
both colors, and interleaved candidate-versus-candidate execution. The interleaved
test checks every expected configuration ID, distinct workers, cleanup, fresh
repeat games and independently replayed traces. The 13 existing registry tests
also passed. Existing fixed tactical/reliability expectations were not changed.

The real pilot and final checks are retained in [issue-37](issue-37/summary.json).
Proposal bundles include policies, parents and full proposal/rejection/state
records. Four compressed traces cover evaluation and search/time candidates in
both colors against the existing seeded training smoke opponent. They use 5000 ms
per-player cumulative clocks and a four-move cap; replay and the independent rules
reference agree. No validation or holdout opponent was played. These are capped
screening checks, not completed league games or evidence of strategic improvement.

Commands and policy/domain choices are documented in
[candidate proposals](../proposals.md). Full-suite, typechecking, compilation and
whitespace results are saved in [final checks](issue-37/final-checks.json).
The [two-axis review](issue-37-review.md) has no unresolved findings.

Final validation: **262 tests passed in 249.729 seconds**; mypy passed all
**36 targeted source files**; compilation and staged whitespace checks passed.
The final serial pilot took **8.127 seconds** with four capped games and zero
player failures. Exact original proposal/policy/parent JSON bytes are also saved
in `issue-37/proposal-artifacts.tar.gz` for manifest-hash verification.

Remaining optimizer work belongs to subsequent tickets: fitness, staged selection,
promotion, checkpointed optimizer state and broader real pilots. This change
does not claim competitive acceptance, promotion or official-clock strength.
