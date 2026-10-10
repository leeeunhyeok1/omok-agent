# Issue #40 review

AI-written by OpenAI Codex. The implement skill requested code-review; its two
axes ran in separate parallel review agents. The fixed point is the session's
starting commit `6e8e8812a17cdadce6f6064bb18e85d9a2bb2f28`. Review covered the
working diff and new league/test/docs files before the requested commit.

## Standards

No hard violations found in the documented repository standards.

One judgment call: possible Duplicated Code in family and color aggregation.
Both calculate weighted opponent means followed by weighted family means.
The formulas remain explicit beside their different reported metrics; they use
the same saved weights and are covered by independent literal-score examples.

The reviewer also identified exponential predecessor duplication: every round
embedded every preceding round, including their predecessors. Fixed by retaining
only the immediate predecessor, giving a linear evidence chain, and checking
that every supplied previous round matches that chain.

## Spec

No remaining findings after the predecessor correction. Saved policies,
family/color balancing, permanent historical artifacts and periodic rotation,
fresh incumbent measurements, unavailable/incomplete evidence, prior screening
rungs and controlled nontransitive regressions cover #40. No scope creep found.

Final counts: Standards **0 hard violations, 1 heuristic observation**;
Spec **0 unresolved findings**. The shared scalability concern was fixed and the
spec reviewer verified the correction.

The standards reviewer also rechecked the predecessor fix and bounded real-engine
pilot, finding no new material issue. Assessment still traverses the retained
chain recursively and preparation reloads preceding artifacts; very long
histories can become expensive. This is a recorded scaling limitation for later
optimization, beyond the bounded Phase 5 pilot.
