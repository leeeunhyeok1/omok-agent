# Phase 5 → Phase 6 handoff

Issue #45 connects proposals, screening, the broader frozen training league,
fresh confirmation, validation and official clocks, atomic promotion/history,
saved reviews and next-parent selection into repeated autonomous optimization.
[Launch, limits, stop/resume, review and export commands](evolution.md) describe the
public `offline.optimizer` interface. Phase 6 selection, final holdout evaluation
and submission packaging are not implemented here.

The verified shortlist contains `phase3-material`, entry
`e3de4b49cfa3b3b92981e00a946fbbf0925cbe5974f06ae8d1db4d1c421c46dc`,
frozen engine commit `105a8f64edaeb86082425c1fecb12932c06c4367`.
The real two-round pilot rejected material-coefficient 2 and 0 variants because
both tied the incumbent at screening fitness 0.75. No new champion was promoted.
It retained 56 actual training attempts, four validation games (2/2 black wins,
0/2 white wins), and eight official-clock smoke wins (4/4 each color), with minimum
remaining incumbent clock 58,964.978ms and no clock rejection reasons.
Exact configuration/source lineage, attempts, histories and export are in the
[acceptance report](verification/issue-45.md),
[compact summary](verification/issue-45/summary.json) and
[lossless evidence archive](verification/issue-45/evidence.tar.xz). Mutated candidates are experimental
parameter variants on that unchanged engine. Candidate acceptance is conditional
on actual gates, balanced training coverage, fresh confirmation, validation,
historical coverage and practical official-clock reliability. A mechanics fixture
that promotes a candidate does not establish real engine strength.

Training and validation are separate stages and exposure records. Prior defensive
validation exposure remains disclosed in Phase 4 and #42 reports. Final reserved
`synthetic-space` receives no optimization, tactical or final-evaluation calls.
Shared synthetic source/utilities and related design families limit independence.

The fixed tactical-suite identity hashes simulator, tactics, interruption,
transposition, evaluator and capture-effect test sources; candidate-specific gates
also restore actual registered players and check both-color public calls, input
ownership, finite scores, wins and capture defense. The suite is not rewritten
when coefficients change. Reliability vetoes, caps and infrastructure attempts
remain visible, including representative independently checked failure evidence.

The acceptance report records actual matchup/color outcomes, cumulative official
clocks, machine/power/load, stage allocations, attempt throughput and limitations.
Logical reproducibility means equal saved evidence yields equal proposals and
selection; clock outcomes depend on contention and hardware. Keep entire run
checkpoints to resume. Compressed Git evidence is for independent review and
restoration, not a substitute for authoritative pending child checkpoints.

Before Phase 6, assess broader diverse ordinary-opening training results, declared
validation exposure and reliability, then select a candidate under that phase's
specification. Final holdout is still reserved. SimplePlayer qualification, hidden
TA wins, tournament rank and the top-20% target remain unverified or unmet; the
small local smoke pilot cannot establish them. Preserve team/disclosure metadata
and acknowledgments for the separate final packaging phase. No new LLM interaction
records were created at the user's request.
