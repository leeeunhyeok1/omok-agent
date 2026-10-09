# AI-written by OpenAI Codex, for issues #4 and #6; issue #21 measurement additions.
"""Run one local game or replay its trace; see docs/runner.md."""
import argparse
import json
import platform
from hashlib import sha256
from pathlib import Path
from typing import Any

from offline.fixtures import NAMES, fixture
from offline.replay import load_trace, replay
from offline.runner import player_source
from offline.supervised import PlayerSpec, Supervision, run_supervised_game
from omok.player import DevelopmentPlayer, IterativePlayer, LegalBaseline, TimePolicy
from omok.evaluation import EvaluationConfig
from offline.measurement import conditions, engine_sources, evaluation_identity, search_settings
from omok.simulator import Position


def budget(value: str) -> float | None:
    milliseconds = float(value)
    return None if milliseconds == -1 else milliseconds


# AI-written by OpenAI Codex, for issue #14.
def search_diagnostics(player: DevelopmentPlayer) -> dict[str, Any] | None:
    return player.diagnostics() if isinstance(player, IterativePlayer) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-color', '--baseline-color', dest='agent_color', choices=('black', 'white'), default='black')
    parser.add_argument('--engine', choices=('baseline', 'search'), default='baseline')
    parser.add_argument('--diagnostics', action='store_true', help='Record bounded search snapshots')
    parser.add_argument('--evaluation-config', type=Path, help='Saved evaluator JSON (search only)')
    parser.add_argument('--profile-every', type=int, default=0, help='Sample every Nth evaluator call; 0 disables')
    parser.add_argument('--max-depth', type=int, default=8)
    parser.add_argument('--max-nodes', type=int, default=10000)
    parser.add_argument('--candidate-radius', type=int, default=2)
    parser.add_argument('--candidate-cap', type=int, default=24)
    parser.add_argument('--max-time-ms', type=float, default=100)
    parser.add_argument('--seed', type=int, default=20261008)
    parser.add_argument('--opponent', choices=('smoke', 'baseline', 'random', 'simple'), default='smoke')
    parser.add_argument('--black-ms', type=budget, default=60000)
    parser.add_argument('--white-ms', type=budget, default=60000)
    parser.add_argument('--startup-ms', type=float, default=5000)
    parser.add_argument('--cleanup-ms', type=float, default=500)
    parser.add_argument('--unlimited-call-ms', type=float, default=1000)
    parser.add_argument('--output-bytes', type=int, default=16384)
    parser.add_argument('--move-cap', type=int, default=1000)
    starts = parser.add_mutually_exclusive_group()
    starts.add_argument('--fixture', choices=NAMES, default='empty')
    starts.add_argument('--start', type=Path, help='JSON containing board and side_to_move')
    parser.add_argument('--output', type=Path, help='Save complete JSON trace')
    parser.add_argument('--replay', type=Path, help='Validate a saved trace without players')
    args = parser.parse_args()
    try:
        if args.replay:
            position = replay(load_trace(args.replay))
            print(json.dumps({'replay': 'valid', 'outcome': position.outcome, 'reason': position.reason}))
            return
        initial = fixture(args.fixture)
        if args.start:
            data = json.loads(args.start.read_text())
            initial = Position(data['board'], data['side_to_move'])
        if args.engine != 'search' and (args.evaluation_config or args.profile_every):
            raise ValueError('Evaluator configuration and profiling require --engine search.')
        if args.profile_every and not args.diagnostics:
            raise ValueError('Profiling requires --diagnostics to retain measurements.')
        evaluation = EvaluationConfig.load(args.evaluation_config) if args.evaluation_config else None
        policy = TimePolicy(max_time_ms=args.max_time_ms)
        settings = search_settings(depth=args.max_depth, nodes=args.max_nodes,
                                   radius=args.candidate_radius, cap=args.candidate_cap, policy=policy)
        color = 0 if args.agent_color == 'black' else 1
        sources = {}
        supplied = args.opponent in ('random', 'simple')
        agent_options = {'name': args.engine, 'supplied': supplied, 'settings': settings,
                         'evaluation': evaluation.canonical_json() if evaluation else None,
                         'profile_every': args.profile_every}
        opponent_options = {'name': args.opponent, 'supplied': supplied, 'seed': args.seed}
        players = [PlayerSpec('offline.worker_players', 'create', agent_options, args.seed),
                   PlayerSpec('offline.worker_players', 'create', opponent_options, args.seed + 1)]
        if supplied:
            from offline.provided import SOURCES
            sources = {name: sha256((SOURCES / name).read_bytes()).hexdigest()
                       for name in ('player.py', 'randomplayer.py', 'simpleplayer.py')}
        if color == 1:
            players.reverse()
        config: dict[str, Any] = {
            'engine': args.engine, 'agent_color': color,
            'evaluator_mode': 'configured' if evaluation else 'retained-phase-2-material',
            'evaluation': evaluation_identity(evaluation or EvaluationConfig()) if args.engine == 'search' else None,
            'search_settings': settings if args.engine == 'search' else None,
            'profile_every': args.profile_every, 'conditions': conditions(),
            'engine_source_sha256': engine_sources(),
            'route': 'real-clock-game',
            'diagnostics': args.diagnostics,
            'engine_version': 'iterative-negamax-v1' if args.engine == 'search' else 'legal-baseline-v1',
            'baseline_version': 'legal-baseline-v1',
            'baseline_implementation': player_source(LegalBaseline(color)),
            'opponent_version': 'seeded-smoke-v1' if args.opponent == 'smoke' else args.opponent,
            'provided_source_sha256': sources,
            'seed': args.seed, 'baseline_color': color,
            'start': str(args.start) if args.start else args.fixture,
            'python': platform.python_version(), 'platform': platform.platform(),
            'machine': platform.machine(), 'workers': 1,
        }
        config['conditions']['execution'] = 'sequential game; two persistent player subprocesses'
        config['conditions']['player_processes'] = 2
        trace = run_supervised_game(players[0], players[1], initial=initial,
                         budgets_ms=(args.black_ms, args.white_ms), move_cap=args.move_cap, config=config,
                         diagnostics=args.diagnostics, supervision=Supervision(
                             startup_ms=args.startup_ms, cleanup_ms=args.cleanup_ms,
                             unlimited_call_ms=args.unlimited_call_ms, output_bytes=args.output_bytes))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(trace, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(json.dumps({key: trace[key] for key in
                          ('status', 'reason', 'winner', 'remaining_ms', 'failure')} | {'moves': len(trace['moves'])}))
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
