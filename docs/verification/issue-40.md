# Issue #40 — broader training league and history

AI-written by OpenAI Codex under Phase 5 (#35), master #1.

Implemented [the broader league API and command](../league.md) over the existing
Phase 4 execution seam. Broader rounds consume only the recorded screening
survivors, retain every prior rung's complete evidence, and schedule the incumbent
on the same frozen distribution as the candidates.

| Acceptance requirement | Evidence |
| --- | --- |
| Save budgets, allocation, weights, coverage, rotation and elimination before execution | Write-once `LeaguePolicy` and `league.json`, embedded ScreeningPolicy, all resolved plans |
| Diverse designs plus incumbent/history, related-family weighting | At least two additional frozen training families; normalized family weights and literal-score variant test |
| Permanent history and periodic coverage after new promotion | Write-once verified source/config bundles, fixed slots, consecutive predecessor coverage and three-round addition test |
| Frozen comparable rounds, remeasure incumbent on changed distribution | One shared snapshot per cohort; new snapshots/job IDs and fresh incumbent plans after history additions |
| Unavailable opponents, caps/failures/incomplete coverage and all prior rungs visible | Reused validated attempt/color/matchup reports, explicit missing full fitness and historical gaps |
| Incumbent-only success insufficient, nontransitivity inspectable | Controlled incumbent win/diverse loss fixture; favorable aggregate/historical loss fixture; explicit white regression fixture |
| Accurate external provenance, no absent external agent or final holdout dependency | Original Entry metadata retained; unavailable supplied fixture remains pending; actual pool exclusion gates reused |

Eight focused public-boundary tests cover incumbent-only rejection, historical
and color regressions, related variants, three-round history rotation and added
champions, unavailable opponents and historical gaps, actual dispatch/resume,
failed gates/pending results, and corrupt archives/deleted schedule slots.
Existing screening tests cover cap and prior-attempt player-failure vetoes through
the same assessment function used by broader rounds.

The bounded pilot command is:

```sh
python -m verification.broader_league --output .scratch/issue-40-pilot
```

It generates one actual material mutation of the retained phase3 engine, runs six
fixed public-call probes per candidate/incumbent, admits the candidate through
explicitly controlled screening results, and executes 16 actual reduced-clock
jobs against aggressive and capture synthetic designs, the incumbent and retained
phase2 history. A legal eight-ply opening makes this execution check affordable.
Partial execution, resume and zero-new-job resume are exercised, and every
available trace is replayed. This is an execution/retention demonstration, not a
full-game strength, validation, official-clock or promotion claim. Validation
and final holdout are not scheduled.

Saved [pilot summary](issue-40/pilot-summary.json) and compressed
`issue-40/pilot-evidence.json.gz` retain the full manifests, policies, source
archives, proposals, probes, screening and broader evidence, checkpoints and
traces. The pilot finished in **52.466 seconds** with **16 replayed traces**,
**zero observed candidate player failures in 16 committed attempts**, and complete
due historical coverage. Both incumbent and mutation scored **0.5**, so the
mutation was rejected for insufficient favorable gain and the incumbent retained.
Resume preserved the same sample counts. The easy opening's black score of 1 and
white score of 0 remains visible; it is not representative color-strength evidence.

Review: [two-axis report](issue-40-review.md). The historical evidence chain was
corrected to avoid exponential duplication before final validation.

Validation commands:

```sh
python -m unittest tests.test_league -q
python -m unittest discover -s tests -q
python -m mypy omok offline --follow-imports=silent
python -m offline.league --help
git diff --check
```

Final settled-source validation: **291 tests passed** in **435.587 seconds**;
typechecking passed all **38 source files**. CLI help, compilation of the new
modules, and staged whitespace checks passed. No LLM-usage record was created,
as instructed by the user.
