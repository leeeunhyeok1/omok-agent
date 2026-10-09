# Issue #26 acceptance and review

AI-written by OpenAI Codex. Implemented **Play immutable registry entries with
protected pool selection** against issue #26, Phase 04 issue #24, and master
context issue #1. No LLM usage records were created. The simulator, candidate
strategies, evaluator/config sources, and search/time policies remain unchanged.
The public testing seam is complete runner/tournament operation, already agreed
in both the master and Phase 04 specifications.

The [registry contract](../registry.md) describes the entry schema, checkpoint
loading, dependencies, seed ownership, protected selection, and exposure records.
The default catalog contains seven versions: actual Phase 1/2/3 archives,
experimental Phase 3 effects configuration, unchanged supplied Random/Simple
sources, and smoke. All are already-exposed training evidence. Validation and
holdout are explicitly empty; reserved-pool checks use controlled fixtures only.
Historical champions and separate classmate bundles use the same entry interface.

## Acceptance evidence

`tests.test_registry` contains 13 public-operation tests covering:

- Supervised game/replay, complete immutable provenance, pool snapshot, exposure purpose and independent role seeds.
- Ordinary holdout exclusion, explicit final evaluation, training/validation separation, and reserved candidate-role safeguards.
- Entry/snapshot tampering and related-family split rejection; returned dictionaries cannot mutate frozen definitions.
- Changed helpers/configuration and newly added assets rejected under an old version.
- Same-named external player/helper modules isolated across workers.
- Missing imports, invalid configuration, explicit wrong color, unavailable entries and bounded import/constructor loops.
- Supported seeded players repeat without sharing a mutable generator.
- All retained checkpoints load their actual sources and play; supplied origin/seed metadata is accurate.
- Lazy imports use copied sources even if the original helper changes during the game.
- Saved registry CLI selection as white, replay, and refusal to overwrite existing evidence.
- Absolute/traversing/missing evaluator paths rejected, including changed external JSON coefficients.

The first tracer test failed before the registry module existed. Historical
checkpoint registration and added-source rejection also had failing tests before
implementation. The review-found evaluator-path regression failed on all four
attempts before its fix. Existing agreed simulator/public-player tests remain
regression gates.

[Saved catalog](issue-26-registry.json.gz) retains full entries, source/adapter
hashes, runtime and training/validation/holdout membership. Four bounded empty-board
development games exercise Phase 3 material against real RandomPlayer/SimplePlayer
in both colors. [The summary](issue-26-games.json) links their compressed traces.
Each used seed 20261010, diagnostics, 60,000 ms cumulative clocks, and a 12-move cap.
All four replayed, had no reliability failure, and reaped both player workers.
Three were capped; SimplePlayer as white reached an exact-five result at move 12.
These are infrastructure checks, not eight-game qualification or strength evidence.
Concurrent regression/review activity is explicitly recorded as uncontrolled
contention; no timing/strength comparison is inferred.

Replay the preserved records without players:

```sh
python3 - <<'PY'
import gzip, json
from pathlib import Path
from offline.replay import replay
from offline.registry import Entry, PoolSnapshot
root = Path('docs/verification')
catalog = json.loads(gzip.decompress((root / 'issue-26-registry.json.gz').read_bytes()))
for record in catalog['entries']:
    Entry.from_record(record)
PoolSnapshot.from_record(catalog['pool_snapshot'])
for game in json.loads((root / 'issue-26-games.json').read_text())['games']:
    replay(json.loads(gzip.decompress((root / game['trace']).read_bytes())))
print('Registry identities and four game replays valid')
PY
```

## Standards

Independent Standards reviewer, against initial HEAD
`af609cee4290e955b83da7ee7ea22461237aeb71`, using AGENTS.md, agent guidance, runner/
registry contracts and the code-review skill's complete smell baseline:

> Standards recheck passes: 0 documented-standard violations and 0 remaining
> actionable smell findings. `PoolSnapshot.validate_candidate` resolves the
> previous Feature Envy suggestion. The evaluator-path validation follows the
> documented immutable source snapshot contract.

## Spec

Independent Spec reviewer using issues #26, #24 and #1:

> Spec review of `af609cee...c6858af`: 0 remaining findings. The original
> immutable-configuration bypass is fixed: my public API reproduction now rejects
> the external evaluator path during registration. A legitimate archived evaluator
> asset remains accepted. The worker also checks resolved containment and manifest
> membership. No further missing requirements, scope creep, or incorrect
> implementations found within issue #26's bounded scope.

The initial review reproduced absolute `evaluation_path` loading mutable JSON
outside the snapshot. Registration now requires a relative verified asset and
workers check resolved containment/membership. The optional Standards suggestion
moved candidate membership interpretation into `PoolSnapshot`.

Final findings: Standards 0; Spec 0. Neither axis has a remaining worst issue.

## Final verification

- `python3 -m unittest tests.test_registry -q`: **13 passed**, 19.661 seconds.
- `python3 -m unittest discover -s tests -q`: **191 passed**, 59.019 seconds after review fixes.
- `.scratch/issue-21-tools/bin/python -m mypy omok offline --follow-imports=silent`: **27 source files passed**.
- `python3 -m compileall -q omok offline verification tests`: passed.
- `git diff --check`: passed.
- Saved catalog identities and all four recorded game replays checked.

Verified locally on Python 3.14.3/macOS. Installed third-party dependencies must
be vendored and declared; the registrar remains responsible for transitive
completeness. Moving a registry requires its bundle roots, retained Git objects
and matching runtime. Batch scheduling/global exposure aggregation are later
framework work. No real reserved opponent was consumed. Unrelated pre-existing
worktree changes were excluded from the commit.
