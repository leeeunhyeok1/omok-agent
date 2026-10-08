# AI-written by OpenAI Codex, for issue #14.
"""Bounded both-color games and independent replay of recorded committed PVs."""
import argparse
import json
import platform
import random
from pathlib import Path

from offline.__main__ import search_diagnostics
from offline.provided import load_players
from offline.replay import replay
from offline.runner import run_game
from omok.player import IterativePlayer, LegalBaseline
from verification.reference import ReferencePosition


def check_lines(trace: dict) -> int:
    root = ReferencePosition(trace['initial']['board'], trace['initial']['side_to_move'])
    count = 0
    for event in trace['events']:
        if event['type'] == 'returned' and 'search' in event:
            report = event['search']
            if report['pv_status'] == 'complete' and report['completed_depth']:
                assert report['principal_variation'][0] == event['move']
                leaf = root
                for move in report['principal_variation']:
                    leaf = leaf.play(move).position
                assert len(report['principal_variation']) == report['completed_depth'] or leaf.outcome != 'ongoing'
                count += 1
        elif event['type'] == 'applied':
            root = root.play(event['move']).position
            assert [list(row) for row in root.board] == event['state']['board']
            assert root.outcome == event['state']['outcome']
    assert [list(row) for row in root.board] == trace['final']['board']
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('.scratch/issue-14'))
    parser.add_argument('--move-cap', type=int, default=12)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    supplied = load_players()
    games = []
    for opponent in ('baseline', 'random', 'simple'):
        for color in (0, 1):
            seed = 20261009 + color
            random.seed(seed)
            if opponent == 'baseline':
                agent, rival = IterativePlayer(color), LegalBaseline(1 - color)
            else:
                agent, rival = supplied.create('search', color), supplied.create(opponent, 1 - color)
            players = (agent, rival) if color == 0 else (rival, agent)
            trace = run_game(*players, move_cap=args.move_cap, diagnostics=search_diagnostics,
                             config={'seed': seed, 'engine': 'iterative-negamax-v1', 'workers': 1})
            replay(trace)
            lines = check_lines(trace)
            assert trace['failure'] is None, trace['failure']
            for side in (0, 1):
                clocks = [60000.0] + [m['remaining_ms'] for m in trace['moves'] if m['color'] == side]
                assert all(a > b for a, b in zip(clocks, clocks[1:]))
            path = args.output_dir / f'{opponent}-{color}.json'
            path.write_text(json.dumps(trace, indent=2, allow_nan=False) + '\n')
            reports = [e['search'] for e in trace['events'] if 'search' in e]
            games.append({'opponent': opponent, 'search_color': color, 'trace': str(path),
                          'status': trace['status'], 'reason': trace['reason'],
                          'moves': len(trace['moves']), 'failure': trace['failure'],
                          'remaining_ms': trace['remaining_ms'], 'verified_complete_pvs': lines,
                          'completed_depths': [r['completed_depth'] for r in reports],
                          'max_public_elapsed_ms': max((r['elapsed_ms'] for r in reports), default=0),
                          'max_table_size': max((r['table_size'] for r in reports), default=0)})
    print(json.dumps({'python': platform.python_version(), 'platform': platform.platform(),
                      'workers': 1, 'budgets_ms': [60000, 60000], 'move_cap': args.move_cap,
                      'games': games}, indent=2))


if __name__ == '__main__':
    main()
