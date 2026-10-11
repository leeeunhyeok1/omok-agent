# Issue #43 acceptance evidence

AI-written by OpenAI Codex under Phase 5 (#35), master #1.

Implemented [atomic champion promotion, export and rollback](../champions.md)
at the agreed public champion-store and export/reload boundaries.

| Acceptance requirement | Evidence |
| --- | --- |
| Committed evidence and deterministic selection | Reassess identity-bound eligibility under saved policy; wait for every declared check plan; choose the highest confirmation lower bound with immutable identity tie-break |
| Atomic complete champion version | One checksummed checkpoint commits current identity, parent, original code/configuration, compatible construction adapter, evidence/run/pool/policy/suite references, runtime, reason and limitations |
| Unchanged history and periodic regression | Retain original version bundles; save/import rotation slots; reject omitted or rescheduled known historical coverage; league dispatch executes archived bytes |
| Exact export and fresh caches | Self-contained export verifies sources and adapter before isolated construction; nondefault evaluation/settings/time policy preserved; repeated workers start with empty caches |
| Rejected/incomplete/inconclusive outcomes | Retain incumbent and record reasons; unidentified tactical suite, incomplete cohort and historical coverage vetoes cannot promote |
| Interrupted/resumed transactions | Tests interrupt before/after evidence and champion commit, plus filesystem replace failure; resume yields one decision, unchanged parent/history, no partial champion |
| Rollback without terminal reconstruction | Restore known stored version; reject unknown version; transaction replay after rollback does not silently repromote |
| Feasible improved candidate | Controlled complete eligibility fixture promotes, exports, runs in real workers and restores its exact predecessor |

The retained pilot passed in **135.967 seconds**. Its fabricated feasible outcomes
and clock observations demonstrate promotion mechanics, not measured playing
strength. The archived synthetic player actually executed two capped moves in
fresh supervised subprocesses. Two additional real-worker reload games verified
material coefficient 19, depth 1, node limit 100, table capacity 32, exact time
policy, and empty cache counters. Those configuration/cache probes use an
explicit constant accounting clock and a low-time path. They are not practical
official-clock strength evidence. No holdout was executed.

See the [summary](issue-43/pilot-summary.json), compressed
[complete evidence](issue-43/pilot-evidence.json.gz), and independent
[Standards/Spec review](issue-43-review.md). Earlier review findings were corrected
and re-reviewed; no hard standards findings or spec defects remain.

The evidence archive uses `omok-evidence-graph-v1`: `artifacts` maps relative JSON
paths to encoded roots; `nodes` maps canonical SHA-256 identities to typed nodes.
An encoded item is either `{value: ...}` or `{ref: node_identity}`. Object and
array nodes recursively decode their `items`; value nodes return `value`.
Verify each node identity and the archive `identity` against the decoded artifact
map. All **20 artifacts / 1,139 unique nodes** round-tripped exactly against the
original files. This representation removes repeated declarations and source
bundles without dropping any evidence, exports or traces.

```sh
python -m unittest tests.test_champions tests.test_experiments tests.test_league.LeagueTests.test_real_dispatch_resumes_without_repeating_evidence -v
python -m verification.champions --output .scratch/champion-pilot
python -m unittest discover -s tests -v
python -m mypy omok offline verification/champions.py --follow-imports=silent
python -m compileall -q omok offline verification tests
git diff --check
```

The focused champion/experiment/league suite passed **22 tests in 1,854.318
seconds**. The final historical-pool/defensive-copy test addition also passed
independently in **4.699 seconds**. The full regression suite passed **336 tests
in 3,525.771 seconds**. Typechecking passed all **43** checked source files;
compilation and whitespace checks passed. The long run includes repeated full
eligibility/checkpoint assessments and archive restoration through subprocesses.
No LLM-usage records were created, as requested.
