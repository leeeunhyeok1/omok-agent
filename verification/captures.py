# AI-written by OpenAI Codex, for issue #19.
"""Reproducible capture inspection, independent oracle, and family cost samples."""
import argparse
from dataclasses import replace
import json
from random import Random
from statistics import median
from time import perf_counter

from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
from omok.simulator import Position, SIZE
from verification.reference import ReferencePosition


def suite() -> dict[str, Position]:
    positions = {'empty': Position.empty()}
    fixtures = {
        'single': ([(9, 12)], [(9, 10), (9, 11)]),
        'multiple': ([(9, 12), (12, 9)], [(9, 10), (9, 11), (10, 9), (11, 9)]),
        'edge': ([(0, 3)], [(0, 1), (0, 2)]),
        'capture_defense': ([(10, 7)], [(9, c) for c in range(6, 10)] + [(8, 7)]),
        'opponent_win': ([(11, 10)], [(9, c) for c in range(5, 11)] + [(10, 10)]),
        'simultaneous_draw': ([(11, 10)] + [(8, c) for c in range(6, 10)],
                              [(9, c) for c in range(5, 11)] + [(10, 10)]),
        'strict_capture_win': ([(11, 10)] + [(8, c) for c in range(6, 10)],
                               [(9, 10), (10, 10)]),
    }
    for name, (black, white) in fixtures.items():
        board = [[-1] * SIZE for _ in range(SIZE)]
        for color, cells in enumerate((black, white)):
            for r, c in cells:
                board[r][c] = color
        positions[name] = Position(board, 0)
    rng = Random(20261030)
    positions['dense'] = Position([[rng.choice((-1, -1, 0, 0, 1, 1))
                                   for _ in range(SIZE)] for _ in range(SIZE)], 0)
    return positions


def verify(position: Position, report: dict) -> int:
    """Enumerate every legal move with the independent window-based rules oracle."""
    checked = 0
    for color, name in enumerate(('black', 'white')):
        oracle = ReferencePosition(position.board, color)
        expected = {}
        if oracle.outcome == 'ongoing':
            for r in range(SIZE):
                for c in range(SIZE):
                    if oracle.board[r][c] != -1:
                        continue
                    transition = oracle.play((r, c))
                    checked += 1
                    if transition.captured:
                        expected[r, c] = transition
        actual = {move['move']: move for move in report['captures'][name]['moves']}
        assert set(actual) == set(expected), (name, 'missing/extra capture moves')
        for cell, transition in expected.items():
            move = actual[cell]
            assert move['cells'] == [item.cell for item in transition.captured]
            assert move['outcome'] == transition.position.outcome
            outcome = transition.position.outcome
            classification = ('continuation' if outcome == 'ongoing' else 'draw' if outcome == 'draw'
                              else 'win' if outcome == ('black_win' if color == 0 else 'white_win')
                              else 'opponent_win')
            assert move['classification'] == classification
            assert move['cell_count'] == len(transition.captured)
            assert move['pair_count'] * 2 == len(transition.captured)
    return checked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=5)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error('repetitions must be positive')
    config = EvaluationConfig.load('configs/capture-v1.json')
    evaluator = ConfiguredEvaluator(config)
    disabled = ConfiguredEvaluator(replace(config, captures_enabled=False))
    reports = {}
    for name, position in suite().items():
        inspection = evaluator.inspect(position)
        checked = verify(position, inspection)
        times = {}
        for label, callback in (('enabled', evaluator), ('disabled', disabled)):
            samples = []
            for _ in range(args.repetitions):
                start = perf_counter()
                callback(position)
                samples.append((perf_counter() - start) * 1000)
            times[label] = {'median_ms': median(samples), 'max_ms': max(samples)}
        reports[name] = {'board': position.board, 'side_to_move': position.side_to_move,
                         'inspection': inspection, 'disabled_total': disabled(position),
                         'oracle_legal_moves_checked': checked, 'evaluation_time': times}
    print(json.dumps({'configuration': json.loads(config.canonical_json()),
                      'dense_seed': 20261030, 'repetitions': args.repetitions,
                      'interpretation': 'Static features and provisional weights; no strength promotion.',
                      'positions': reports}, indent=2))


if __name__ == '__main__':
    main()
