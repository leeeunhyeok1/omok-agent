# AI-written by OpenAI Codex, for issue #27.
"""Resolved immutable schedules and bounded execution over the supervised runner."""
from collections.abc import Callable
from dataclasses import asdict, dataclass
import json
import os
from math import isfinite
from pathlib import Path
from typing import Any

from offline.measurement import conditions
from offline.registry import Entry, PoolSnapshot, ROOT, canonical, digest, player_seed
from offline.supervised import FORMAT as TRACE_FORMAT, Supervision
from omok.simulator import Position

FORMAT = 'omok-experiment-v1'
MODES = ('official', 'development', 'screening', 'fixture')
FAILURE_POLICY = {
    'version': 'raw-execution-v1', 'scoring': 'none; preserve rules and execution separately',
    'caps': 'no rules draw or player loss', 'setup_and_infrastructure': 'no player loss',
    'player_failure': 'retain offending color; match scoring deferred', 'retries': 'none',
}


def save_new_json(path: Path, value: dict[str, Any]) -> None:
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def execution_conditions(workers: int = 1, contention: str = 'external contention uncontrolled') -> dict[str, Any]:
    observed = conditions()
    observed.update(workers=workers, execution='bounded game supervisor threads; isolated player subprocesses',
        player_processes=2 * workers, start_method='fresh-python-subprocess',
        contention=contention, timing_comparison='serial wall-clock; verify declared contention' if workers == 1
        else 'concurrent wall-clock; contention affects strength; unsuitable for final timing comparison')
    try:
        sysconf = getattr(os, 'sysconf')
        observed['ram_bytes'] = sysconf('SC_PHYS_PAGES') * sysconf('SC_PAGE_SIZE')
    except (AttributeError, OSError, ValueError):
        observed['ram_bytes'] = None
    if os.name == 'nt':
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                        ('values', ctypes.c_ulonglong * 7)]
        memory = MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            observed['ram_bytes'] = memory.values[0]
    return observed


def portable_entry(entry: Entry) -> Entry:
    data = entry.data
    if data['loader']['kind'] == 'local':
        root = Path(data['loader']['root'])
        if root.is_absolute():
            try:
                root = root.resolve().relative_to(ROOT)
            except ValueError as error:
                raise ValueError('Vendor external sources inside the project for portable plans.') from error
        if '..' in root.parts:
            raise ValueError('Plan source roots must remain inside the project.')
        data['loader']['root'] = root.as_posix()
    return Entry(canonical(data))


def opening_record(moves: list[list[int]]) -> dict[str, Any]:
    position = Position.empty()
    for move in moves:
        position = position.play(move).position
    if position.outcome != 'ongoing':
        raise ValueError('Development openings must be live legal positions.')
    return {'kind': 'legal-sequence', 'moves': moves, 'board': position.board,
            'side_to_move': position.side_to_move}


def schedule(data: dict[str, Any]) -> list[dict[str, Any]]:
    settings = data['settings']
    candidate = Entry.from_record(data['candidate'])
    snapshot = PoolSnapshot.from_record(data['pool_snapshot'])
    snapshot.validate_candidate(candidate, purpose=settings['purpose'])
    # Runtime observations describe the run, rather than alter the intended games.
    experiment_id = digest({k: v for k, v in data.items() if k not in ('jobs', 'conditions')})
    jobs = []
    for pool, opponent in snapshot.select(settings['opponents'], purpose=settings['purpose']):
        match_id = digest([experiment_id, candidate.identity, opponent.identity])
        for slot in range(settings['games_per_opponent']):
            pair = slot // 2
            game_seed = player_seed(settings['seed'], opponent.identity, 'pair-' + str(pair))
            opening = settings['openings'][pair % len(settings['openings'])]
            job = {'match_id': match_id, 'slot': slot, 'pair': pair,
                'candidate_color': slot % 2, 'opponent': opponent.record(), 'pool': pool,
                'opening': opening, 'game_seed': game_seed,
                'seeds': {role: player_seed(game_seed, version, role) for role, version in
                          (('candidate', candidate.identity), ('opponent', opponent.identity))},
                'seed_support': {'candidate': candidate.data['seed_support'],
                                 'opponent': opponent.data['seed_support']}}
            deterministic = all(s == 'deterministic' for s in job['seed_support'].values())
            job['duplicate_evidence_group'] = digest([candidate.identity, opponent.identity,
                job['candidate_color'], opening]) if deterministic else None
            job['seed_limitations'] = [role + ': ' + support for role, support in
                job['seed_support'].items() if support in ('unsupported', 'deterministic')]
            job['game_id'] = digest(job)
            jobs.append(job)
    return jobs


@dataclass(frozen=True)
class ExperimentPlan:
    definition: str

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self.definition)

    @property
    def identity(self) -> str:
        return digest(self.data)

    def record(self) -> dict[str, Any]:
        return {'identity': self.identity, **self.data}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        save_new_json(path, self.record())

    @classmethod
    def load(cls, path: Path) -> 'ExperimentPlan':
        return cls.from_record(json.loads(path.read_text(encoding='utf-8')))

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'ExperimentPlan':
        data = dict(record)
        identity = data.pop('identity')
        if data['format'] != FORMAT or digest(data) != identity:
            raise ValueError('Experiment format or identity mismatch.')
        settings = data['settings']
        start = settings['openings'][0]
        restored = cls.resolve(Entry.from_record(data['candidate']),
            PoolSnapshot.from_record(data['pool_snapshot']), mode=settings['mode'],
            opponents=settings['opponents'], purpose=settings['purpose'], seed=settings['seed'],
            games_per_opponent=settings['games_per_opponent'], total_ms=settings['budgets_ms'][0],
            move_cap=settings['move_cap'], diagnostics=settings['diagnostics'],
            supervision=Supervision(**settings['supervision']),
            openings=[s['moves'] for s in settings['openings']] if settings['mode'] not in ('official', 'fixture') else None,
            fixture=Position(start['board'], start['side_to_move']) if settings['mode'] == 'fixture' else None)
        if canonical({k: v for k, v in restored.data.items() if k != 'conditions'}) != canonical(
                {k: v for k, v in data.items() if k != 'conditions'}):
            raise ValueError('Saved jobs disagree with the resolved schedule.')
        return cls(canonical(data))

    @classmethod
    def resolve(cls, candidate: Entry, snapshot: PoolSnapshot, *, mode: str = 'development',
            opponents: list[str] | None = None, purpose: str = 'development',
            seed: int = 20261010, games_per_opponent: int = 8,
            total_ms: float | None = 60000, move_cap: int = 1000,
            openings: list[list[list[int]]] | None = None,
            fixture: Position | None = None, supervision: Supervision | None = None,
            diagnostics: bool = False) -> 'ExperimentPlan':
        if mode not in MODES:
            raise ValueError('Unknown experiment mode.')
        if type(seed) is not int:
            raise ValueError('Seed must be an integer.')
        if type(games_per_opponent) is not int or games_per_opponent <= 0 or games_per_opponent % 2:
            raise ValueError('Games per opponent must be positive and even.')
        if type(move_cap) is not int or move_cap < 0:
            raise ValueError('Move cap must be a nonnegative integer.')
        if total_ms is not None and (isinstance(total_ms, bool) or not isfinite(total_ms) or total_ms < 0):
            raise ValueError('Clock must be finite nonnegative milliseconds or None.')
        if mode == 'official' and (total_ms != 60000 or games_per_opponent != 8 or openings or fixture):
            raise ValueError('Official mode requires eight empty-board games and 60000 ms per player.')
        if mode == 'screening' and (total_ms is None or total_ms >= 60000):
            raise ValueError('Screening requires a reduced finite total wall-clock budget.')
        if (mode == 'fixture') != (fixture is not None):
            raise ValueError('Fixture mode requires an explicit fixture, exclusive to that mode.')
        if fixture is not None and openings:
            raise ValueError('Fixtures cannot be mixed with legal development openings.')
        if candidate.data['availability'] != 'ready':
            raise ValueError('Requested candidate is ' + candidate.data['availability'])
        candidate = portable_entry(candidate)
        pools = {pool: [portable_entry(Entry.from_record(r)) for r in records]
                 for pool, records in json.loads(snapshot.definition).items()}
        snapshot = PoolSnapshot.freeze(pools)
        selected = snapshot.select(opponents, purpose=purpose)
        if not selected:
            raise ValueError('Experiment must request at least one opponent.')
        starts = [opening_record(moves) for moves in (openings if openings is not None else [[]])]
        if not starts:
            raise ValueError('Opening list must not be empty.')
        if fixture is not None:
            starts = [{'kind': 'artificial-fixture', 'moves': None, 'board': fixture.board,
                       'side_to_move': fixture.side_to_move}]
        observed = execution_conditions()
        data: dict[str, Any] = {'format': FORMAT, 'trace_format': TRACE_FORMAT, 'candidate': candidate.record(),
            'pool_snapshot': snapshot.record(), 'conditions': observed,
            'settings': {'mode': mode, 'purpose': purpose, 'seed': seed,
                'opponents': [e.data['logical_id'] for _, e in selected],
                'games_per_opponent': games_per_opponent, 'budgets_ms': [total_ms, total_ms],
                'budget_mechanism': 'reduced-total-wall-clock' if mode == 'screening' else
                                    'externally-capped-unlimited' if total_ms is None else 'total-wall-clock',
                'move_cap': move_cap, 'openings': starts, 'diagnostics': diagnostics,
                'clock_policy': 'dispatch-through-response; cumulative; floor argument milliseconds',
                'seed_policy': 'paired role seeds; colors alternate; sha256-v1',
                'opening_policy': 'same recorded opening in each color pair; cycle by pair',
                'failure_policy': FAILURE_POLICY, 'supervision': asdict(supervision or Supervision()),
                'resources': {'workers': 1, 'player_processes': 2,
                              'start_method': 'fresh-python-subprocess',
                              'contention': 'external contention uncontrolled'}}}
        data['jobs'] = schedule(data)
        return cls(canonical(data))


def execute_job(plan: ExperimentPlan, job: dict[str, Any], check_stop: Callable[[], None] | None = None) -> dict[str, Any]:
    from offline.supervised import preflight_player, run_supervised_game
    data = plan.data
    candidate = Entry.from_record(data['candidate'])
    settings = data['settings']
    policy = Supervision(**settings['supervision'])
    opponent = Entry.from_record(job['opponent'])
    entries = [candidate, opponent] if job['candidate_color'] == 0 else [opponent, candidate]
    roles = ['candidate', 'opponent'] if job['candidate_color'] == 0 else ['opponent', 'candidate']
    specs = [entry.spec(job['seeds'][roles[c]]) for c, entry in enumerate(entries)]
    record: dict[str, Any] = {'game_id': job['game_id'], 'match_id': job['match_id'],
        'slot': job['slot'], 'candidate_color': job['candidate_color'], 'trace': None,
        'status': 'setup_failed', 'preflight': [], 'error': None}
    try:
        for entry in entries:
            for color in (0, 1):
                report = preflight_player(entry.spec(job['seeds'][
                    'candidate' if entry.identity == candidate.identity else 'opponent']), color, policy, check_stop=check_stop)
                record['preflight'].append({'identity': entry.identity, 'color': color, **report})
                if not report['ready']:
                    raise ValueError('Preflight failed: ' + str(report['detail']))
        start = job['opening']
        trace = run_supervised_game(*specs, initial=Position(start['board'], start['side_to_move']),
            budgets_ms=tuple(settings['budgets_ms']), move_cap=settings['move_cap'],
            supervision=policy, diagnostics=settings['diagnostics'], check_stop=check_stop, config={'experiment': {
                'manifest_identity': plan.identity, 'job': job, 'mode': settings['mode'],
                'candidate': candidate.record(), 'purpose': settings['purpose']},
                'registry': {'format': 'omok-registry-game-v1',
                    'candidate': candidate.record(), 'opponent': opponent.record(),
                    'candidate_color': job['candidate_color'],
                    'pool_snapshot': data['pool_snapshot'], 'game_seed': job['game_seed'],
                    'seeds': [job['seeds'][role] for role in roles],
                    'preflight': record['preflight'], 'exposure': {
                        'purpose': settings['purpose'], 'pool': job['pool'],
                        'identity': opponent.identity, 'kind': 'competitive-game-attempt'
                        if settings['mode'] != 'fixture' else 'fixture-game-attempt'}}})
        record.update(trace=trace, status=trace['status'])
    except (ValueError, TypeError, KeyError, OSError) as error:
        record['error'] = {'type': type(error).__name__, 'message': str(error)}
    trace = record['trace']
    calls = [sum(event['type'] == 'returned' and event['color'] == color
                 for event in trace['events']) for color in (0, 1)] if trace else [0, 0]
    record['exposure'] = {'purpose': settings['purpose'], 'pool': job['pool'],
        'candidate_identity': candidate.identity, 'opponent_identity': opponent.identity,
        'kind': ('fixture-turn-attempt' if settings['mode'] == 'fixture' else 'competitive-turn-attempt')
                if any(calls) else 'no-player-turns',
        'turns_called': calls, 'applied_moves': len(trace['moves']) if trace else 0}
    return record


def run_experiment(plan: ExperimentPlan, *, output: Path | None = None,
        resume: bool = False, max_jobs: int | None = None, max_seconds: float | None = None,
        stop_requested: Callable[[], bool] | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
        infrastructure_retries: int | None = None, workers: int = 1,
        contention: str = 'external contention uncontrolled') -> dict[str, Any]:
    """Execute saved jobs with one commit owner and bounded concurrent supervision."""
    from offline.batches import run_batch
    return run_batch(plan, output=output, resume=resume, max_jobs=max_jobs,
        max_seconds=max_seconds, stop_requested=stop_requested, progress=progress,
        infrastructure_retries=infrastructure_retries, workers=workers, contention=contention)
