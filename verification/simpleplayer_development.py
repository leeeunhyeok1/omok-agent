# AI-written by OpenAI Codex.
"""Run one frozen, serial SimplePlayer development schedule against a source tree.

This deliberately has no default game schedule. Write the resolved configuration,
openings, colors, and clocks to --plan before running either source revision.
These local games are development evidence, not independent qualification.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan_bytes = args.plan.read_bytes()
    plan = json.loads(plan_bytes)
    if args.output.exists():
        parser.error('Output already exists; preserve earlier evidence and choose another path.')
    source = args.source_root.resolve()
    sys.path.insert(0, str(source))
    from offline.provided import load_players
    from offline.replay import replay
    from offline.runner import run_game
    from offline.worker_players import create
    from omok.simulator import Position

    args.output.mkdir(parents=True)
    (args.output / 'plan.json').write_bytes(plan_bytes)
    report = {
        'plan_sha256': sha256(plan_bytes).hexdigest(), 'runtime': sys.version,
        'platform': platform.platform(), 'source_root': str(source), 'workers': 1,
        'conditions': 'serial local development; external load and power uncontrolled',
        'sources': {str(p.relative_to(source)): sha256(p.read_bytes()).hexdigest()
                    for directory in ('omok', 'offline', 'players')
                    for p in sorted((source / directory).glob('*.py'))},
        'scope': 'SimplePlayer development games; not holdout or qualification',
        'games': [],
    }
    config = plan['configuration']
    for index, job in enumerate(plan['jobs']):
        position = Position.empty()
        for move in job['opening']:
            position = position.play(move).position
        color = job['candidate_color']
        candidate = create(color, name='search', settings=config['settings'],
                           evaluation=json.dumps(config['evaluation']))
        opponent = load_players().create('simple', 1 - color)
        players = (candidate, opponent) if color == 0 else (opponent, candidate)
        trace = run_game(*players, initial=position,
                         budgets_ms=(plan['total_ms'], plan['total_ms']),
                         move_cap=plan['move_cap'], config={'plan': report['plan_sha256'],
                                                          'job': index},
                         diagnostics=lambda p: p.diagnostics() if p is candidate else None)
        replay(trace)
        name = f'game-{index}.json'
        (args.output / name).write_text(json.dumps(trace) + '\n')
        diagnostics = [e['search'] for e in trace['events']
                       if e['type'] == 'returned' and 'search' in e]
        result = {
            'job': index, 'candidate_color': color, 'opening': job['opening'],
            'status': trace['status'], 'reason': trace['reason'],
            'winner': trace['winner'], 'candidate_win': trace['winner'] == color,
            'remaining_ms': trace['remaining_ms'], 'plies': len(trace['moves']),
            'search_turns': len(diagnostics),
            'completed_depth_sum': sum(d['completed_depth'] for d in diagnostics),
            'depth_zero_turns': sum(d['completed_depth'] == 0 for d in diagnostics),
            'trace': name,
        }
        report['games'].append(result)
        (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
