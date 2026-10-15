# Analysis of the uploaded `run/` experiment

Analyzed October 16, 2026, Asia/Seoul. Saved evidence only: no new games,
benchmarks, or test suites were launched. This is an artifact audit, not an
executed reproduction or verified engine fix.

## Finding

The champion stayed unchanged because every screening survivor failed the
broader league. Screening is no longer uniformly zero. The run exposes both a
strict advancement barrier and continued weak play against SimplePlayer.

## Provenance and coverage

- Basis identity: `e1770829fb8c026ddea9ef424ab89c9403812c9062340c0ff5bd15ac54e2394a`.
- Champion entry: `98f07af4228dd5a3df61a9261de1d4260d14d815337cd1f53dd74cff5ce58134`.
- Champion store version: `19521cf28ac6d58dd3b2e57ef9e11c587b852efa7079e051f51325ed7111a262`.
- All 46 frozen source hashes match commit
  `d44f054b38c073d30b7550746c76811a34d9232d`. This verifies those files, not the
  entire checkout or its exact Git HEAD. No session metadata/backup was supplied
  alongside `run/` to establish the original run name or pinned HEAD directly.
- Runtime: `3.13.16 (main, Oct  1 2026, 15:40:24) [GCC 13.3.0]`.
- Colab Linux x86_64, two logical CPUs, one game worker.
- Four active segments recorded 232, 164, 80, and 96 attempts: 572 total.
- Their saved supervisor wall times total about 112.8 minutes; these are not
  measurements of complete notebook execution including setup and backups.
- All 572 saved result records are completed games; no recorded game failures,
  caps, or infrastructure failures in these stage results.
- Rounds 0 and 1 committed. Round 2 finished screening and is pending in league,
  with no league games yet committed to its saved controller stage.
- There were 12 accepted proposal slots across three populations, including a
  repeated configuration in round 2. These are not 12 completed generations.
- Later invocations record one keyboard interrupt and four graceful stops with
  zero attempts. `run/NOTEBOOK_STOP` exists. It must be deliberately removed
  before a future resume; do not change the frozen basis/checkpoints.

## Exact elimination path

Scores below are weighted game-point fitness, not qualification win rates.

| Round | Candidate prefix | Screening gain | League gain | League rejection |
| --- | --- | ---: | ---: | --- |
| 0 | `9dffe92e72` | +0.0500 | -0.0833 | Insufficient gain |
| 0 | `cff01891a9` | +0.1000 | 0.0000 | Insufficient gain |
| 1 | `0fab864809` | +0.0500 | +0.0729 | Matchup/family regression |
| 1 | `2486f60309` | +0.1000 | +0.0625 | Matchup/family regression |
| 1 | `6d53615419` | +0.0500 | +0.0208 | Gain below 0.05 |

Round 2 had no screening survivors: gains were -0.10, -0.10, -0.25,
and -0.10 versus the freshly measured incumbent.

The two positive league gains in round 1 came with better synthetic-capture
scores (0.5 to 1.0), but lower scores against `all24-initial`:

- Incumbent baseline: 7/16 game points (0.4375).
- `0fab864809` (material coefficient 1 to 2): 6/16 (0.375).
- `2486f60309` (small capture-coefficient mutation): 5/16 (0.3125).

The saved league policy sets maximum family, color, and matchup regressions to
zero. `offline/league.py:276` onward implements that rule. Consequently even a
one-point decrease over 16 incumbent games blocks further advancement despite
a larger overall weighted score. No candidate reached fresh confirmation.
Round 1's promotion check assessed only the incumbent; its transaction retained
the incumbent because no candidate was eligible.

This explains the unchanged champion. It does not establish that the rejected
candidates were stronger: they also lost their SimplePlayer league games, and
their initial advantages did not survive every comparison.

## Search and SimplePlayer evidence

Raw candidate-side returned events across all recorded stages contain 6,565
search diagnostics:

- Mean completed depth: 0.3508, weighted by actual recorded turns.
- Depth zero: 4,449 turns (67.8%).
- `partial_depth_one`: 4,031 turns (61.4% of all recorded turns).
- `verified_win`: 264; `verified_defense`: 87; `root_ordering`: 58;
  `static_ordering`: 9; no fallback source: 2,116.

The screening-only mean is 0.3415 across 3,098 turns, compared with the historical
0.126629. Different hardware contention and execution conditions prevent a
controlled causal strength comparison. Partial first iterations now retain work,
but most moves still do not complete a full first iteration.

Across screening and league, all candidates together scored 2 wins and 86 losses
against SimplePlayer; all 88 games ended by exact five. This aggregates different
candidates and repeated schedules, not an independent champion test. Screening
accounts for 2 wins/58 losses; league accounts for 0 wins/28 losses.

The separate recorded official-clock incumbent check scored:

- SimplePlayer: 0/8 wins, 0/4 as each color; each color has only one distinct
  evidence identity, so these are not eight diverse independent positions.
- RandomPlayer: 8/8 wins.
- Minimum remaining candidate time across the 16 official games: about 55.19
  seconds out of 60 seconds. The per-move search cap remained 250 ms.

Thus the SimplePlayer deficit includes ordinary board losses with substantial
clock remaining, rather than game-time forfeits. The official check is embedded
in optimization and is not the notebook's optional independent 40-game test.

A concrete incumbent screening loss as Black ended at ply 32, with about 6.07
seconds remaining from its 10-second clock. Its final search evaluated only two
children out of 24 root candidates and returned `partial_depth_one`. SimplePlayer
already had an open four in column 10, rows 7 through 10 (zero-based coordinates),
then won at `(6, 10)`. This identifies an already-losing late position; it does
not prove that a different final move could save it. Finding the avoidable
earlier mistake requires a separate bounded diagnostic reproduction.

## Interpretation and concrete next action

The current optimizer mutates coefficients and selects through fixed gates. It
does not turn loss reviews into source changes, new features, or directed
training targets. Two hours produced only two completed selection rounds, and
both retained only the incumbent as the next parent. More wall time therefore
continues sampling around that same parent unless a candidate clears every
barrier.

Do not commit another long run on the strength of these results alone. Preserve
this run and use its saved SimplePlayer losses to diagnose the earliest avoidable
threat-creation/defense mistake and the cost of obtaining useful reply search.
Separately review whether zero-tolerance league regression is appropriate for
exploration with this small, clock-sensitive sample. Any revised policy belongs
in a new experiment; relaxing it would permit different advancement, not prove
stronger play.

An LLM could propose explanations and candidate changes from recorded games,
but commentary alone does not update this engine. Such proposals need concrete
implementation and measured acceptance. No LLM integration was implemented in
this analysis.
