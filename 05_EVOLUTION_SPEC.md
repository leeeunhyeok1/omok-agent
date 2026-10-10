# Phase 05 — Offline Evolution, Promotion, and Failure Analysis

Status: specification for the fifth bounded implementation phase.

Recorded: October 8, 2026, Asia/Seoul.

Parent context: `MASTER_SPEC.md`, especially sections 7.3–7.7, 8, and 9.

Prerequisites: verified simulator/search/evaluator and the phase-04 reproducible tournament framework.

Next phase: `06_GENERALIZATION_TESTING_SPEC.md`.

## 1. Work order and destination

Implement a bounded, resumable offline optimization loop that proposes valid parameter configurations, evaluates them against a diverse training league, selects promising candidates, and promotes a champion only after reliability, league, historical-version, and validation checks.

Use the existing engine architecture and evaluator feature definitions as a frozen basis for each run. Improve evaluation coefficients and supported search/time parameters through measured experiments. Preserve older champions and analyze representative failures so development is guided by evidence rather than only an aggregate rating.

The destination is a repeatable local command that can run for an allocated resource budget, checkpoint, resume, explain every promotion/rejection, and export the exact code/configuration identity of the best verified version. It need not produce an improvement in every batch. A correct optimizer that retains the previous champion after inconclusive or unfavorable evidence is successful behavior.

Keep final holdout opponents completely outside optimization and candidate selection. Do not claim a class percentile, hidden TA victory, or a promised number of games from this work. Full reinforcement learning, architecture replacement, and final packaging are outside this phase.

## 2. Inspect and establish the frozen baseline

Read the master and earlier phase specifications, actual code, configuration schemas, acceptance reports, decision records, runtime profile, pool manifests, and confirmed tactical positions. This authoring workspace does not establish that the implementation prerequisites have already passed.

Run correctness/reliability gates before optimizing. Verify that the tournament framework enforces cumulative clocks, bounds nonreturning players, preserves job identity, and reports game versus match outcomes accurately. Repair a measurement defect before trusting fitness differences.

Retain the current verified champion, even if it is only the phase-03 default. Snapshot its engine/evaluation version, complete configuration, tactical-suite version, training/validation pool identities, runtime/clock policy, and performance evidence. A path to mutable working code is not an immutable champion.

Measure local throughput and practical resource limits before selecting initial population size, games per screening stage, mutation rate, and worker count. Those values were intentionally deferred; choose and record them as implementation choices, not previously agreed numbers. No GPU/cloud execution is required.

## 3. Agreed boundaries and implementation discretion

The main acceptance seam is an optimizer run consuming the phase-04 execution/results API and emitting immutable candidate records, evidence, and a champion decision. Controlled synthetic results can verify selection and promotion behavior, followed by a bounded real-engine pilot.

Existing rule, public-player, and tournament boundaries remain hard regression gates. Optimization must not alter their expected outcomes, hide failures, or remove slow opponents to make a candidate look stronger.

The implementing AI may select a simple mutation/selection strategy, staged evaluation policy, gene schema/ranges, fitness construction, uncertainty method, and promotion thresholds. Record these choices in the run policy before using them to interpret outcomes. Do not invent a single mandated algorithm such as CMA-ES, a neural learner, or a large genetic population.

Prefer an understandable initial population search around a retained champion, with some diversity and immutable elites. More elaborate optimizers are optional follow-up experiments after the basic loop is validated. Code changes are distinct from parameter changes.

## 4. Parameter schema and invariants

### 4.1 Eligible parameters

Use the evaluator schema from phase 03 and supported engine configuration from phase 02. Potential genes include:

- Line/pattern, capture, vulnerability, and positional coefficients.
- Compatible offense/defense/tempo parameters that preserve zero-sum scoring.
- Ordinary candidate radius/count and supported ordering coefficients.
- Existing tactical-extension thresholds, only if extensions have actually been implemented and verified separately.
- Existing time-allocation/reserve parameters and other bounded search resource settings.

Begin with small coherent parameter groups. Evaluation-only batches and search/time-policy batches should be identifiable. Combining groups is allowed when deliberate and recorded, but not necessary for the first loop.

Do not add a fictional gene for an unimplemented feature. A missing extension implementation is not implemented by tuning an extension threshold. Introducing a new feature or search mechanism is an explicit engine-version change, with separate correctness checks and baseline measurements.

### 4.2 Untunable requirements

The optimizer cannot change game rules, board encoding, public method semantics, supplied player color, official 60-second budget, terminal outcome logic, cancellation correctness, mandatory tactical-move protection, or result accounting.

It cannot disable input/state checks, convert capped games into wins/draws, remove crash flags, consume holdout opponents, or relax a failed tactical assertion to make a candidate feasible. Timing parameters must retain actual total-clock protection; turning off deadline checks is not a faster policy.

### 4.3 Types, bounds, and validation

Document each gene's type, domain, transformation if any, default, and constraints/interactions. Select actual ranges from implemented score bounds and observed runtime rather than copying untested arbitrary values. Integer/categorical parameters must not receive unvalidated floating mutations.

Before scheduling games, reject malformed, unsupported, nonfinite, or out-of-domain configurations. Validate score-range/terminal dominance, perspective consistency, memory limits, and feasible candidate/time settings. Reject invalid mutations or repair them with a documented deterministic rule; never silently clamp without recording the resulting actual genotype.

Different coefficient scales may represent similar preferences, but score bounds, thresholds, ordering, and saturation can make scaling consequential. Optional normalization/canonicalization must preserve documented semantics rather than assuming all proportional configurations are identical.

Canonical configuration identity must use the actual validated serialized values. Deduplicate exact duplicates and record shared ancestry. Do not give one genotype extra statistical weight because it was generated repeatedly under different display names.

### 4.4 Cache and agent independence

Each candidate owns its configuration and runtime state. Changing parameters invalidates incompatible evaluator/table values according to phases 02–03. Interleaved candidate execution must not share mutable coefficients or score caches.

Keep immutable candidate artifacts and construct fresh per-game instances through the existing adapter. A final champion is code plus configuration, not a standalone weight file whose engine semantics are unknown.

## 5. Training league and historical champions

Use a versioned training snapshot containing diverse frozen opponent designs and selected historical champions. Do not optimize only against the current champion. Maintain per-opponent and per-color evidence so one exploitable style cannot dominate the decision unnoticed.

Retain promoted historical versions permanently in the registry/archive and include them in periodic regression checks. Practical rotating subsets are acceptable if their schedule is recorded and older versions still receive periodic coverage. Never delete a past champion merely because the new version beat it once.

Freeze the opponent set and weights within each comparable round. If a new classmate bot, synthetic design, or historical champion is added, create a new pool snapshot and remeasure the incumbent on the changed distribution. Do not compare new-pool fitness directly with an old-pool score as though the environment were unchanged.

Related opponent variants must be identified; ten variants of one engine should not automatically receive ten times the influence of an independent family. League weights and any family balancing are explicit policy choices. Missing opponents and unavailable files remain visible; they cannot disappear silently from a named league.

The professor's bots and approximately 3–4 possible classmates' bots remain external opponents, with attribution. Hidden TA agents are not available. Holdout exclusion applies even to a tempting classmate agent whose result would be useful for debugging.

## 6. Fitness and reliability gates

### 6.1 Explicit objective

Select and save the objective before each run. A weighted league score is consistent with the plan, but exact weights and draw treatment are not fixed here. Define the score's units, opponent/color weighting, denominators, failure handling, and any worst-matchup component.

Distinguish strict win rate, game score with draw credit, eight-game match outcome/coins, and ratings. The assignment's qualification gate counts at least five strict wins; its tournament uses match coins. A training score with draw credit is not a qualification claim. Elo is a summary, not a sufficient fitness/promotion rule by itself.

Use balanced colors and comparable jobs within a selection cohort. When opponents receive different sample counts, aggregate according to the declared league/family policy rather than accidentally treating micro-average volume as intended importance. Expose the underlying counts and color imbalance.

### 6.2 Feasibility before strength

Rules/tactical correctness and observed reliability failures are gates. A reproduced candidate crash, timeout, illegal move, mutation, broken restoration, invalid score, or mandatory-tactic regression prevents promotion regardless of estimated strength.

Screening may discard failing candidates early to conserve compute, preserving the failing traces and reason. An infrastructure error is not automatically a candidate failure or a strategic loss; use the phase-04 classification/retry policy.

Reliability cost may also be included in a fitness display, but a finite penalty cannot allow an otherwise high-scoring defective candidate to bypass the gate. Report zero observed failures with its sample size, not as a guarantee of impossibility.

### 6.3 Incomplete and capped evidence

A candidate with incomplete scheduled coverage does not have a completed full-league fitness. Missing games/opponents, caps, interrupted attempts, and unresolved outcomes must remain explicit. Do not invent draws to complete its score or cherry-pick only successful attempts.

Resource caps can create selection bias if a configuration deliberately reaches them often. Set a declared completion/coverage policy and inspect cap rates against the incumbent. Insufficient completion or suspicious censoring makes evidence inconclusive/ineligible, not automatically favorable.

Stage-local screening scores may use a subset, but compare candidates on that same defined subset and label the score. Do not rank one candidate's weak-opponent partial score against another's completed full-league score.

## 7. Candidate proposal and staged selection

### 7.1 Proposal

Generate offspring from recorded parents using a seeded deterministic proposal process. Support parameter-group mutation scales and occasional diversity proposals within valid domains. Elitism preserves the incumbent rather than overwriting it in place.

Mutation distribution, step size, crossover if any, categorical handling, and adaptation policy are implementation choices. Record actual changed values, parent IDs, proposal seed/state, and any repair/rejection. Bound invalid-proposal retries so a degenerate domain cannot hang the optimizer.

Do not mutate source code as part of the ordinary genotype loop. Feature/architecture experimentation follows the separate version procedure below.

### 7.2 Evaluation stages

Use a cost-aware pipeline:

1. Configuration and fixed tactical/reliability gates.
2. Small comparable training screenings to remove clearly unpromising candidates.
3. Broader balanced training league and incumbent/historical comparisons for survivors.
4. Fresh confirmatory jobs for finalists rather than reusing only selection-winning samples.
5. Periodic validation and official-clock checks before champion promotion.

Exact budgets, elimination policy, sample sizes, and validation cadence must be saved before the stage. Cheap node/depth or reduced-clock screening is useful but does not establish official-budget strength. Final time-management candidates must be checked at equal real wall-clock total budgets.

Progressive allocation is acceptable. Preserve every rung's requested jobs/results and elimination reason. Do not present early-stopped candidates as though they all received the final budget. Concurrent completion order must not silently change which seeded candidates/jobs are proposed.

### 7.3 Noise and confirmation

Expect selection to favor noisy winners when many configurations are compared. Repeating identical deterministic games does not solve this. Use defined variation, balanced pairings, and fresh confirmation seeds/openings on the training distribution for serious finalists.

Choose a documented uncertainty/decision method appropriate to the data, accounting for pairing, opponent heterogeneity, and duplicate evidence. Record when evidence is too sparse or dependent to support a strong conclusion. No mandatory p-value, confidence threshold, or sample count is invented in this spec.

Predeclare stopping/elimination rules. Repeatedly checking results until a candidate barely passes must not be presented as a clean fixed-sample proof. If a sequential policy is selected, document that policy and its practical limitations.

## 8. Validation and champion promotion

### 8.1 Validation exposure

Validation is excluded from direct candidate fitness and routine mutation selection. Check selected finalists/champions at the recorded cadence with balanced colors and comparable conditions. Repeated validation-guided choices still influence development, so validation is not an untouched final test.

Log exposure and distinguish training gains from validation changes. If training improves while validation degrades, retain the prior champion or investigate overfitting rather than declaring a universal strength gain. Do not tune directly against every weak validation opponent and still describe that pool as unseen.

Do not schedule final holdout at any stage of this loop. Holdout evaluation is deferred until a final candidate is selected in the later generalization/freeze workflow.

### 8.2 Saved promotion policy

Save concrete promotion criteria before deciding a candidate. They must cover:

- Passing correctness and zero observed reproduced reliability failures.
- Evidence against the incumbent, without relying on one favorable eight-game match.
- Aggregate diverse-league performance and per-color behavior.
- Worst-matchup/family regressions and historical-champion checks.
- Validation results under the declared cadence/coverage policy.
- Practical official-clock timing, completion behavior, and score/configuration compatibility.

Select material improvement and allowable regression margins using measured data and the available budget; these numeric thresholds were not previously decided. Weak evidence yields “retain incumbent/inconclusive,” not a forced promotion merely to show progress.

Nontransitive results are possible: a candidate may beat the incumbent while losing to an older champion or another style. Preserve matchup tables and investigate serious regressions. Do not infer general strength from head-to-head victory alone or require an impossible claim of beating every opponent with certainty.

### 8.3 Promotion transaction

Promote atomically only after required evidence has been committed. Save the new champion's immutable code/configuration identity, parent, full promotion evidence, run/pool/tactical-suite versions, runtime settings, limitations, and decision reason. Retain the old champion unchanged in the historical archive.

The export must load the exact promoted configuration under its compatible engine. Reset incompatible caches. Never point “champion” to a half-written weights file or select whichever worker happened to finish last.

If no candidate qualifies, keep the incumbent and explain why. Rollback must restore a known version without reconstructing settings from terminal output.

## 9. Failure analysis and bounded engine improvements

Use phase-04 loss replay/export to sample representative failures across opponents, colors, time pressure, and game phases. Do not inspect only losses to one attractive benchmark or assume the final move caused the defeat.

Record hypotheses such as capture-defense omission, exposed pair, wrong line value, candidate exclusion, horizon effect, opening weakness, or time-allocation failure. Verify rule/tactical claims through the independent simulator and appropriate search analysis. Deeper offline analysis uses a separately recorded budget.

Turn confirmed failures into fixed regression fixtures with checked outcomes/allowed move sets. Distinguish an unknown best strategic move from a demonstrable missed win or capture defense. Do not rewrite existing expected answers to make a tuned configuration pass.

Daily review should produce a small actionable report: strongest verified candidate, promotion/rejection reason, worst matchups/colors, failure examples, timing/throughput, and the next bounded experiment. It must be informative without requiring the user to read thousands of raw games.

If a repeated failure requires a new evaluator feature, candidate mechanism, or selective extension, handle it as a bounded code change on a separate engine version. Document the problem, allowed modules, intended behavior, correctness checks, and comparison plan. Rebenchmark incumbent configurations under compatible versions and start a new comparable optimization run.

Search/time tuning can include already supported radius/count, ordering, table-resource, and clock parameters. It cannot introduce unverified pruning through a numeric parameter or remove tactical protection. Architectural freeze means a coherent experimental basis, not concealing necessary bug fixes.

## 10. Checkpoints, reproducibility, and resources

Persist optimizer state in addition to game results: engine/schema/pool/policy identities, population and parentage, proposal RNG state, stage assignments, committed fitness evidence, pending jobs, eliminated candidates, incumbent/history, validation exposure, and promotion decisions.

Resume from saved logical state, using phase-04 stable job identities and attempt handling. Do not regenerate a new population or silently re-evaluate only favorable games. Default proposal/selection order must be reproducible independent of worker completion order; if an asynchronous variant is later selected, record its decision events and timing dependence explicitly.

A graceful stop ends dispatch, commits verified results, leaves unfinished candidates pending/inconclusive, and does not promote them. Crash/restart recovery must not duplicate a generation or champion transaction. Cross-machine resume retains provenance and labels changed wall-clock conditions rather than mixing them invisibly.

Runs are bounded by user-selected wall time/games/resources and can continue through checkpoints. Use measured local throughput to choose batch size and reserve time for correctness, validation, confirmation, and packaging. Do not spend the entire remaining project budget on screening offspring.

The original plan aims for several days of offline grinding, with October 17 the last planned day for major strategic changes and October 18 reserved for freeze/verification. This spec does not assume nonstop hardware availability or promise thousands of generations. Mac/PC execution comes first; additional compute is a later user resource choice.

## 11. Verification scenarios

### 11.1 Schema and mutation

- The same seed, parents, and policy produce the same validated proposals.
- Invalid/nonfinite/type-incompatible values are rejected before scheduling.
- Repairs, duplicates, and rejected proposals are recorded without unbounded retry loops.
- Mutations cannot alter rules, clock budget, terminal protection, or pool exclusion.
- Interleaved configurations preserve independent weights and clear/segregate incompatible caches.

### 11.2 Fitness and stage accounting

Use synthetic phase-04 result fixtures with known candidate/opponent/color counts. Verify declared weighting/draw handling, failure vetoes, incomplete coverage, cap handling, stage-local scores, and unchanged incumbent when evidence is inconclusive.

Construct a candidate that beats only the current champion but loses across the diverse league: it must not be promoted from that head-to-head result alone. Construct one with a higher aggregate score but a reproduced crash: the reliability gate must block promotion. A high score over completed easy opponents with missing difficult opponents must not masquerade as full-league fitness.

### 11.3 Confirmation and pool separation

Test that selection samples and fresh confirmation jobs are identifiable. Default optimization jobs never include final holdout, and validation is not injected into direct fitness. Verify exposure tracking and new-pool incumbent remeasurement when an opponent is added.

Test historical versions remain archived after promotion and receive the documented periodic coverage. Related variants and duplicate deterministic evidence retain their labels rather than inflating independent-opponent claims.

### 11.4 Promotion and resume

Use deterministic synthetic outcomes to demonstrate a feasible improved candidate can pass the saved policy and be exported exactly. Demonstrate a rejected candidate leaves the champion unchanged. Simulate interruption before/after result commits and during promotion; resume without duplicate jobs, regenerated proposals, or partial champion artifacts.

Serial and out-of-order mocked result completion must produce the same logical selection under the default deterministic policy. Genuine player failures remain recorded and cannot be retried away under infrastructure recovery.

### 11.5 Real bounded pilot

Run a small real-engine pilot with actual training opponents, both colors, valid mutated configurations, at least one completed selection decision, checkpoints/resume, and a validation check where available. Exercise official-clock confirmation for a serious candidate or the incumbent even if no improvement is found.

Report source/configuration identities, policy, counts, seeds, caps/failures, elapsed resources, throughput, tactical gates, selected/rejected versions, and limitations. No minimum Elo gain or win-rate improvement is required for engineering acceptance. Avoid spending the reserved final holdout during this pilot.

## 12. Acceptance, deliverables, and handoff

Accept the phase when valid proposals are reproducible, measured selection uses the declared league policy, reliability gates cannot be bypassed, pool separation is preserved, confirmation/promotion decisions are auditable, history is retained, resume/export are exact, and the real bounded pilot completes with honest evidence.

Deliver the gene/policy schemas, seeded proposal/selection loop, staged execution integration, fitness/uncertainty reporting, validation/promotion gates, checkpoint/resume commands, immutable champion exports/history, loss-review/regression workflow, verification scenarios, and pilot acceptance report.

Keep engine code, parameter artifacts, optimizer state, opponent files, and eventual submission output separated. Preserve AI attribution, prompts/responses, external-source acknowledgments, and portable paths. Do not publish or assemble the final assignment package now.

For phase 06, provide a shortlist of verified champions/configurations, training/validation histories, per-color/matchup evidence, tactical-suite version, reliability/timing results, code-change lineage, and final holdout exposure status. The generalization phase tests robustness and selects/freezes a final candidate before untouched final evaluation; it must not repeat the full optimizer indefinitely.

## 13. Out of scope

- Final holdout evaluation, guaranteed hidden TA wins, actual class percentile, and final submission packaging.
- Mutating rules/source as ordinary genes, hiding failures, relaxing fixtures, or changing evidence after seeing results.
- Full neural reinforcement learning, MCTS replacement, GPU/cloud setup, new search paradigms, and a large opening book.
- Promoting from ratings/head-to-head alone or forcing a champion change every generation.
- Background scheduling automations, issue publication, GUI/Part 1 work, and implementing the next phase without the user's request.

Next specification to request: `06_GENERALIZATION_TESTING_SPEC.md`.
