# Issue #44 acceptance evidence

AI-written by OpenAI Codex under Phase 5 (#35), master #1.

Implemented [saved-evidence batch reviews and checked regressions](../reviews.md)
at the agreed optimizer-evidence and tournament/replay boundaries. Submission
engine behavior and existing tactical expectations remain unchanged.

| Requirement | Evidence |
| --- | --- |
| Compact candidate/incumbent review | Markdown summary and JSON evidence companion include selection, promotion reasons when saved, coverage, reliability samples, weak opponent/color cells, timing, recorded resources and next bounded experiment |
| Representative failures | Stable diversity sampling across candidates/opponents/colors/clock pressure; positions spread across game plies; full source trace, prior history and available diagnostics retained |
| Hypotheses and deeper budget | Automatic phase/clock/category explanations marked hypotheses; review performs no deeper analysis; explicit transition/wall-time budget and actual use recorded separately |
| Independent checked tactics | Exhaustive independent reference one-ply wins or two-ply immediate defenses; partial search stays unknown; only complete confirmed failures export allowed sets |
| Additive fixtures | Exclusive creation; independently recheck expected answers; preserve existing fixture bytes and reject changed expectations |
| Bounded engine proposals | Record problem/scope/behavior/gates/comparison, distinct lineage, compatible incumbent rebenchmark and new comparable run |
| No diagnostic probing | Saved-run reader validates authoritative checkpoint evidence without writing files, resuming execution or constructing competitors; saved eligibility/transactions bind to original training cohort/stage/evidence |
| Provenance and controlled examples | Original player/configuration/source evidence retained; explicit AI attribution; compressed controlled artifacts round-trip exactly |

Controlled examples use fabricated scoring outcomes and recorded test-player
turns, not measured playing strength. The missed-win example independently finds
exactly one immediate winning move, `(9, 9)`, while the recorded move was `(0, 0)`.
A one-transition budget yields unknown and cannot create a checked fixture.
No validation, holdout or registered opponent was executed by the collector.

The [summary](issue-44/summary.json), [compact review](issue-44/review.md), and
[compressed controlled evidence](issue-44/controlled-evidence.json.gz) retain all
10 JSON artifacts, including stage/raw evidence, checked fixture and source
trace. Decode the gzip as UTF-8 JSON: keys are original relative artifact paths,
values are complete artifact contents. All artifacts round-tripped exactly.
The independent [two-axis review](issue-44-review.md) has no remaining findings.

```sh
python -m verification.reviews --output .scratch/fresh-review-example
python -m offline.reviews batch --stage .scratch/fresh-review-example/stage --raw .scratch/fresh-review-example/raw.json --output .scratch/fresh-review-example/cli-review.json
python -m unittest tests.test_reviews.ReviewTests -v
python -m unittest discover -s tests -v
python -m mypy omok offline verification/reviews.py --follow-imports=silent
python -m compileall -q omok offline verification tests
git diff --check
```

Focused suite: **5 tests passed in 116.826 seconds**. Final full-suite coverage:
**341 tests passed**, with no failures. The user briefly requested stopping the
long run, then requested continuation. The initial **163** completed tests were
preserved; the remaining **178** passed in **667.141 seconds**, including the final
earlier-rung provenance assertion. [Coverage evidence](issue-44/test-coverage.json)
verifies the complete discovered test identities against both logs, with no
duplicate completed tests.

Typechecking passed all **45** checked source files; CLI review, independent
fixture verification, compilation and whitespace checks passed. No LLM-usage
records were created, as requested.
