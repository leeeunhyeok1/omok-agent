# AI-written by OpenAI Codex, for issue #21.
"""Reproduce bounded material diagnostics, replay and evaluator comparison evidence."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from offline.compare import compare
from offline.measurement import configured_search, conditions, engine_sources, evaluation_identity, search_settings
from offline.replay import replay
from offline.runner import player_source, run_game
from omok.evaluation import EvaluationConfig
from omok.player import IterativePlayer, TimePolicy
from omok.simulator import Position


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.scratch/issue-21-measurement.json'))
    args = parser.parse_args()
    material = EvaluationConfig.load('configs/material-v1.json')
    effects = EvaluationConfig.load('configs/effects-v1.json')
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'reload.json'
        material.save(path)
        reloaded = EvaluationConfig.load(path)
    if material.identity != reloaded.identity:
        raise AssertionError('Saved configuration changed identity.')
    policy = TimePolicy()
    settings = search_settings(depth=2, nodes=40, radius=2, cap=3, policy=policy)
    report: dict[str, Any] = {'conditions': conditions(), 'engine_source_sha256': engine_sources(),
                              'settings': settings, 'reload_identity': reloaded.identity,
                              'comparisons': [], 'games': []}
    for color in (0, 1):
        board = [list(row) for row in Position.empty().board]
        board[9][6:10] = [1 - color] * 4
        board[8][7], board[10][7] = 1 - color, color
        fixtures = [('empty', Position(Position.empty().board, color)),
                    ('capture-defense', Position(board, color))]
        for name, initial in fixtures:
            for route in ('fixed-depth', 'node-budget'):
                comparison = compare([material, effects], initial, route=route,
                                     depth=2, cap=3, radius=2, nodes=40, profile_every=2)
                comparison['fixture'] = name
                report['comparisons'].append(comparison)
        agent = IterativePlayer(color, max_depth=settings['max_depth'], max_nodes=settings['max_nodes'],
                                policy=policy, search=configured_search(reloaded, settings, profile_every=2))
        opponent = IterativePlayer(1 - color, max_depth=settings['max_depth'], max_nodes=settings['max_nodes'],
                                   policy=policy, search=configured_search(None, settings))
        players = [agent, opponent] if color == 0 else [opponent, agent]
        trace = run_game(*players, move_cap=6, budgets_ms=(60000, 60000),
                         config={'route': 'real-clock-game', 'agent_color': color,
                                 'seed': 20261009, 'opening': 'empty', 'settings': settings,
                                 'evaluation': evaluation_identity(reloaded),
                                 'opponent_version': 'retained-phase-2-material',
                                 'opponent_source': player_source(opponent),
                                 'engine_source_sha256': engine_sources(), 'conditions': conditions()},
                         diagnostics=lambda player: player.diagnostics() if isinstance(player, IterativePlayer) else None)
        replay(json.loads(json.dumps(trace)))
        if trace['failure'] is not None:
            raise AssertionError('Bounded game failed: ' + repr(trace['failure']))
        calls = [event['search']['remaining_ms'] for event in trace['events']
                 if event['type'] == 'returned' and event['color'] == color]
        if len(calls) < 2 or not all(a > b for a, b in zip(calls, calls[1:])):
            raise AssertionError('Cumulative clock did not decrease.')
        report['games'].append({'replay': 'valid', 'trace': trace})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'comparisons': len(report['comparisons']), 'games': len(report['games']),
                      'replays': 'valid', 'configuration_reload': 'identical', 'output': str(args.output)}))


if __name__ == '__main__':
    main()
