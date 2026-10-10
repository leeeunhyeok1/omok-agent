# Eight-game opponent matches

Issue #28 adds `offline.matches.score_experiment(plan, raw_results)` and the
`score` command. Each run saves `match-scores.json` beside unchanged game facts;
`results.json` and the return value include the same report as `match_scores`.
Previously saved `omok-experiment-v1` plans and raw
`omok-experiment-results-v1` results remain readable without changing their IDs.

```sh
python3 -m offline.experiment_cli score --plan .scratch/official-run/manifest.json --results .scratch/official-run/results.json --output .scratch/rescored.json
python3 -m unittest tests.test_matches -v
```

Scoring never imports or runs the registered players. Output uses exclusive writes;
choose a new file to retain earlier evidence. For an interrupted run, construct a
results object with `format: "omok-experiment-results-v1"`, the saved plan's
`manifest_identity`, and a `results` list of committed per-game records. Missing
records remain pending. This is a reporting API, not a checkpoint/resume protocol.

The `omok-match-scores-v1` report records the applied `eight-game-local-v1`
policy independently of the manifest's raw-execution policy. Result format and
manifest identity must match; duplicate, foreign, or misassigned results fail
explicitly. Supplied aggregate counts and any previous `match_scores` are ignored;
all counts are derived from the planned slots. Completion order does not affect
scores. Available traces are independently replayed before recognition; their
actual initial board/side, cumulative budgets and move cap must match the plan.
When trace experiment provenance exists, its job and manifest ID must match.
Earlier failures are considered only in a replay-validated cleanup-error record;
an unrelated `prior_result` field is invalid evidence.
This checks evidence consistency; it does not authenticate externally edited files.

For each opponent match, the report preserves all slots, candidate color counts,
execution status/reason/failure/error, board-rule outcome, recognized game result,
crash flags, and completed/failed/capped/pending/infrastructure-failed counts.
`rules_score` counts only actual rule-terminal wins/draws. `recognized` adds the
explicit local game-forfeit interpretation below; it never rewrites raw traces or
the rule winner. Coins are ordered `[candidate, opponent]` and awarded once per
match, never per game.

| Recognized strict wins, opponent wins, draws | Candidate qualifies | Tournament result | Coins |
| --- | --- | --- | --- |
| 5, 3, 0 | Yes | Win | 2, 0 |
| 4, 3, 1 | No | Win | 2, 0 |
| 4, 4, 0 | No | Draw | 1, 1 |
| 3, 4, 1 | No | Loss | 0, 2 |
| 0, 0, 8 | No | Draw | 1, 1 |

These rows assume eight recognized slots, four assignments of each color, and no
crash or infrastructure error. The five-win threshold and greater-win tournament
comparison are separate decisions. An opponent crash can award a tournament win
but cannot replace the candidate's five strict wins for qualification.

## Failures and interpretation

The assignment explicitly overrides an opponent match when a player crashes.
Locally, an exception raised during a turn or an unexpected player-process exit
is a crash: it forfeits that game and the opponent match. A candidate-only crash
disqualifies the candidate and gives tournament loss/coins `[0, 2]`, even with six
raw rule wins. An opponent-only crash gives tournament win/coins `[2, 0]`.
The raw and recognized scoreboards remain visible. An observed exception still
counts as a crash when the supervisor labels the late call as a timeout.

Timeout, invalid move, input mutation and broken protocol are **local game
forfeits only**. They are recognized strict wins for the nonoffending side under
this documented policy. They do not apply the stronger crash match-loss override.
The supplied text does not establish the grader's exact treatment of every such
error; these are explicit offline interpretations, not new official rules.
Reliability gates for future promotion must still reject reproduced candidate
failures, even when this local match interpretation says the candidate qualifies.

A match needs eight planned slots numbered 0–7 and four assignments of each color.
Any missing result, resource cap, setup failure, supervisor error, or malformed/
inconsistent trace keeps tournament outcome `unresolved`, coins `null`, and
qualification `null`. An observed candidate crash always makes qualification
`false`, even if other slots are unresolved. Counts and flags expose every cause;
caps never become draws. A cleanup error retains any preceding crash evidence but
still prevents a coin allocation. Both players crashing in different games adds
`both_crash`, leaves the tournament unresolved without coins, and disqualifies the
candidate. No contradictory official award is fabricated.

`complete` means a match is fully interpretable under this policy. Player game
forfeits can be complete; both-crash ambiguity and infrastructure/caps cannot.
The separate `development` field compares only recognized game wins, ignores the
match crash override, reports how many games contributed, and awards no coins.
It may classify a partial sample; it is never a completed-match decision.

All modes retain their label. `official_format` is true only for the saved
`official` empty-board, eight-game, 60,000-ms plan. Other eight-game modes can use
the same comparison as local development evidence; their coins/qualification are
local policy projections. Short schedules retain slots/counts but carry
`invalid_schedule` and receive no match award. Artificial fixture results do not
establish playing strength or actual official qualification. No standings, class
rank, rating, retries or promotion are implemented here.

Implementation and tests are AI-written by OpenAI Codex. No LLM usage transcript
was recorded, as requested.
