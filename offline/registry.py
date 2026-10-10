# AI-written by OpenAI Codex, for issue #26.
"""Immutable offline player descriptions, pool snapshots, and supervised selection."""
from dataclasses import dataclass
from hashlib import sha256
import json
import io
import subprocess
import tarfile
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any

from offline.supervised import PlayerSpec, Supervision, run_supervised_game, preflight_player

ROOT = Path(__file__).resolve().parents[1]
POOLS = ('training', 'validation', 'holdout')
PURPOSES = ('development', 'training', 'validation', 'final-evaluation')


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value: Any) -> str:
    return sha256(canonical(value).encode()).hexdigest()


def source_snapshot(root: Path, paths: tuple[str, ...], *, allow_missing: bool = False) -> dict[str, str]:
    sources: dict[str, str] = {}
    for name in paths:
        path = root / name
        if not path.exists():
            if not allow_missing:
                raise RegistryError('Missing registered source: ' + str(path))
            continue
        files = sorted(path.rglob('*')) if path.is_dir() else [path]
        for file in files:
            if (file.is_file() and file.suffix not in ('.pyc', '.pyo')
                    and not any(part in ('__pycache__', '.git') for part in file.relative_to(root).parts)
                    and file.name != '.DS_Store'):
                relative = file.resolve().relative_to(root.resolve()).as_posix()
                sources[relative] = sha256(file.read_bytes()).hexdigest()
    return sources


class RegistryError(ValueError):
    """A requested version cannot be used as registered."""


@dataclass(frozen=True)
class Entry:
    # Store canonical JSON, rather than a mutable options/source dictionary.
    definition: str

    def __post_init__(self) -> None:
        data = json.loads(self.definition)
        required = ('logical_id', 'origin', 'family', 'variant', 'loader', 'options',
                    'sources', 'dependencies', 'availability', 'acknowledgment',
                    'seed_support', 'diagnostics', 'limitations', 'color_mapping', 'source_paths', 'runtime', 'adapter_sources')
        if not isinstance(data, dict) or set(data) != set(required):
            raise RegistryError('Incomplete registry entry.')
        if data['color_mapping'] != {'black': 0, 'white': 1, 'constructor': 'color'}:
            raise RegistryError('Unsupported or ambiguous color mapping.')
        if data['availability'] not in ('ready', 'pending', 'unavailable'):
            raise RegistryError('Invalid availability.')
        if data['seed_support'] not in ('constructor', 'process-global', 'deterministic', 'unsupported'):
            raise RegistryError('Invalid seed interface.')
        if any(not isinstance(data[key], str) or not data[key] for key in
               ('logical_id', 'origin', 'family', 'acknowledgment')):
            raise RegistryError('IDs, family, origin and acknowledgment must be explicit.')
        if 'evaluation_path' in data['options']:
            value = data['options']['evaluation_path']
            if (not isinstance(value, str) or Path(value).is_absolute()
                    or '..' in Path(value).parts or value not in data['sources']):
                raise RegistryError('Evaluator path must identify a verified asset inside the source snapshot.')
        object.__setattr__(self, 'definition', canonical(data))

    @property
    def identity(self) -> str:
        return sha256(self.definition.encode()).hexdigest()

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self.definition)

    def record(self) -> dict[str, Any]:
        return {'identity': self.identity, **self.data}

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'Entry':
        data = dict(record)
        expected = data.pop('identity')
        entry = cls(canonical(data))
        if entry.identity != expected:
            raise RegistryError('Registry identity does not match its immutable definition.')
        return entry

    @classmethod
    def local(cls, logical_id: str, *, module: str, factory: str,
              options: dict[str, Any] | None = None, source_paths: tuple[str, ...],
              origin: str, family: str, acknowledgment: str, variant: str = 'v1',
              source_root: Path = ROOT, dependencies: tuple[str, ...] = (),
              availability: str = 'ready', seed_support: str = 'deterministic',
              diagnostics: tuple[str, ...] = (), limitations: str = '') -> 'Entry':
        root = source_root.resolve()
        sources = source_snapshot(root, source_paths, allow_missing=availability != 'ready')
        if not sources and availability == 'ready':
            raise RegistryError('Ready entries require a source/dependency snapshot.')
        # Repository-relative roots remain portable; external bundles may use absolute roots.
        location = '.' if root == ROOT else str(root)
        return cls(canonical({'logical_id': logical_id, 'origin': origin, 'family': family,
            'variant': variant, 'loader': {'kind': 'local', 'root': location,
                                         'module': module, 'factory': factory},
            'options': options or {}, 'sources': sources, 'source_paths': list(source_paths),
            'runtime': sys.version, 'dependencies': list(dependencies),
            'adapter_sources': source_snapshot(ROOT, ('offline',)),
            'availability': availability, 'acknowledgment': acknowledgment,
            'seed_support': seed_support, 'diagnostics': list(diagnostics),
            'limitations': limitations,
            'color_mapping': {'black': 0, 'white': 1, 'constructor': 'color'}}))

    @classmethod
    def checkpoint(cls, logical_id: str, *, commit: str, factory: str,
                   options: dict[str, Any] | None = None, variant: str = 'retained',
                   origin: str = 'retained-engine', acknowledgment: str = 'Local AI-written engine') -> 'Entry':
        paths = ('omok', 'players', 'configs') if 'evaluation_path' in (options or {}) else ('omok', 'players')
        archive = checkpoint_archive(commit, paths)
        with TemporaryDirectory(prefix='omok-registration-') as directory:
            root = Path(directory)
            with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
                stream.extractall(root, filter='data')
            entry = cls.local(logical_id, module='omok.player', factory=factory,
                options=options, source_paths=paths, source_root=root, origin=origin,
                family='omok', variant=variant, acknowledgment=acknowledgment,
                diagnostics=('search',) if factory == 'IterativePlayer' else (),
                limitations='Related engine versions; deterministic duplicates are not independent evidence.')
        data = entry.data
        data['loader'] = {'kind': 'checkpoint', 'commit': commit, 'paths': list(paths),
                          'module': 'omok.player', 'factory': factory}
        return cls(canonical(data))

    def spec(self, seed: int) -> PlayerSpec:
        if self.data['availability'] != 'ready':
            raise RegistryError(f"Requested opponent {self.data['logical_id']} is {self.data['availability']}.")
        return PlayerSpec('offline.registry_worker', 'create', {'entry': self.record(), 'seed': seed}, seed)


def checkpoint_archive(commit: str, paths: tuple[str, ...]) -> bytes:
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise RegistryError('Checkpoint requires a full immutable commit SHA.')
    try:
        return subprocess.check_output(['git', 'archive', commit, *paths], cwd=ROOT,
                                       timeout=5, stderr=subprocess.PIPE)
    except (OSError, subprocess.SubprocessError) as error:
        raise RegistryError('Required checkpoint unavailable: ' + commit) from error


@dataclass(frozen=True)
class PoolSnapshot:
    definition: str

    def __post_init__(self) -> None:
        data = json.loads(self.definition)
        if set(data) != set(POOLS):
            raise RegistryError('A snapshot must explicitly contain all three pools.')
        seen: set[str] = set()
        families: dict[tuple[str, str], str] = {}
        for pool in POOLS:
            for record in data[pool]:
                entry = Entry.from_record(record)
                name = entry.data['logical_id']
                if name in seen:
                    raise RegistryError('Duplicate logical ID in pool snapshot: ' + name)
                seen.add(name)
                family = (entry.data['origin'], entry.data['family'])
                if family in families and families[family] != pool:
                    raise RegistryError('Related design variants must remain in one pool.')
                families[family] = pool
        object.__setattr__(self, 'definition', canonical(data))

    @classmethod
    def freeze(cls, pools: dict[str, list[Entry]]) -> 'PoolSnapshot':
        return cls(canonical({pool: sorted([e.record() for e in entries],
                             key=lambda e: e['logical_id']) for pool, entries in pools.items()}))

    @property
    def identity(self) -> str:
        return sha256(self.definition.encode()).hexdigest()

    def record(self) -> dict[str, Any]:
        return {'identity': self.identity, 'pools': json.loads(self.definition)}

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'PoolSnapshot':
        snapshot = cls(canonical(record['pools']))
        if snapshot.identity != record['identity']:
            raise RegistryError('Pool snapshot identity mismatch.')
        return snapshot

    def validate_candidate(self, candidate: Entry, *, purpose: str) -> None:
        # Related versions cannot bypass reserved membership by changing role/ID.
        for records in json.loads(self.definition).values():
            for record in records:
                if (record['identity'] == candidate.identity
                        or (record['family'], record['origin']) ==
                           (candidate.data['family'], candidate.data['origin'])):
                    self.select([record['logical_id']], purpose=purpose)

    def select(self, names: list[str] | None = None, *, purpose: str = 'development') -> list[tuple[str, Entry]]:
        if purpose not in PURPOSES:
            raise RegistryError('Unknown exposure purpose: ' + purpose)
        allowed = {'development': ('training', 'validation'), 'training': ('training',),
                   'validation': ('validation',), 'final-evaluation': POOLS}[purpose]
        available = {r['logical_id']: (pool, Entry.from_record(r))
                     for pool, records in json.loads(self.definition).items() for r in records}
        selected = list(names) if names is not None else [name for name, (pool, _) in available.items()
                                                        if pool in allowed]
        if len(set(selected)) != len(selected):
            raise RegistryError('Duplicate requested opponent.')
        result = []
        for name in selected:
            if name not in available:
                raise RegistryError('Unknown requested opponent: ' + name)
            pool, entry = available[name]
            if pool not in allowed:
                raise RegistryError(f'{name} belongs to protected {pool}; purpose {purpose} cannot select it.')
            if entry.data['availability'] != 'ready':
                raise RegistryError(f"Requested opponent {name} is {entry.data['availability']}.")
            result.append((pool, entry))
        return result


def player_seed(seed: int, identity: str, role: str) -> int:
    if type(seed) is not int:
        raise RegistryError('Game seed must be an integer.')
    return int(digest([seed, identity, role])[:16], 16)


def run_registered_game(candidate: Entry, snapshot: PoolSnapshot, opponent_id: str, *,
                        candidate_color: int = 0, purpose: str = 'development', seed: int = 0,
                        supervision: Supervision | None = None, **game_options: Any) -> dict[str, Any]:
    if type(candidate_color) is not int or candidate_color not in (0, 1):
        raise RegistryError('Candidate color must be 0 or 1.')
    snapshot.validate_candidate(candidate, purpose=purpose)
    pool, opponent = snapshot.select([opponent_id], purpose=purpose)[0]
    entries = [candidate, opponent] if candidate_color == 0 else [opponent, candidate]
    seeds = [player_seed(seed, entry.identity, 'candidate' if c == candidate_color else 'opponent')
             for c, entry in enumerate(entries)]
    specs = [entry.spec(seeds[c]) for c, entry in enumerate(entries)]
    policy = supervision or Supervision()
    preflight = []
    # Validate both constructor/color adapters, without calling take_turn or consuming holdout results.
    for entry in entries:
        for color in (0, 1):
            report = preflight_player(entry.spec(player_seed(seed, entry.identity, 'preflight')), color, policy)
            preflight.append({'identity': entry.identity, 'color': color, **report})
            if not report['ready']:
                raise RegistryError(f"Preflight failed for {entry.data['logical_id']} ({entry.identity}): {report['detail']}")
    config = dict(game_options.pop('config', {}) or {})
    config['registry'] = {'format': 'omok-registry-game-v1', 'candidate': candidate.record(),
        'opponent': opponent.record(), 'candidate_color': candidate_color,
        'pool_snapshot': snapshot.record(), 'game_seed': seed, 'seeds': seeds,
        'preflight': preflight, 'exposure': {'purpose': purpose, 'pool': pool,
            'identity': opponent.identity, 'kind': 'competitive-game-attempt'}}
    return run_supervised_game(*specs, supervision=policy, config=config, **game_options)


# These are verified checkpoint identities, not reimplementations of older strategies.
PHASE1 = 'c0c56fa40826719794f0765fd35464a5c0174cc3'
PHASE2 = '798963cae696eead8353232d1cc8c289cce473a9'
PHASE3 = '105a8f64edaeb86082425c1fecb12932c06c4367'


def default_catalog() -> tuple[dict[str, Entry], PoolSnapshot]:
    entries = [Entry.checkpoint('phase1', commit=PHASE1, factory='LegalBaseline', variant='phase1-baseline'),
               Entry.checkpoint('phase2', commit=PHASE2, factory='IterativePlayer', variant='phase2-material'),
               Entry.checkpoint('phase3-material', commit=PHASE3, factory='IterativePlayer', variant='phase3-material'),
               Entry.checkpoint('phase3-effects', commit=PHASE3, factory='IterativePlayer',
                                options={'evaluation_path': 'configs/effects-v1.json'}, variant='phase3-experimental-effects')]
    for name in ('random', 'simple', 'smoke'):
        supplied = name != 'smoke'
        entries.append(Entry.local(name, module='offline.worker_players', factory='create',
            options={'name': name, 'supplied': supplied}, source_paths=('omok', 'offline', 'players') if supplied else ('omok', 'offline'),
            origin='professor-provided' if supplied else 'synthetic', family='provided-' + name if supplied else 'random-smoke',
            acknowledgment='Professor-provided source; recovered Player base, see issue #7.' if supplied else 'Local AI-written smoke bot.',
            availability='ready' if not supplied or all((ROOT / 'players' / file).is_file()
                for file in ('player.py', name + 'player.py')) else 'pending',
            seed_support='process-global' if name == 'random' else 'constructor' if name == 'smoke' else 'deterministic',
            limitations='Already exposed during development; not reserved validation/holdout evidence.'))
    # Issue #30: benchmark-only strategies and related variants have explicit pools.
    synthetic_pools = synthetic_catalog()
    pools = {'training': entries + synthetic_pools['training'],
             'validation': synthetic_pools['validation'], 'holdout': synthetic_pools['holdout']}
    all_entries = [entry for pool in pools.values() for entry in pool]
    return ({e.data['logical_id']: e for e in all_entries}, PoolSnapshot.freeze(pools))


def synthetic_catalog() -> dict[str, list[Entry]]:
    """Freeze locally authored designs; metadata only does not expose holdout play."""
    definitions = (
        ('local', 'local-density', 'training', 'Own-neighbor density; ignores remote tactics.'),
        ('aggressive', 'line-pattern', 'training', 'Own maximal run extension; ignores opponent replies.'),
        ('pattern', 'line-pattern', 'training', 'Unblocked five-cell windows including gaps; not forced threats.'),
        ('capture', 'capture-collection', 'training', 'Actual captured cells before central tie breaking; no capture win rule.'),
        ('search1', 'reply-minimax', 'training', 'One-ply cubic maximal-run evaluation; eight ranked moves plus immediate win/block cells.'),
        ('search2', 'reply-minimax', 'training', 'Two-ply worst-reply minimax with the same bounded move policy.'),
        ('random', 'frontier-random', 'training', 'Uniform seeded adjacent frontier selection; no tactical override.'),
        ('defensive', 'reply-denial', 'validation', 'Minimize actual immediate opponent wins, then remaining run pressure.'),
        ('space', 'space-filling', 'holdout', 'Maximize distance from occupied cells; reserved, unplayed design.'),
    )
    pools: dict[str, list[Entry]] = {pool: [] for pool in POOLS}
    for strategy, family, pool, behavior in definitions:
        pools[pool].append(Entry.local('synthetic-' + strategy,
            module='offline.synthetic', factory='create', options={'strategy': strategy},
            source_paths=('offline', 'omok/__init__.py', 'omok/simulator.py'),
            origin='synthetic', family=family, variant=strategy + '-v1',
            acknowledgment='Locally authored by OpenAI Codex for issue #30; no external strategy source.',
            seed_support='constructor' if strategy == 'random' else 'deterministic',
            dependencies=(), limitations=behavior + ' Shared rules, source bundle and line utilities limit independent family coverage; see docs/synthetic.md.'))
    return pools
