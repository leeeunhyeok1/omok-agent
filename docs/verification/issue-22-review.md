# Issue #22 code review

AI-written by OpenAI Codex. Reviewed against starting commit `3536693` using the
code-review skill's parallel Standards and Spec agents. User-owned changes were
excluded. No LLM-usage records were created.

## Standards

No documented-standard violations found. The new verification module uses only
the standard library and existing project modules, includes AI attribution, and
follows the documented issue/domain conventions.

One nonblocking heuristic finding: **possible Data Clumps / Primitive Obsession**.
The seven-field game identity is an unnamed tuple (`version, opponent, color,
seed, cap, budget, start`), and summary logic uses positional indexing for color.
A named game-plan type could make field-order changes easier to maintain.

Disposition: retained the bounded existing JSON key representation. This is an
optional readability improvement, not a correctness or documented-standard defect.

## Spec

One original finding: **P2 — Resume checks miss changed configurations and supplied
opponents**. The issue requires reproducible evidence and comparable opponent
versions. Checking only engine Python hashes allowed changed saved configurations
or supplied bots to mix under the same resumed batch name.

Disposition: fixed with a persisted batch identity covering canonical evaluator
identities, supplied-source hashes, immutable checkpoint, search settings and
offline-source hashes. Both resume and summary reject incompatible manifests. A
public CLI regression reproduced the original silent success before the fix and
now checks rejection. Existing manifests were added only after checking every
saved trace's evaluator, bot hashes, checkpoint and settings. The follow-up Spec
review confirmed resolution.

No scope creep or additional Spec findings were reported.

Standards: 0 hard violations, 1 optional maintainability finding. Spec: 1 original
reproducibility finding, fixed; 0 unresolved findings.

## Validation

The initial full suite passed **163 tests in 30.055 seconds**. The resume correction
added a regression and required a final full-suite rerun (results below).
Targeted measurement/replay checks passed, and typechecking passed for 21 source
files. Compilation passed. `python3 -I -S verification/offline_engine.py --iterative`
passed with engine/standard-library imports only and Python socket operations
denied. All 76 game traces hash-checked and replayed successfully.

Final full suite: **164 tests passed in 30.209 seconds**. Final typecheck and
compilation passed. The corrected batch resume retained completed games without
rerunning them, and the final summary replayed all 76 traces.
