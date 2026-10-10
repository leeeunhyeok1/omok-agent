# Frozen optimizer baseline (#36)

AI-written by OpenAI Codex. This is the prerequisite ticket under #35, consuming
the completed Phase 4 framework. It selects no optimization, fitness, mutation
or promotion policy. Material remains the retained default; effects remains
experimental. Phase 3 competitive acceptance is unmet: both versions lost all
eight retained SimplePlayer games. Tiny-clock acceptance remains partial.

From the repository root, use a fresh output directory:

```sh
python -m verification.optimizer_baseline collect --output .scratch/baseline-run
python -m verification.optimizer_baseline verify --output .scratch/baseline-run
```

The standard-library command freezes the basis, proves isolated restoration,
runs the existing simulator/public-player/search and framework gates, runs the
remaining fixed tactical/configuration/integration suites, then probes six
balanced training slots with **one game worker**, 5,000 ms cumulative per player
and a 20-move cap. The default probe budget is 60 seconds; `--probe-seconds`
permits positive finite values up to 120. Each of the three gate groups has a
600-second subprocess bound; isolated restoration has a 30-second bound.
Batch budget shutdown includes bounded active-worker cleanup, so elapsed time
can exceed the requested dispatch budget. Progress prints after gate groups and
committed games. No background service, GPU, cloud account or continuous session
is needed. A machine must support the recorded exact Python runtime and retained
Git objects for game execution; the official grader runtime remains unknown.

`freeze` creates the artifact without running gates or measuring throughput;
it is preparation, never acceptance. `verify` checks all artifact digests,
registry and pool identities, runtime compatibility, restored source hashes
and resolved settings. It proves restoration, never competitive strength.
Neither operation plays any opponent. Existing output directories are refused.
Gates reject a working engine whose bytes differ from the retained incumbent;
changed code needs separately established compatible gates and a new basis.

`baseline.json` has a SHA-256 identity over its complete canonical basis. Its
incumbent is the actual #22 checkpoint
`105a8f64edaeb86082425c1fecb12932c06c4367`, with exact registry entry, source
hashes and runtime. The restored public player supplies concrete depth/node,
candidate, ordering, table, profiling and time settings. Its evaluator is
`omok.search.material_evaluation`, with no configured evaluator. This distinction
preserves the actual callback; loading `material-v1.json` would construct a
different configuration/cache identity despite equivalent material scores.
`incumbent.tar.gz` includes the compatible engine, supplied players and all five
configuration assets. Restoration uses `-I -S -B` in a fresh directory and checks
both-color legal fallback, input ownership and the known material score.

`basis-inputs.tar.gz` retains working engine/runner/adapter sources, all existing
tests and verification tools, configuration contracts, earlier handoffs and
the complete #22 and #34 performance evidence. Individual input hashes and a
fixed-suite identity are saved. New fixture expectations or feature semantics
require a new basis. Keep both archives with the manifest; restoration uses
the exported engine bytes and does not depend on a mutable working-code path.
Re-execution additionally needs compatible registered adapter sources and
retained Git objects, as required by the Phase 4 API.

Training, validation and holdout have exact pool and opponent identities in the
basis. The probe uses only training: SimplePlayer, capture and pattern designs.
`synthetic-defensive` was already exposed in Phase 4 and remains labeled
validation; it does not receive new games here. `synthetic-space` receives no
games or tactical calls. Metadata freezing is not gameplay. Shared source,
related strategy families and deterministic repeats limit independent evidence.
Classmates and hidden TA agents remain unavailable.

`gates.json`, `fixed-suite-gates.json` and `restoration.json` record executed
verification. `probe.json` records scheduled, completed, failed, capped,
infrastructure and pending counts, wall time, separate slot/completed-rule-game
rates and observed machine/runtime conditions. The adjacent compressed plans,
results, reports and representative losses preserve seeds, colors, exposures,
clock policy, diagnostics, attempts and independent replay. Durable `run/`
outputs preserve checkpoints for the existing batch resume API; do not overwrite
them to restart the collector. Compressed result exports alone are analysis
evidence, not a resumable checkpoint.

CPU/RAM snapshots and one-worker timing inform local resource choice. Peak
per-process memory and external OS contention are not measured. Record local
conditions with `--contention '...'`. Start with one worker for comparable
wall-clock evidence; any later concurrency change needs a separately labeled
measurement. Caps and budget-interrupted slots remain explicit. Screening slot
throughput does not estimate official completed-game throughput; that field is
unavailable. Player/infrastructure failures are saved and make collection exit
unsuccessfully, requiring investigation before using fitness evidence. A bounded
probe with pending slots is partial resource evidence, not a completed league.

No new LLM usage records are created, per the user's instruction. Supplied bots
remain unchanged and retain their acknowledgments. Final submission and
disclosure verification remain later work.
