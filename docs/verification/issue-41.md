# Issue #41 — fresh finalist confirmation

AI-written by OpenAI Codex under Phase 5 (#35), master #1.

Implemented [fresh training confirmation](../confirmation.md) on the existing
optimizer execution/evidence seam. The incumbent stays immutable and retained;
finalists advance only to later validation and official-clock promotion checks.

| Acceptance requirement | Evidence |
| --- | --- |
| Save budget, pairings, variation, stopping and uncertainty before outcomes | Write-once validated policy and `confirmation.json`; complete common settings and all paired jobs saved before dispatch |
| Separate selection-winning samples from fresh training jobs | Retained source stages/results and all league predecessors; effective seed/opening overlap rejection; foreign selection result rejection |
| Account for pairing, heterogeneous opponents, families and duplicate/seed dependence | Paired color blocks, duplicate collapsing, weighted opponent means within families, explicit seed limitations, leave-one-block/family sensitivity |
| Preserve different execution segments | Pairwise declared condition comparison, segment provenance/metrics and missing or incompatible condition gates |
| Counts, effects, limitations and advancement/rejection/inconclusive reasons | Raw-job and attempt counts, distinct block counts, family/color effects, descriptive sensitivity range and saved fixed decision method |
| Auditable predeclared stopping | Fixed jobs and bounded infrastructure retries; partial reports stay incomplete; resume preserves declaration and exported attempt/segment history |
| Noisy winner can fail; sparse/unfavorable evidence retains incumbent | Controlled screening-win/confirmation-loss, one favorable block, sparse pairs, deterministic/unsupported repeats and family-regression fixtures |
| Training only and hard coverage/reliability gates | Shared training-only resolution and replay-validated reports; candidate failure veto; incomplete results stay inconclusive; no holdout/qualification/promotion claim |

The two-axis [review](issue-41-review.md) identified and fixed a checkpoint rollback
defect: older internally valid checkpoints cannot erase previously exported
attempts or execution conditions. No findings remain on either review axis.

Fifteen public-boundary confirmation tests cover the fixed policy, provenance,
freshness, paired sensitivity, shared-family effects, reliable retention and
supervised stop/resume, including lost/rolled-back checkpoints.

The first full regression run passed **305 tests in 490.150 seconds** using
`python -m unittest discover -s tests -v`. Typechecking passed for all 39 modules
with `python -m mypy omok offline --follow-imports=silent`. Compilation and
`git diff --check` passed. The three focused resume checks passed together after
the source was held fixed.

A final audit added a legal-opening-order fixture: different move orders that
reach the same board and side to move cannot manufacture fresh deterministic
evidence. Freshness and dependence blocks now use the effective starting state,
while retaining the full opening sequence in saved provenance.

The final full suite on the corrected frozen source passed **306 tests in
489.175 seconds**. Both reviewers rechecked the opening-state correction and
reported zero remaining findings. Typechecking still passed for all 39 modules.

The bounded pilot's selection winner is a **controlled artificial fixture**.
Confirmation uses actual restored Phase 3 incumbent/proposed engine configurations
in supervised games against two training designs. Its two-move cap deliberately
limits work and does not provide ordinary strength evidence. Every cap remains
unresolved; the decision retains the incumbent with an inconclusive finalist.
Zero observed candidate failures is limited to the recorded attempts. No
validation or holdout games are used.

The final reviewed-source pilot completed in 61.718 seconds. Both configurations
recorded eight committed attempts each, with zero observed candidate player
failures. All 16 games reached the declared two-move cap, leaving no recognized
paired strength blocks. The finalist is inconclusive and the incumbent retained.
See [the summary](issue-41/pilot-summary.json) and the complete compressed
[declarations, gates, checkpoints, attempts and traces](issue-41/pilot-evidence.json.gz).

The source remains frozen during final regression tests. Two earlier focused
resume checks observed source-identity rejection because the adapter was edited
while those checks ran; both passed when rerun with unchanged source. This was
an expected provenance gate and did not require weakening it.
