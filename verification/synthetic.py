# AI-written by OpenAI Codex, for issue #30.
"""Reproducible controlled positions and color-balanced bounded development games."""
import argparse
import gzip
import json
from pathlib import Path
from typing import Any

from offline.experiments import ExperimentPlan, execute_job
from offline.registry import default_catalog, run_registered_game
from offline.replay import replay
from omok.simulator import Position


def save(path: Path, value: Any) -> None:
    with gzip.open(path, 'wt', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.scratch/synthetic-v1'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    catalog, snapshot = default_catalog()
    save(args.output / 'registry.json.gz', {'format': 'omok-registry-v1',
        'entries': [e.record() for e in catalog.values()], 'pool_snapshot': snapshot.record()})
    cluster = [(3, c, 0) for c in range(3, 6)] + [(r, c, 0) for r, c in
               ((10, 10), (10, 12), (12, 10), (12, 12))]
    danger = [(5, c, 1) for c in range(5, 9)] + [(5, 4, 0)] + [(12, c, 0) for c in range(10, 13)]
    crossing = ([(3, c, 0) for c in range(3, 6)]
                + [(9, c, 0) for c in (7, 10, 11)] + [(r, 9, 0) for r in (7, 10, 11)])
    fixtures = [
        ('local', cluster, {(11, 11)}), ('aggressive', cluster, {(3, 6)}),
        ('defensive', danger, {(5, 9)}), ('search1', danger, {(12, 9), (12, 13)}),
        ('search2', danger, {(5, 9)}),
        ('capture', [(5, 6, 1), (5, 7, 1), (5, 8, 0)] + [(12, c, 0) for c in range(10, 13)], {(5, 5)}),
        ('pattern', [(3, c, 0) for c in (3, 4, 6, 7)], {(3, 5)}),
        ('pattern', crossing, {(9, 9)}), ('aggressive', crossing, {(3, 6)}),
        ('random', [(9, 9, 1)], {(r, c) for r in range(8, 11) for c in range(8, 11) if (r, c) != (9, 9)}),
    ]
    checked = []
    for index, (strategy, stones, expected) in enumerate(fixtures):
        board = [[-1] * 19 for _ in range(19)]
        for r, c, color in stones:
            board[r][c] = color
        trace = run_registered_game(catalog['synthetic-' + strategy], snapshot, 'smoke',
            initial=Position(board, 0), seed=20261010, move_cap=1)
        replay(trace)
        if trace['failure'] or tuple(trace['moves'][0]['move']) not in expected:
            raise AssertionError('Controlled behavior failed: ' + strategy)
        save(args.output / f'{strategy}-fixture-{index:02d}.json.gz', trace)
        checked.append({'strategy': strategy, 'move': trace['moves'][0]['move'],
                        'captures': len(trace['moves'][0]['captured'])})
        print('Checked ' + strategy, flush=True)
    opponents = [e.data['logical_id'] for _, e in snapshot.select()
                 if e.data['logical_id'].startswith('synthetic-')]
    plan = ExperimentPlan.resolve(catalog['phase2'], snapshot, opponents=opponents,
        mode='screening', seed=20261010, games_per_opponent=2, total_ms=5000, move_cap=12)
    save(args.output / 'plan.json.gz', plan.record())
    games = []
    for index, job in enumerate(plan.data['jobs']):
        result = execute_job(plan, job)
        trace = result['trace']
        replay(trace)
        if trace['failure'] or trace['status'] not in ('completed', 'capped'):
            raise AssertionError('Bounded game failed: ' + job['opponent']['logical_id'])
        filename = f'game-{index:02d}.json.gz'
        save(args.output / filename, result)
        games.append({'opponent': job['opponent']['logical_id'], 'candidate_color': job['candidate_color'],
            'status': trace['status'], 'moves': len(trace['moves']), 'artifact': filename})
        print('Played ' + filename, flush=True)
    summary = {'format': 'omok-synthetic-evidence-v1', 'conditions': plan.data['conditions'],
        'candidate': catalog['phase2'].identity, 'pool_snapshot': snapshot.identity,
        'fixtures': checked, 'games': games, 'holdout_exposures': [],
        'limitations': 'Short capped screening proves runnable contrasting behavior, not strength or independent trials.'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
