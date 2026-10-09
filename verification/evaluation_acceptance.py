# AI-written by OpenAI Codex, for issue #22.
"""Bounded Phase 3 evidence; no league, holdout or parameter optimization."""
import argparse
from collections import Counter
from dataclasses import replace
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import random
import subprocess
import sys
import tarfile
from time import monotonic
from typing import Any

from offline.compare import compare
from offline.fixtures import fixture
from offline.measurement import conditions, engine_sources, evaluation_identity, configured_search, search_settings
from offline.provided import load_players, SOURCES
from offline.replay import replay
from offline.runner import run_game
from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
from omok.player import IterativePlayer, TimePolicy
from omok.simulator import Position
from verification.acceptance import distribution, write

CHECKPOINT = '798963cae696eead8353232d1cc8c289cce473a9'
FAMILIES = ('lines', 'potential', 'captures', 'effects', 'multiplicity')
ROOT = Path(__file__).resolve().parents[1]


def configurations() -> dict[str, EvaluationConfig]:
    complete = EvaluationConfig.load(ROOT / 'configs/effects-v1.json')
    disabled: dict[str, Any]
    ablations = {}
    for family in FAMILIES:
        disabled = {family + '_enabled': False}
        ablations['without-' + family] = replace(complete, **disabled)
    return {'old': EvaluationConfig(), 'new': complete,
            **ablations}


def checkpoint_path() -> Path:
    destination = ROOT / '.scratch/issue-22-phase2' / CHECKPOINT
    archive = subprocess.check_output(['git', 'archive', CHECKPOINT, 'omok'], cwd=ROOT)
    # Re-extract the immutable git object each time, rather than trusting stale files.
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(destination, filter='data')
    return destination


class PhaseTwoPlayer:
    """Isolate checkpoint imports. Timed IPC is an explicitly reported coupling."""
    def __init__(self, color: int) -> None:
        self.color = color
        code = '''import json, sys
from omok.player import IterativePlayer
p = IterativePlayer(int(sys.argv[1]))
for line in sys.stdin:
    board, remaining = json.loads(line)
    move = p.take_turn(board, remaining)
    print(json.dumps({'move': move, 'search': p.diagnostics()}), flush=True)
'''
        self.process = subprocess.Popen([sys.executable, '-u', '-c', code, str(color)],
            cwd=checkpoint_path(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.last: dict[str, Any] | None = None

    def take_turn(self, board: list[list[int]], time: float) -> tuple[int, int]:
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(json.dumps([board, time]) + '\n')
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        if not response:
            raise RuntimeError('Phase 2 subprocess exited.')
        data = json.loads(response)
        self.last = data['search']
        return tuple(data['move'])

    def diagnostics(self) -> dict[str, Any] | None:
        return self.last

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()


def diagnostic_starts() -> dict[str, Position]:
    starts = {name: fixture(name) for name in ('empty', 'dense', 'opponent-win')}
    board = [list(row) for row in Position.empty().board]
    board[9][6:10] = [1] * 4
    board[8][7], board[10][7] = 1, 0
    starts['capture-defense'] = Position(board, 0)
    edge = [list(row) for row in Position.empty().board]
    edge[0][0:3] = [0] * 3
    edge[1][2] = 1
    starts['edge'] = Position(edge, 1)
    # Reconstruct an actual SimplePlayer loss, then retain a nonterminal midgame.
    path = ROOT / 'docs/verification/issue-15/official-simple-black-20261009.json.gz'
    with gzip.open(path, 'rt') as stream:
        trace = json.load(stream)
    replay(trace)
    position = Position(trace['initial']['board'], trace['initial']['side_to_move'])
    for event in trace['moves'][:len(trace['moves']) // 2]:
        position = position.play(tuple(event['move'])).position
    starts['simple-loss-midpoint'] = position
    return starts


def gate(output: Path) -> None:
    modules = ['tests.test_evaluation', 'tests.test_lines', 'tests.test_potential',
               'tests.test_captures', 'tests.test_threat_effects', 'tests.test_measurement',
               'tests.test_search', 'tests.test_transposition', 'tests.test_iterative',
               'tests.test_tactics', 'tests.test_player', 'tests.test_provided',
               'tests.test_integration', 'tests.test_replay', 'tests.test_runner',
               'tests.test_simulator', 'tests.test_reference']
    command = [sys.executable, '-m', 'unittest', *modules, '-q']
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    report = {'command': command, 'returncode': process.returncode,
              'stdout': process.stdout, 'stderr': process.stderr,
              'conditions': conditions(), 'engine_source_sha256': engine_sources()}
    write(output / 'gate.json', report)
    if process.returncode:
        raise RuntimeError('Regression gate failed; do not run strength experiments.')


def development(output: Path) -> None:
    configs = configurations()
    report: dict[str, Any] = {'conditions': conditions(), 'engine_source_sha256': engine_sources(),
                             'comparisons': [], 'inspections': [],
                             'loss_source': 'issue-15/official-simple-black-20261009.json.gz',
                             'loss_explanation': 'material/horizon explanations remain hypotheses'}
    starts = diagnostic_starts()
    for name, initial in starts.items():
        for route in ('fixed-depth', 'node-budget'):
            result = compare(list(configs.values()), initial, route=route,
                             depth=2, cap=2, nodes=12, profile_every=1)
            result['fixture'] = name
            result['configuration_names'] = list(configs)
            report['comparisons'].append(result)
        report['inspections'].append({'fixture': name, 'report':
                                      ConfiguredEvaluator(configs['new']).inspect(initial)})
        write(output / 'development.json', report)
        print(json.dumps({'development': name}), flush=True)

    probes = []
    for name in ('empty', 'capture-defense', 'dense', 'simple-loss-midpoint'):
        for color in (0, 1):
            initial = Position(starts[name].board, color)
            for version in ('old', 'new'):
                for remaining in (60000, 3, 0.5):
                    board = [list(row) for row in initial.board]
                    player = IterativePlayer(color, evaluation_config=configs[version])
                    begin = monotonic()
                    move = player.take_turn(board, remaining)
                    elapsed = (monotonic() - begin) * 1000
                    initial.play(move)
                    if board != [list(row) for row in initial.board]:
                        raise AssertionError('Public probe mutated input.')
                    probes.append({'fixture': name, 'color': color, 'version': version,
                                   'remaining_ms': remaining, 'public_elapsed_ms': elapsed,
                                   'exceeds_incoming_clock': elapsed > remaining,
                                   'diagnostics': player.diagnostics()})
    report['public_timing'] = probes
    write(output / 'development.json', report)


def one_game(version: str, opponent_name: str, color: int, seed: int,
             cap: int, budget: int, initial: Position) -> dict[str, Any]:
    config = configurations()[version]
    # Exactly the ordinary Phase 2 settings; instrumentation off in clock games.
    settings = search_settings(depth=8, nodes=10000, radius=2, cap=24, policy=TimePolicy())
    supplied = load_players()
    agent = supplied.create('search', color, max_depth=8, max_nodes=10000,
                            search=configured_search(None if version == 'old' else config, settings))
    random.seed(seed)
    opponent = (PhaseTwoPlayer(1 - color) if opponent_name == 'phase2' else
                supplied.create(opponent_name, 1 - color))
    players = [agent, opponent] if color == 0 else [opponent, agent]
    metadata = {'route': 'equal-real-clock', 'version': version, 'agent_color': color,
                'evaluation': evaluation_identity(config), 'seed': seed,
                'opponent': opponent_name, 'phase2_checkpoint': CHECKPOINT,
                'provided_source_sha256': {p.name: sha256(p.read_bytes()).hexdigest()
                                          for p in sorted(SOURCES.glob('*.py'))},
                'conditions': conditions(), 'engine_source_sha256': engine_sources(),
                'search_settings': settings, 'profile_every': 0,
                'coupling': 'phase2 opponent process startup/JSON IPC charged to its public clock; '
                            'current agent in-process; diagnostics outside charged turn'}
    try:
        trace = run_game(*players, initial=initial, budgets_ms=(budget, budget), move_cap=cap,
                         config=metadata, diagnostics=lambda p: p.diagnostics()
                         if hasattr(p, 'diagnostics') else None)
        replay(json.loads(json.dumps(trace)))
        return trace
    finally:
        if isinstance(opponent, PhaseTwoPlayer):
            opponent.close()


def game_summary(trace: dict[str, Any], color: int) -> dict[str, Any]:
    reports = [event['search'] for event in trace['events']
               if event['type'] == 'returned' and event['color'] == color and event.get('search')]
    return {key: trace[key] for key in ('status', 'reason', 'winner', 'failure', 'remaining_ms')} | {
        'moves': len(trace['moves']), 'replay': 'valid',
        'move_sequence_id': sha256(json.dumps([m['move'] for m in trace['moves']]).encode()).hexdigest(),
        'completed_depths': dict(Counter(r['completed_depth'] for r in reports)),
        'fallback_turns': sum(r['completed_depth'] == 0 for r in reports),
        'agent_turns': len(reports), 'evaluation_calls': sum(r.get('evaluation_calls', 0) for r in reports),
        'public_elapsed_ms': distribution([r['elapsed_ms'] for r in reports]) if reports else None}


def batch_identity() -> dict[str, Any]:
    return {'evaluators': {name: evaluation_identity(config)
                           for name, config in configurations().items()},
            'provided_sources': {p.name: sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(SOURCES.glob('*.py'))},
            'phase2_checkpoint': CHECKPOINT,
            'search_settings': search_settings(depth=8, nodes=10000, radius=2, cap=24,
                                              policy=TimePolicy()),
            'offline_sources': {p.name: sha256(p.read_bytes()).hexdigest()
                                for p in sorted((ROOT / 'offline').glob('*.py'))}}


def games(output: Path, batch: str) -> None:
    # Per-game subprocess provides a hard resource bound and isolates random/global state.
    plan = ([(v, o, c, s, 400, 60000, 'empty')
             for v in ('old', 'new') for o in ('phase2', 'random', 'simple')
             for c in (0, 1) for s in range(20261009, 20261013)] if batch == 'integration' else
            [(v, 'phase2', c, 20261009, 24, 60000, start)
             for v in configurations() for c in (0, 1)
             for start in ('empty', 'capture-defense')])
    path = output / (batch + '.json')
    report: dict[str, Any] = json.loads(path.read_text()) if path.exists() else {
        'batch': batch, 'batch_identity': batch_identity(),
        'conditions': conditions(), 'engine_source_sha256': engine_sources(),
        'planned_games': len(plan), 'external_timeout_seconds': 150, 'games': []}
    # Do not silently reuse evidence across source/config changes.
    if report['engine_source_sha256'] != engine_sources():
        raise ValueError('Sources changed; use a new output directory.')
    if report.get('batch_identity') != batch_identity():
        raise ValueError('Batch identity changed; use a new output directory.')
    report['planned_games'] = len(plan)
    done = {tuple(r['key']) for r in report['games']}
    for item in plan:
        if item in done:
            continue
        version, opponent, color, seed, cap, budget, start = item
        target = output / f'{batch}-{version}-{opponent}-{color}-{seed}-{start}.json.gz'
        command = [sys.executable, '-m', 'verification.evaluation_acceptance', 'game',
                   '--version', version, '--opponent', opponent, '--color', str(color),
                   '--seed', str(seed), '--cap', str(cap), '--budget', str(budget),
                   '--start', start, '--trace', str(target)]
        record: dict[str, Any] = {'key': item, 'command': command}
        begin = monotonic()
        try:
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=150)
            if process.returncode:
                record.update(status='failed', failure='process_exit', stderr=process.stderr)
            else:
                with gzip.open(target, 'rt') as stream:
                    trace = json.load(stream)
                replay(trace)
                record.update(game_summary(trace, color), trace=str(target),
                              trace_sha256=sha256(target.read_bytes()).hexdigest())
        except subprocess.TimeoutExpired:
            record.update(status='failed', failure='external_timeout; offending player unknown')
        record['wall_seconds'] = monotonic() - begin
        report['games'].append(record)
        write(path, report)
        print(json.dumps(record), flush=True)


def summarize(output: Path) -> None:
    summary: dict[str, Any] = {'groups': [], 'replayed_traces': 0,
        'duplicates': 'identical moves under deterministic settings are repeated evidence; '
                      'clock stopping can vary even with the same seed',
        'default': 'retained Phase 2 material; effects-v1 remains experimental'}
    for batch in ('integration', 'ablations'):
        report = json.loads((output / (batch + '.json')).read_text())
        if report.get('batch_identity') != batch_identity():
            raise ValueError('Batch identity changed; do not combine incompatible evidence.')
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for game in report['games']:
            version, opponent, color, seed, cap, budget, start = game['key']
            groups.setdefault((version, opponent, start), []).append(game)
            if 'trace' in game:
                path = Path(game['trace'])
                # Recorded paths can come from another checkout.
                if not path.exists():
                    path = output / path.name
                if sha256(path.read_bytes()).hexdigest() != game['trace_sha256']:
                    raise ValueError('Trace hash changed: ' + str(path))
                with gzip.open(path, 'rt') as stream:
                    replay(json.load(stream))
                summary['replayed_traces'] += 1
        for (version, opponent, start), records in groups.items():
            def outcome(record: dict[str, Any]) -> str:
                if record['status'] != 'completed':
                    return record['status']
                if record['winner'] is None:
                    return 'draw'
                return 'win' if record['winner'] == record['key'][2] else 'loss'
            counts = dict(Counter(outcome(r) for r in records))
            summary['groups'].append({'batch': batch, 'version': version, 'opponent': opponent,
                'start': start, 'outcomes': counts,
                'by_color': {str(c): dict(Counter(outcome(r) for r in records if r['key'][2] == c))
                             for c in (0, 1)},
                'unique_move_sequences': len({r['move_sequence_id'] for r in records
                                              if 'move_sequence_id' in r}),
                'reliability_failures': [r['failure'] for r in records if r.get('failure')],
                'match_reliability_passed': not any(r.get('failure') for r in records),
                'failure_consequence': 'a crash in any provided-opponent game fails that opponent match',
                'fallback_turns': sum(r.get('fallback_turns', 0) for r in records),
                'agent_turns': sum(r.get('agent_turns', 0) for r in records)})
    write(output / 'summary.json', summary)
    print(json.dumps(summary), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('gate', 'development', 'integration', 'ablations', 'game', 'summary'))
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/verification/issue-22')
    parser.add_argument('--version', choices=tuple(configurations()), default='new')
    parser.add_argument('--opponent', choices=('phase2', 'random', 'simple'), default='phase2')
    parser.add_argument('--color', type=int, choices=(0, 1), default=0)
    parser.add_argument('--seed', type=int, default=20261009)
    parser.add_argument('--cap', type=int, default=400)
    parser.add_argument('--budget', type=int, default=60000)
    parser.add_argument('--start', choices=('empty', 'capture-defense'), default='empty')
    parser.add_argument('--trace', type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == 'gate':
        gate(args.output_dir)
    elif args.mode == 'summary':
        summarize(args.output_dir)
    elif args.mode == 'game':
        if args.trace is None:
            parser.error('--trace required for game')
        initial = diagnostic_starts()[args.start]
        initial = Position(initial.board, args.color) if args.start != 'empty' else initial
        trace = one_game(args.version, args.opponent, args.color, args.seed, args.cap, args.budget, initial)
        with gzip.open(args.trace, 'wt') as stream:
            json.dump(trace, stream, separators=(',', ':'), allow_nan=False)
    else:
        passed = json.loads((args.output_dir / 'gate.json').read_text())
        if passed['returncode'] or passed['engine_source_sha256'] != engine_sources():
            raise ValueError('Run regression gate with current sources first.')
        if args.mode == 'development':
            development(args.output_dir)
        else:
            games(args.output_dir, args.mode)


if __name__ == '__main__':
    main()
