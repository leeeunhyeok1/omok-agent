# Champion transactions (issue #43)

AI-written by OpenAI Codex under Phase 5 (#35), master #1.

The champion store is a single-owner, checksummed checkpoint. One atomic file
replacement commits the current champion, all immutable version bundles,
historical rotation, embedded eligibility evidence, and the decision together.
The checkpoint is authoritative; terminal output and exported reports are not.

Promotion consumes the saved `eligibility.json` and identity-bound
`eligibility-results.json`, reassessing all evidence under the saved promotion
policy. A saved deterministic rule chooses the eligible candidate with the
largest lower end of the fresh-confirmation sensitivity range, breaking ties by
immutable candidate identity. Result arrival order never selects a champion.
Every declared validation and official plan must be complete before any candidate
can promote, including plans belonging to other candidates. Missing evidence
cannot promote. Completed negative or inconclusive decisions
retain the incumbent and record each candidate's explanation.

Each retained version contains original registry identity and source bytes,
constructor configuration, runtime and dependency settings, parent champion,
eligibility policy and evidence identities, and limitations. Prior versions are
never edited by promotion or rollback. Historical rotation retains existing
slots and schedules each displaced incumbent. Eligibility must include all known
historical opponents and preserve their recorded rotation. Successful promotion
also retains the historical bundles and slots declared by its saved run.

Baseline context must contain `tactical_suite: {identity, sources}`: `sources`
maps fixed suite paths to SHA-256 hashes, and `identity` is the canonical digest
of that map. Each saved `mandatory_tactic` gate must carry the matching
`suite_identity`. Unidentified or changed suite evidence is recorded as
inconclusive. This binds a declared suite to its evidence; it does not establish
that an arbitrary external producer honestly ran its declared checks.

Export produces a complete, checksummed JSON artifact containing the version and
its source bundle. Reload verifies the artifact before materializing its files
inside a fresh worker snapshot. Each worker constructs a fresh player with empty
engine caches; it does not import the mutable original player path. The export
is an offline development artifact, not the final assignment submission package.
The compatible construction adapter is included and loaded from the archive.
The checkpoint stores evidence once under content identities; exports include
the referenced evidence and recorded decision as well as the version.

The transaction uses the existing flushed atomic replacement and owner lock.
Interruption before replacement leaves the previous checkpoint; interruption
after replacement resumes the recorded transaction without a duplicate. A
replayed eligibility transaction remains the same decision even after rollback.
Windows abrupt power-loss guarantees remain limited by filesystem behavior.

```sh
python -m offline.champions --store .scratch/champions initialize --incumbent incumbent.json --context baseline-context.json --reason "Verified Phase 5 baseline" --history history.json
python -m offline.champions --store .scratch/champions promote --checks .scratch/checks
python -m offline.champions --store .scratch/champions export --output .scratch/exports/champion.json
python -m offline.champions --store .scratch/champions show
python -m offline.champions --store .scratch/champions history --round 0
python -m offline.champions --store .scratch/champions rollback --version <saved-version-identity> --reason "Restore known baseline"
```

`ChampionStore.history()` returns the existing league archive shape plus the
recorded period and slots. Pass `champions` into `league.prepare(history=...)`
and preserve `history_period`/`history_slots` in the next saved `LeaguePolicy`.
`history(round_index)` exposes the scheduled subset for inspection. All source
bundles stay in `champions.json` even while their slot is not due. Export a
historical version and use `exported_spec(path, seed=...)` through the supervised
game API to execute its exact archive without depending on its original path.
League preparation converts original historical identities into portable archive
execution descriptors. Original identities and rotation slots stay unchanged in
the archive. Large player specifications travel through a checksummed file in
the supervised worker workspace, preserving the protocol's bounded frame limit.

`commit_evidence(checks, raw)` is the synthetic/external evidence boundary. It
validates then commits a snapshot; an existing different snapshot requires a new
check declaration. Normal eligibility execution already commits the same envelope
after each plan. Promotion reassesses that durable envelope, never a mutable
caller-supplied eligibility report. Missing evidence raises without modifying
the store. A later completed snapshot is a new transaction; a stale incumbent
cannot promote against a champion it was never compared with.

Run `python -m verification.champions --output .scratch/champion-pilot` to retain
a controlled improved-candidate promotion, exact export, rollback, and real
worker reload probes. The fixture outcomes establish transaction behavior, not
competitive strength. Configuration/cache probes explicitly use a controlled
accounting clock. See `docs/verification/issue-43.md` for retained results.
