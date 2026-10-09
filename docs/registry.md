# Immutable player registry and protected pools

AI-written by OpenAI Codex for issue #26. This is offline infrastructure; it does
not change candidate strategy, clocks, rules, evaluator weights, or submission imports.

Freeze the currently available versions before playing them:

```sh
python3 -m offline.registry_cli freeze --output .scratch/registry-v1.json
python3 -m offline.registry_cli play --registry .scratch/registry-v1.json --candidate phase3-material --opponent random --candidate-color white --purpose development --seed 20261010 --move-cap 20 --output .scratch/registered-game.json
python3 -m offline --replay .scratch/registered-game.json
```

Outputs are created exclusively: existing registry/game files are never overwritten.
The play command uses the saved entries and pool snapshot rather than rebuilding
identities from current files. Changed sources/adapters or a different Python
runtime require a newly registered version. The API is `run_registered_game` in
`offline.registry`; it accepts the existing supervised runner's initial board,
budgets, move cap, diagnostics and supervision settings. CLI default clocks are
60,000 ms per player; one game is not an official eight-game match. A move cap is
an experiment stop, not a draw. Replay continues to accept v1/v2/v3 game traces.

## Entry contract

`Entry.local` and `Entry.checkpoint` return frozen canonical-JSON definitions.
`record()` and `data` return independent copies. `from_record` checks the stored
SHA-256 identity before use. The identity covers every definition field:

| Field | Meaning |
| --- | --- |
| logical_id, variant | Stable selection name and version description; the SHA-256 identifies the exact version |
| origin, family | Source provenance and design grouping; parameter variants are related designs |
| loader | Local bundle root/module/factory, or full Git commit and archived paths |
| options | Complete JSON constructor configuration; checkpoint evaluator path resolves inside the immutable archive |
| sources, source_paths | SHA-256 of source/configuration/dependency assets and exact declared bundle membership |
| adapter_sources | All live offline adapter/supervision sources, pinned separately even for retained checkpoints |
| runtime | Exact Python runtime string; moving to another runtime requires a new identity |
| dependencies | Required import names, checked inside bounded workers |
| availability | ready, pending, or unavailable; requested non-ready entries fail explicitly |
| color_mapping | Explicit constructor `color`, black=0, white=1; other conventions require a thin bundle factory |
| acknowledgment | Source credit; required for all origins, including classmates |
| seed_support | constructor, process-global, deterministic, or unsupported |
| diagnostics, limitations | Supported diagnostic fields and compatibility/evidence limits |

Include **all** local dependencies and non-Python configuration/model assets in
`source_paths`. Directories capture all files except bytecode/cache, Git metadata,
and `.DS_Store`; adding/removing files changes the bundle. External installed
non-standard-library dependencies must be vendored into the declared bundle.
This deliberately avoids treating an unpinned environment import as immutable.
The stdlib belongs to the pinned runtime. `dependencies` lists required imports;
transitive dependency completeness remains the registrar's responsibility.
Absolute external roots must be made available at the same location when moving
a saved registry; repository entries use `.` and checkpoints use Git objects.

Both colors undergo bounded import/construction/configuration preflight before a
game. Preflight never calls `take_turn`, so it is metadata/setup validation rather
than competitive exposure. It rejects invalid config, wrong color, missing imports,
changed files and nonreturning setup. Requested unavailable opponents never disappear
from the requested coverage. A setup exception identifies the logical ID and digest.
Each game starts fresh persistent player workers, with verified private source
copies; lazy imports stay within that snapshot. The supervisor owns and removes
the snapshot workspace after worker termination. This is process isolation, not a
security sandbox. External packages named `player` or `helper` remain separate
between players. A factory module resolving outside the bundle is rejected.

Each role receives an independent deterministic seed derived from game seed,
entry identity and role. Constructor-seeded players own their `Random` instance;
process-global supplied RandomPlayer owns the generator in its dedicated process.
Unsupported seed APIs are labeled; deterministic duplicates remain duplicate
evidence. Diagnostics are optional and bounded by the existing worker protocol.

## Built-in catalog

| Logical ID | Actual implementation | Provenance / limitations |
| --- | --- | --- |
| phase1 | LegalBaseline from `c0c56fa40826719794f0765fd35464a5c0174cc3` | Retained Phase 1; deterministic, no search diagnostics |
| phase2 | IterativePlayer from `798963cae696eead8353232d1cc8c289cce473a9` | Retained Phase 2 material; deterministic, search diagnostics |
| phase3-material | IterativePlayer from `105a8f64edaeb86082425c1fecb12932c06c4367` | Retained Phase 3 default material; same engine family |
| phase3-effects | Same Phase 3 checkpoint plus archived effects-v1.json | Experimental full evaluator; related config variant, not an independent design |
| random | Unmodified supplied RandomPlayer through offline inheritance adapter | Professor source, recovered Player base; process-global seed |
| simple | Unmodified supplied SimplePlayer through offline inheritance adapter | Professor source, recovered Player base; deterministic |
| smoke | SeededSmokePlayer | Locally authored smoke behavior, constructor seed |

Git checkpoints restore the actual historical code, not current strategy renamed
as an old version. All built-ins were previously exposed: they are **training /
development evidence**. Validation and holdout are empty. Missing supplied files
are registered pending. Hidden TA agents and absent classmates are not listed as
played opponents. No strength qualification, pool independence, or untouched
holdout claim follows from these registry checks.

Add a historical champion with `Entry.checkpoint(..., origin='historical-champion',
commit=<full SHA>, factory='IterativePlayer', ...)`. Classmates use `Entry.local`
with a separate source bundle and a factory accepting explicit `color`; constructor
adaptations belong in that thin offline bundle, not in candidate/scheduler code.
Register missing expected bundles with `availability='pending'`. Save each new
record and create a new pool snapshot rather than editing an old version identity.

## Pool and exposure contract

`PoolSnapshot.freeze` requires explicit training, validation and holdout lists.
Each logical ID appears once. Variants sharing origin/family must stay in one
pool. Entries and complete membership are included in the snapshot digest;
`from_record` rejects changed membership under an old snapshot identity.

| Purpose | Selectable pools |
| --- | --- |
| development (default) | training, validation |
| training | training only |
| validation | validation only |
| final-evaluation (explicit) | training, validation, holdout |

`select()` defaults to every eligible entry; naming an ineligible entry raises
rather than silently excluding it. Candidate selection also checks reserved
membership/family, preventing a held-out version from being selected as the
candidate to bypass opponent safeguards. Reserved pool tests use controlled
entries only; no actual holdout competition runs in this ticket.

A game trace's `config.registry` retains both complete entries, the complete pool
snapshot, role seeds, setup reports, and opponent pool/exposure purpose. Its
`competitive-game-attempt` exposure includes failures/caps rather than silently
forgetting them; moves/events distinguish actual calls from setup-only failures.
The API caller must save returned traces; CLI saves them automatically. Preflight
failures raise before competitive execution. This ticket adds no batch scheduler
or global exposure ledger. Downstream batch tooling can aggregate these records.
If later holdout results influence tuning, keep the old snapshot and exposure
records and freeze a new snapshot with those families moved to validation; do not
rewrite earlier evidence or continue claiming they were untouched.
