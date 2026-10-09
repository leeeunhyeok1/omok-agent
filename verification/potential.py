# AI-written by OpenAI Codex, for issue #18.
"""Reproducible quiet/edge/dense static inspection; no strength claim."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import platform
from random import Random
from statistics import median
from time import perf_counter

from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
from omok.simulator import Position, SIZE


def suite() -> dict[str, Position]:
    positions = {}
    fixtures = {
        'quiet_open_three': ((7, 8, 9), ()),
        'quiet_broken_three': ((7, 8, 10), ()),
        'quiet_two': ((7, 9), ()),
        'blocked_three': ((7, 8, 9), (6,)),
        'edge_three': ((0, 1, 2), ()),
        'overline_adjacent': ((5, 7, 8, 9), ()),
    }
    for name, (own, other) in fixtures.items():
        board = [[-1] * SIZE for _ in range(SIZE)]
        for color, cells in enumerate((own, other)):
            for col in cells:
                board[9][col] = color
        positions[name] = Position(board, 0)
    rng = Random(20261015)
    positions['dense'] = Position([[rng.choice((-1, -1, 0, 0, 1, 1))
                                   for c in range(SIZE)] for r in range(SIZE)], 0)
    return positions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/potential-v1.json'))
    parser.add_argument('--repetitions', type=int, default=10)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error('repetitions must be positive')
    config = EvaluationConfig.load(args.config)
    evaluator = ConfiguredEvaluator(config)
    disabled = ConfiguredEvaluator(replace(config, potential_enabled=False))
    reports = {}
    for name, position in suite().items():
        samples = []
        for _ in range(args.repetitions):
            start = perf_counter()
            evaluator(position)
            samples.append((perf_counter() - start) * 1000)
        reports[name] = {
            'board': position.board, 'side_to_move': position.side_to_move,
            'inspection': evaluator.inspect(position),
            'potential_disabled': disabled.inspect(position),
            'evaluation_ms': {'median': median(samples), 'max': max(samples)},
        }
    print(json.dumps({
        'runtime': platform.python_version(), 'machine': platform.machine(),
        'workers': 1, 'repetitions': args.repetitions, 'dense_seed': 20261015,
        'configuration': json.loads(config.canonical_json()),
        'interpretation': 'Static geometry and provisional weighted scores; no forced-win or strength claim.',
        'score_order_hypothesis': 'At equal material, this configuration prefers open to broken threes. '
                                  'This is a provisional preference, not an exact game rule.',
        'positions': reports,
    }, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
