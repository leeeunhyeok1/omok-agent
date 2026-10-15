# Handoff: balanced v3 training and acceleration

Written October 16, 2026, Asia/Seoul. Think and respond in English.

## Start here

1. Read this file, `AGENTS.md`, `docs/agents/issue-tracker.md`, and
   `docs/agents/domain.md`. GitHub Issues are authoritative; use `gh` for relevant
   specs, especially #35 and #45.
2. Identify the evidence supplied by the user. The repaired engine and balanced
   notebook have been pushed, but **no balanced-v3 Colab results have arrived**.
   Inspect supplied logs/artifacts before drawing conclusions or starting games.
3. Establish the actual source commit, exact Python build, profile, run name,
   worker count, completed rounds, pending stage, parents, and champion identity.
4. Follow the relevant branch below. Completion means an evidence-backed account
   of what ran, the concrete issue or progress, remaining uncertainty, and the
   next bounded action. A champion change is not required to demonstrate that
   exploration occurred; neither parent movement nor deeper search proves strength.

## User intent and scope

The user wants **general competitive strength beyond SimplePlayer**. They plan
to add classmates' agents later; none have been supplied or registered yet.
SimplePlayer is a diagnostic weakness, not the sole intended objective.

The user was frustrated after two hours without a champion change. They
authorized delegated diagnosis, implementation, focused verification, and a push
to GitHub. Those actions are complete. The latest request is to write this
handoff and explain whether GPU migration could greatly accelerate training.
The GPU answer is feasibility guidance; no GPU backend implementation has been
requested or completed in this turn. See
[the acceleration research](gpu-training-feasibility.md) when considering that work.

Earlier the user stopped broad testing. Subsequently they authorized a concrete
repair and its small controlled comparison. Keep verification proportional:
eight development games have already been run; another long training session or
large game sweep is not an automatic next step. Use the diagnosing-bugs skill for
concrete failures. The user explicitly permits sub-agent delegation.

## Delivered source and notebook

Repository: `https://github.com/leeeunhyeok1/omok-agent`.

Pushed to `main` and verified with `git ls-remote`:

```text
7220f3b0d21aab10414eb947071fd20c807708b3
Merge Colab-saved notebook history and preserve prior session archive
```

Implementation commit: `edc9b6f` — Improve search evaluation and add balanced
exploratory Colab training. Any subsequent documentation commit does not change
that engine delivery. The notebook uses `SOURCE_REF = "main"`, so establish its
printed pinned commit rather than assuming this commit was used.

- [Current notebook](../notebooks/all24-training.ipynb)
- [Open in Colab](https://colab.research.google.com/github/leeeunhyeok1/omok-agent/blob/main/notebooks/all24-training.ipynb)
- [Notebook instructions](../notebooks/README.md)
- [Balanced profile](colab-training/balanced.md)
- [Implementation and measured evidence](simpleplayer-search-repair.md)

Defaults: `ACTION = "fresh"`, `TRAINING_PROFILE = "balanced"`,
`RUN_NAME = "balanced-search-v3"`, one worker, one segment of up to 1,800 seconds
and 250 game attempts. Gates, setup, backup, and cleanup add time. The old four
segments/two-hour default has been replaced. Use a fresh runtime when changing
already imported engine code, and a fresh run for the changed source/policy.

Three profiles exist:

- `balanced` (default): original five screening families with equal weights,
  original all24 configuration and game allocations, new exploratory parents.
- `simple-focused`: optional targeted diagnosis, SimplePlayer gets half the
  initial screening weight and eight games over four distinct opening pairs;
  separate confirmation openings. It is no longer the notebook default.
- `all24`: original recipe and original strict parent policy, available for
  comparisons. All profiles preserve champion qualification requirements.

Fresh initialization without playing games:

```sh
python3 docs/colab-training/initialize-all24-colab.py \
  --profile balanced --output .scratch/balanced-search-v3
```

The remote had a Colab-saved notebook commit `dd9d29e` with old resume settings,
outputs, and manually commented stop-file checks. It was merged into history;
its exact notebook is preserved at
`notebooks/archive/all24-search-v2-colab.ipynb`. Use the current notebook for new
training. Unrelated user work and old run data were excluded from the push.

## Why the two-hour champion stayed unchanged

The uploaded old `run/` is a search-v2 experiment with frozen basis
`e1770829fb8c026ddea9ef424ab89c9403812c9062340c0ff5bd15ac54e2394a`.
Its 46 frozen source hashes match `d44f054b38c073d30b7550746c76811a34d9232d`;
the actual Git HEAD was not separately supplied. Colab runtime was
`3.13.16 (main, Oct  1 2026, 15:40:24) [GCC 13.3.0]`.

It recorded 572 completed games, two committed rounds, and a third round with
screening complete and league pending. Five screening survivors all failed the
broader league. Two improved weighted league fitness (+0.0729 and +0.0625) but
failed zero-tolerance matchup regression against the incumbent. Neither completed
round selected an additional parent, so mutation repeatedly started from the
same champion. This was not the earlier all-zero-screening problem.

Search was still shallow: 4,449/6,565 recorded candidate turns completed depth
zero. Most used `partial_depth_one`. The incumbent official-clock check recorded
zero wins and eight losses versus SimplePlayer, and eight wins versus RandomPlayer. Minimum remaining clock
across those 16 official games was about 55.19 seconds out of 60. The move cap
was 250 ms. These were ordinary board losses, not game-clock forfeits.

For authoritative details read [the old-run audit](colab-search-v2-run-analysis.md).
Do not modify that run's hashes/checkpoints to resume under updated code.
`run/NOTEBOOK_STOP` exists locally; old subsequent zero-attempt invocations
include graceful stops. A stop file must be deliberately removed to resume its
compatible original experiment.

## Implemented repair and evidence

`omok/lines.py` reuses already found exact-five geometric completion candidates,
then verifies strict outcomes through `Position.play` and classification.
`omok/captures.py` enumerates existing own-stone anchors instead of every empty
square in eight directions. Multi-capture grouping and sorted output remain.
Rules, feature meanings, coefficients, candidate membership, and search/time
settings were preserved. No neural evaluator, GPU, SPSA, CMA-ES, or LLM loop was
implemented.

The captured proposal-candidate position at ply 22 has a deterministic real-engine
regression: within 100,000 cooperative checks, the baseline selects `(6, 8)` after
four evaluated children; SimplePlayer's `(11, 8)` then creates an undefendable
threat. Updated evaluation examines fourteen children and selects `(11, 8)`,
occupying the saved reply square. An independent rules oracle checks the losing
continuation and an explicit alternative. This establishes one avoided fatal
continuation, not the globally earliest strategic error or a forced win against
every reply. Both old/new bounded results still have completed depth zero.

Read [the diagnosis](simpleplayer-saved-loss-diagnosis.md) for provenance, exact
baseline red invocation, hypotheses, and limits. The fixed fixture is
`verification/fixtures/simpleplayer-ply22.json`.

Verification already completed:

- 84 focused engine/search/evaluation tests passed.
- Complete line, capture, and evaluator inspection reports matched exactly on
  29 captured/seeded positions.
- Seven original selection/profile checks passed; adding balanced support
  produced eight passing checks across those classes, including all three
  initializers with zero game dispatch.
- One integration test proves actual exploratory offspring ancestry survives
  round-commit and proposal-persistence interruption/resume while champion
  promotion remains unchanged. It uses fabricated scripted-worker outcomes,
  not strength games. One source-edit race triggered the compatibility guard;
  the stable-source rerun passed. The guard was preserved.
- Notebook JSON and all 12 code cells parse. Initializer/status CLI construction
  was checked. The notebook has **not** been executed in Colab by this agent.
- A full repository suite was not run. Old `tests/test_evolution.py` helpers
  derive a policy from the historical phase3 entry while default initialization
  now registers current code, so some existing tests fail the source-identity
  guard before testing their intended behavior. The old recovery mechanics
  scenario passed when only its starter fixture was swapped to current code;
  production compatibility checks were retained.

Eight real local development games were played serially under one frozen plan:
four baseline and four updated, same original coefficients and 250 ms move cap.
Baseline 1W/3L; updated 2W/2L. Black results regressed from 1/2 to 0/2; White
improved from 0/2 to 2/2. Mean completed depth increased 0.5167 to 1.2549;
depth-zero turns decreased 31/60 to 5/51. The sample does not establish a strength
gain. Local Python was 3.14.3 on macOS, unlike Colab; power/load were uncontrolled.

Plan, source/runtime hashes, scores and eight replay-verified compressed traces:
`docs/verification/simpleplayer-repair/`. The harness is
`verification/simpleplayer_development.py`; it requires an explicit frozen plan
and refuses to overwrite earlier evidence.

## When balanced-v3 results arrive

Inspect cell 8, then saved evidence as needed. Prefer existing envelope readers
and report APIs; `evolution.json` and controller checkpoints are not flat objects.

1. Confirm actual profile/source/runtime, workers, attempts, stop reasons,
   committed rounds and pending stage.
2. Compare actual proposals, per-opponent/color outcomes, screening and league
   gains. Separate accepted mutation generation from acceptance/promotion.
3. Inspect **selected parents and actual next-population ancestry** separately
   from the champion. New `offline.evolution.parent_candidates` permits feasible
   screening survivors rejected only for league strength to parent. Known
   failures/incomplete evidence block them. Validation strength is excluded.
4. Inspect champion qualification decisions. Every original champion gate still
   applies; an unchanged champion can coexist with useful exploration.
5. Compare turn-weighted search depth, evaluated children, cancellation and raw
   `fallback_source`. A depth-zero `partial_depth_one` move uses evaluated work.
6. Analyze representative losses across opponent families before proposing a
   targeted fix. More depth, one favorable seed, or a new parent is not strength
   proof. Preserve reduced-clock versus official-clock distinctions.

If the notebook fails, identify the first failing cell and traceback before
judging training. If testing is disabled, the missing independent test scores
are expected. Ask only for evidence needed by the current question.

For resume/restore/backups, the original local
`docs/colab-search-update-handoff.md` is useful when present, but
this file supersedes its source, profile, verification, and notebook defaults.
Use the checked-in notebook/README as the current operational reference.

## Generalization and acceleration follow-up

Keep diverse frozen training opponents and separate evaluation opponents or
versions. Adding classmates' agents changes the pool: register their provenance,
family and runtime, freeze a new snapshot, and remeasure the incumbent. Neither
the current five-family pool nor repeated evaluation on training bots establishes
general strength. Final holdout remains outside optimization.

The optimizer tunes 24 scalar coefficients through games; it does not run neural
gradient training. Current search/evaluation is standard-library CPU Python.
Selecting a GPU Colab runtime does not move it to GPU. Read the linked GPU
research before proposing implementation, and distinguish games/hour from
decision quality at a fixed move clock. Profile the current revision before
selecting another hotspot: earlier profiles predate these optimizations. Measure
the whole invocation, including candidate gates, process startup and backups,
as well as move/evaluator time; kernel speed alone is not end-to-end throughput.

Preserved unrelated local state: modified `.DS_Store`, deleted
`05_EVOLUTION_SPEC.md`, `Untitled3.ipynb`, `all24-training-colab/`,
`match-scores-2.json`, `run/`, and earlier untracked handoffs. These were not part
of the engine push. Avoid broad staging, cleanup, or reset commands.
