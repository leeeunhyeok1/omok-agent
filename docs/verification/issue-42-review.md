# Issue #42 two-axis review

AI-written by OpenAI Codex under Phase 5 (#35), master #1.

Fixed point: `57026bb7e5b455d699bca3d9c5c66aea1f27560f` (task-start HEAD).
Two independent read-only reviewers used the code-review skill, initially comparing
`git diff 57026bb7e5b455d699bca3d9c5c66aea1f27560f...HEAD` at implementation
commit `8ca31fa`, then reviewing the corrections in the working tree.

## Standards

No findings. The documented repository conventions and existing standard-library
Python patterns are followed. New implementation, tests, collector and docs carry
AI attribution. Tests exercise observable eligibility, regressions, holdout guards
and resume behavior. No substantive baseline code smells were identified.

## Spec

The reviewer identified two defects, both fixed before final verification:

1. Final promotion margins originally applied to selection-league regressions but
   omitted fresh-confirmation matchup/history/family/color regressions when the
   earlier confirmation policy was looser. The current policy now checks both
   sets of evidence. A controlled clean-selection/new-confirmation-regression
   fixture was observed to incorrectly report eligible before the fix, and now
   rejects with `confirmation_historical_regression`.
2. Earlier retained training rounds could contain a candidate failure that a later
   successful rescreen concealed from eligibility. All retained source screening
   rungs and historical rounds are now assessed recursively, retaining reliability
   and external-gate vetoes for each immutable candidate. A controlled earlier
   crash followed by successful current league/confirmation/checks still rejects.

The reviewer rechecked both changes and reported no remaining substantive Spec
gaps. The bounded real incumbent pilot supplies balanced validation and eight
empty-board official-clock games with recorded power/load/worker conditions.

Final review: **Standards 0 findings; Spec 0 remaining findings** (2 corrected).

At resumed handoff, two fresh independent reviewers checked the complete change
from the same fixed point, including the pending corrections and retained pilot
artifacts. Standards reported zero findings; Spec reported zero findings against
issues #42, #35 and #1. The compressed archive identity was verified, all twelve
traces replayed, and reassessment reproduced `checked_incumbent`.
