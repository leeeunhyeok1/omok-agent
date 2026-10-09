# Issue #16 — saved evaluator acceptance

AI-written by OpenAI Codex, based on GitHub #16 and master #1. Implementation
choices and public loading/inspection APIs are in [evaluation.md](../evaluation.md).
No LLM-usage records were created, per the user's explicit instruction. Existing
user deletions and the untracked phase specification are excluded from the commit.

## Prerequisites, before production edits

Baseline `798963cae696eead8353232d1cc8c289cce473a9`, Python 3.14.3,
macOS 13.7.8 Intel, serial local execution:

```sh
python3 -m unittest tests.test_simulator tests.test_reference tests.test_search tests.test_iterative tests.test_transposition -q
python3 -m verification.differential
python3 -m verification.iterative
.scratch/typecheck-env/bin/mypy omok --ignore-missing-imports --follow-imports=silent
```

67 tests passed in 2.501 s; baseline typechecking passed for 6 files. Tests cover
capture/exact-five/draw rules, immutable input ownership, alpha-beta/unpruned
matched trees, cancellation and transposition compatibility. Independent reference
comparison passed 5,561 transitions over 32 sequences, seeds/rules unchanged from
Phase 2 (10.432 s). No prerequisite correctness defect was found.

[Fresh timing records](issue-16/prerequisite-timing.json): 336 public probes,
49 incoming-clock overruns at 0.001, 0.1 or 1 ms, zero input mutation/legality
failures. Phase 2's recorded 48 tiny-clock overruns remain a known timing
limitation; this fresh run is also explicitly partial timing acceptance, not a
claim of meeting hard deadlines. No timing policy was changed.

## Implementation checks

The master #1 and supplied Phase 3 document pre-agree simulator/public-player and
matched-tree search seams, with configuration/inspection checks required by #16.
The first saved-config test failed on the missing evaluator module before
implementation; the public-player slice then failed on unsupported constructor
configuration before integration. Additional boundary checks reject malformed
configuration, verify bounded/disabled inspection, cancel inside feature scans,
and preserve terminal scores. Tests use literal fixture expectations and retained
Phase 2/unpruned search as independent oracles.

```sh
python3 -m unittest tests.test_evaluation -v
.scratch/typecheck-env/bin/mypy omok offline verification/evaluation.py verification/acceptance.py verification/offline_engine.py --ignore-missing-imports --follow-imports=silent
python3 -m verification.evaluation --config configs/material-v1.json --position position.json
python3 -I -S verification/offline_engine.py --iterative
python3 -m unittest discover -s tests -q
python3 -m compileall -q omok offline verification tests
```

Five evaluation tests pass. Matched trees use a capture fixture, both colors,
depths 1/3/2/3 and bounded tables. Configured material scores/optimal moves agree
with retained Phase 2 unpruned search. Interleaved independently weighted public
players and a switched engine agree with fresh equivalent search. Switching clears
scores/hints and stale diagnostics. Invalid installation leaves the engine intact.
Canceled evaluation yields no completed score or leaf entry; board remains intact.
Inspection handles ablation, saturation and incomplete work, with no partial total.

Full suite passed 124 tests in 12.930 s; compilation passed.
Typechecking passed 17 engine/offline/verification files. Isolated no-site execution
passed with Python socket operations denied and engine/standard-library imports.
CLI inspection of an empty explicit black-to-move board returned material zero,
complete/unsaturated, configuration ID
`0f197f30a680dfe3909a2f04f4af164285df72c8826e9e164c6f6d4c7f4d7c48`.

Required richer families remain pending #17–#20; this is configuration foundation
acceptance, not whole-Phase-3 acceptance. No strength experiment or promotion is
claimed. Phase 2 checkpoint and evaluator remain unchanged.
