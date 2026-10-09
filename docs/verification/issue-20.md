# Issue #20 acceptance evidence

AI-written by OpenAI Codex. Scope: capture effects on implemented line families,
explicit endpoint multiplicity, shared defenders, and coherent opportunity/urgency.
Definitions and provisional parameters are in [the evaluation contract](../evaluation.md).
No LLM usage records were created at the user's request.

## Verified behavior

- Actual after-board feature recomputation includes intersecting fours and smaller
  potential. Captured cells become empty. Counterfactual geometric comparison
  isolates blocker removal; it is not used for rule outcomes.
- Capture-exposed opponent exact fives and simultaneous-win draws agree with the
  independent reference. Diagnostics retain before/after maximal runs and endpoints.
- Coexisting and move-created endpoint sets are deduplicated. Two broken fours
  sharing one completion are not labeled as multiple threats. Independence is
  limited to complete immediate-reply evidence, never geometric counts alone.
- The apparent-open-four fixture reports `(7, 7)` as a shared capture defender;
  removing White `(8, 7)` removes that capture opportunity and its effect.
  Color swaps and all eight rotations/reflections pass. No total-score ordering
  between fixture/control is presumed.
- Phase 2 tactical classifications are reused. Ordinary leaf multiplicity does
  not enumerate defender moves. Public search keeps the capture defense under
  radius zero/cap one and adverse extreme capture weights, and chooses a verified
  safe response for both colors and all board symmetries under sufficient budget.
- Context-fixed perspective inversion, color/context swaps, configuration bounds,
  saturation, family ablation, interleaved evaluators, cancellation after hypothetical
  captures, immutable parent/caller restoration, table clearing, and matched-tree
  alpha-beta/unpruned search at depths 0–3 pass.
- Earlier saved configuration schemas and canonical identities are unchanged.
  Phase 2's default and checkpoint remain available. No rules, candidate ranking,
  search recursion, public compatibility or clock policy changes were made.

## Commands and results

```sh
python3 -m unittest tests.test_search tests.test_tactics tests.test_transposition tests.test_captures -q
python3 -m unittest tests.test_threat_effects -q
python3 -m unittest discover -s tests -q
.scratch/typecheck-env/bin/mypy omok offline verification/evaluation.py verification/threat_effects.py --ignore-missing-imports --follow-imports=silent
python3 -m compileall -q omok verification tests
python3 -m verification.threat_effects --repetitions 5
python3 -m verification.threat_effects --games
python3 -I -S verification/offline_engine.py --iterative
```

Prerequisite checks: 47 passed. New focused tests: 8 passed. Full suite: **154
passed**, 30.307 seconds. Typecheck: 19 source files passed. Syntax/whitespace
checks and isolated engine/standard-library-only verification passed. The same
import/network guard also passed `effects-v1` loading and empty-board inspection
under `python3 -I -S` after running the guard via `runpy.run_path`.

[Independent suite and timings](issue-20-suite.json): 7,376 legal reference
transitions checked. Endpoints use an independently implemented five-window
candidate filter followed by the independent reference rules. Shared defenders
for fixture, control and intersecting threats are independently enumerated over
all legal defender moves and checked for new winning replies. The oracle does
not use engine capture, line, tactical or terminal helpers to derive labels.

Five repetitions per timing sample, local Python 3.14.3 on macOS 13.7.8,
x86_64, serial execution. Enabled
static evaluation medians: fixture 29.690 ms, control 18.164 ms, intersecting
29.368 ms, multiple capture 28.042 ms, dense 1,160.972 ms. Both new families
disabled: about 7.6–9.9 ms on sparse fixtures, dense 30.477 ms. Retained material:
about 0.03 ms. These are unrestricted evaluator calls, not public turn deadlines.

[Eight bounded game traces](issue-20-games.json): enabled, effects disabled,
multiplicity disabled, both disabled, each as Black and White against retained
Phase 2. Each starts from the same color-swapped single-capture fixture, retains
ordinary candidates and clock policy, uses max depth two, 60,000 ms per player,
and is capped after eight moves. All traces replayed and had no runner failures,
illegal moves, input mutations or exhausted game clocks. All eight were **capped**,
not wins or official draws. Deterministic color-symmetric runs are not independent
strength samples. All 32 experimental-agent turns fell back at completed depth
zero: enabled variants visited 4–6 nodes per turn, effects-disabled variants 11.
The 100 ms allocation was insufficient to complete their first iteration. This
is negative runtime evidence and prevents default promotion.

## Status and limits

Feature correctness is accepted; `effects-v1` remains opt-in and experimental.
Provisional coefficient utility/playing-strength improvement is not established.
The implementation deliberately retains a clear, costly recomputation reference;
optimization and broader Phase 3 strength measurement remain later work. No
league, evolution, extensions, final packaging or opponent holdout was added.
Review findings and disposition are recorded in [the review](issue-20-review.md).
