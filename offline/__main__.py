# AI-written by OpenAI Codex, for issues #4 and #6.
"""Run one local game or replay its trace; see docs/runner.md."""
import argparse
import json
import platform
import random
from hashlib import sha256
from pathlib import Path
from typing import Any

from offline.fixtures import NAMES, fixture
from offline.opponents import SeededSmokePlayer
from offline.replay import load_trace, replay
from offline.runner import player_source, run_game
from omok.player import DevelopmentPlayer, IterativePlayer, LegalBaseline
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
    parser.add_argument('--seed', type=int, default=20261008)
    parser.add_argument('--opponent', choices=('smoke', 'baseline', 'random', 'simple'), default='smoke')
    parser.add_argument('--black-ms', type=budget, default=60000)
    parser.add_argument('--white-ms', type=budget, default=60000)
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
        color = 0 if args.agent_color == 'black' else 1
        sources = {}
        agent: DevelopmentPlayer = IterativePlayer(color) if args.engine == 'search' else LegalBaseline(color)
        if args.opponent in ('smoke', 'baseline'):
            opponent: DevelopmentPlayer = (SeededSmokePlayer(1 - color, args.seed)
                                           if args.opponent == 'smoke' else LegalBaseline(1 - color))
            players: list[DevelopmentPlayer] = [agent, opponent]
        else:
            from offline.provided import SOURCES, load_players
            supplied = load_players()
            random.seed(args.seed)
            players = [supplied.create(args.engine, color),
                       supplied.create(args.opponent, 1 - color)]
            sources = {name: sha256((SOURCES / name).read_bytes()).hexdigest()
                       for name in ('player.py', 'randomplayer.py', 'simpleplayer.py')}
        if color == 1:
            players.reverse()
        config: dict[str, Any] = {
            'engine': args.engine, 'agent_color': color,
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
        trace = run_game(players[0], players[1], initial=initial,
                         budgets_ms=(args.black_ms, args.white_ms), move_cap=args.move_cap, config=config,
                         diagnostics=search_diagnostics if args.diagnostics else None)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(trace, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(json.dumps({key: trace[key] for key in
                          ('status', 'reason', 'winner', 'remaining_ms', 'failure')} | {'moves': len(trace['moves'])}))
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
