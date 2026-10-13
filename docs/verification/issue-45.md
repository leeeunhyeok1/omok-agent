# Issue #45 — autonomous Phase 5 integration and acceptance

The optimizer now initializes and repeatedly proposes, gates, screens, evaluates
survivors/incumbent/history, confirms finalists, checks eligibility, commits atomic
champion decisions, reviews and selects the next recorded parents. The complete
saved policy and experimental basis precede proposals or dispatch. User bounds
cover all rounds/stages and infrastructure retries. See [copyable commands and
resource limits](../evolution.md) and [Phase 6 handoff](../phase-05-handoff.md).

## Real public-command pilot

The collector ran `offline.optimizer initialize`, bounded `run`, stop-file `run`,
resumed `run`, `status`, `review`, `export` and zero-budget `run` on this machine.
The exact commands, logs, immutable policy/pool, population RNG/ancestry, raw
attempts, plans, stage reports, exposure, decisions, reviews, source IDs and export
are retained in the evidence archive. Full live checkpoints remain under
`.scratch/issue-45-acceptance/autonomous` for local resume.

Machine: Intel Core i5-7360U @ 2.30GHz, four logical CPUs, 8 GiB RAM,
macOS 13.7.8, CPython 3.14.3. Runs used `nice -n 10` and one game worker (two
isolated players), with other Omok experiments stopped. Observed launch power:
battery, discharging at 42%; power policy unmeasured. Desktop/Codex contention was
uncontrolled; load observations are retained in each execution segment.

The pilot saved seed 46, one candidate per population, balanced near-win opening
training at 5,000ms per player and a 20-move cap. Those openings bound execution
cost; their outcomes establish no broad strength improvement. Validation used two
opening variations, including an empty board, at the saved 5,000ms clock and
100-move cap. Official smoke checks started empty and used actual cumulative
60,000ms clocks, one worker, and four games of each color.

| Work | Actual attempts | Result |
| --- | ---: | --- |
| Round 0 screening and incumbent league | 28 | Complete; candidate rejected for insufficient gain |
| Stop file at committed round boundary | 0 | No dispatch or population change |
| Round 1 training, generated from saved parents | 28 | Complete; candidate rejected for insufficient gain |
| Due real validation | 4 | 2/2 black wins, 0/2 white wins against synthetic-defensive |
| Actual official-clock smoke check | 8 | 4/4 black wins and 4/4 white wins |

The candidates mutated material coefficient 1 to **2**, then **0**; their exact
identities are `71186610041b8652d17639e96a4805945dbc80f20afb7049e846802324452b11`
and `73a57baf31f63db9feeabbaf1a14cb8ffbf0a81d3cfb6ba141889c4a223f543f`.
Both scored training fitness **0.75**, tied with the incumbent. No candidate
advanced and no actual champion changed. The minimum incumbent remaining official
clock was **58,964.978ms**, with eight samples and no clock-eligibility reasons.
The public training phase completed 28 attempts in 74.911 recorded invocation
seconds, **0.374 attempts/s**, including gates, preparation, persistence and
reduced-clock games. The second bounded invocation completed 40 attempts in
125.437 seconds. These are workload-specific measurements, not a promise for
ordinary-opening or larger leagues.

Retained incumbent entry:
`e3de4b49cfa3b3b92981e00a946fbbf0925cbe5974f06ae8d1db4d1c421c46dc`,
`phase3-material`, frozen engine commit `105a8f64edaeb86082425c1fecb12932c06c4367`.
The material engine remains unchanged. Its exact champion export restored in real
isolated players and made two legal moves; that deliberate two-move cap is a
restoration probe, not a scored draw or a strength result.

## Controlled engineering evidence

Public-boundary scenarios cover proposal/stage/child commits, corruption rejection,
all training-role policies, archived-holdout role rejection, exhausted populations
and renderable reviews, gate vetoes without game dispatch, parent/next-round
creation, and interrupted-versus-uninterrupted equality of populations, decisions,
RNG and parents for equal evidence. Zero-budget recovery recreates an export lost
in the round-commit window. Committed games and champion transactions are not
repeated on resume.

The separately retained controlled autonomous scenario uses **fabricated worker
outcomes and fabricated official conditions** to exercise a feasible promotion,
fresh finalist confirmation, validation separation, subsequent historical coverage,
rejected confirmation/incumbent retention, automatic next proposals and a crash
immediately after the champion transaction. It establishes mechanics, not engine
strength or real timing. Independently checked missed-win evidence is also labeled
as a constructed failure scenario. The unchanged full repository suite covers
rules, public-player ownership/clocks, mandatory tactics, tournament accounting,
proposal schemas, fitness, pools, confirmation/history and atomic promotion.

## Reproduction and limits

```sh
nice -n 10 python3 -m verification.evolution_acceptance \
  --output .scratch/new-issue45-acceptance \
  --power 'actual observed power and unknown settings' \
  --load 'actual observed load; other experiments stopped'
python3 -m unittest tests.test_evolution -v
python3 -m unittest discover -s tests -v
.scratch/issue-21-tools/bin/python -m mypy omok offline verification/evolution_acceptance.py --follow-imports=silent
```

[The compact summary](issue-45/summary.json) records allocations and outcomes.
[The lossless archive](issue-45/evidence.tar.xz) contains exact files, including the
original complete summary; [the inventory](issue-45/inventory.json) binds every
archived file. Gzip output was losslessly transcoded to streaming XZ (5.6 MiB)
for repository retention, without dropping outcomes or checkpoints. Its
inventory records SHA-256 for each file. Keep the original live run directory for
pending-job resume; restoration must use compatible source/runtime and locally
retained Git objects. Source version `6119320` binds this collector's runtime code.
Logical reproducibility is distinct from wall-clock outcome reproducibility.

Both saved pool policy and actual exposure audit protect final `synthetic-space`:
no optimization, tactical or final-evaluation calls. Defensive validation had
prior development exposure; shared synthetic source/utilities and repeated use
limit independence. Infrastructure failures remain attempts with explicit unknown
exposure where needed; missing results and caps never become draws or fitness.

No new champion, Elo gain, SimplePlayer qualification, hidden TA wins or class
rank is claimed. The official smoke result is not professor-bot qualification.
Phase 6 selection, untouched final holdout evaluation and final submission
assembly remain separate work. No new LLM usage transcript was recorded at the
user's request. [Independent review](issue-45-review.md) has no remaining
confirmed specification findings and one optional maintenance suggestion.
