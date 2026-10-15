# AI-written by OpenAI Codex.
"""Serial replay benchmark of saved Colab loss positions and optional games.

Run as a script with --source-root to compare a pristine source snapshot. Timing
is descriptive; exact scores/features and node-limited results are comparable.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import random
from statistics import median
import sys
from time import perf_counter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--games', type=int, default=0,
                        help='Games per opponent, alternating colors; zero skips games')
    args = parser.parse_args()
    if args.games < 0 or args.games % 2:
        parser.error('--games must be an even nonnegative count')
    source = args.source_root.resolve()
    sys.path.insert(0, str(source))
    from offline.worker_players import create
    from offline.provided import load_players
    from offline.runner import run_game
    from offline.replay import replay
    from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
    from omok.search import SearchLimits
    from omok.simulator import Position

    args.output.mkdir(parents=True, exist_ok=True)
    fixture = Path(__file__).parent / 'fixtures/colab-search-positions.json'
    records = json.loads(fixture.read_text())
    report = {'runtime': sys.version, 'platform': platform.platform(),
              'source_root': str(source), 'workers': 1,
              'conditions': 'serial local development; external load/power uncontrolled',
              'sources': {str(p.relative_to(source)): sha256(p.read_bytes()).hexdigest()
                          for p in sorted((source / 'omok').glob('*.py'))},
              'fixture_sha256': sha256(fixture.read_bytes()).hexdigest(),
              'positions': [], 'games': []}
    for i, record in enumerate(records):
        p, config = record['position'], record['configuration']
        position = Position(p['board'], p['side_to_move'])
        evaluation = json.dumps(config['evaluation'])

        def player():
            return create(position.side_to_move, name='search',
                          settings=config['settings'], evaluation=evaluation)

        timings = []
        for _ in range(3):
            engine = player().search
            start = perf_counter()
            result = engine.iterative(position, 1, limits=SearchLimits(max_nodes=10000))
            timings.append((perf_counter() - start) * 1000)
        fixed = {'move': result.move, 'score': result.score, 'nodes': result.nodes,
                 'completed_depth': result.completed_depth,
                 'median_ms': median(timings)}
        evaluator = ConfiguredEvaluator(EvaluationConfig.from_json(evaluation))
        features = evaluator.inspect(position)
        public = player()
        public.take_turn(position.board, 10000)
        diagnostics = public.diagnostics()
        item = {'index': i, 'source': record['source'], 'fixed_depth_one': fixed,
                'features': features,
                'clock_250ms': {key: diagnostics[key] for key in
                    ('move', 'score', 'completed_depth', 'nodes', 'evaluation_completed',
                     'elapsed_ms', 'fallback_reason')}}
        report['positions'].append(item)
        print(json.dumps({'position': i, 'depth_one_ms': fixed['median_ms'],
                          'clock_depth': diagnostics['completed_depth']}), flush=True)
    config = records[0]['configuration']
    for opponent in ('simple', 'random'):
        for game in range(args.games):
            color = game % 2
            random.seed(20261015 + game)
            candidate = create(color, name='search', settings=config['settings'],
                               evaluation=json.dumps(config['evaluation']))
            rival = load_players().create(opponent, 1 - color)
            players = (candidate, rival) if color == 0 else (rival, candidate)
            trace = run_game(*players, move_cap=1000,
                             diagnostics=lambda p: p.diagnostics() if p is candidate else None,
                             config={'settings': config, 'seed': 20261015 + game,
                                     'conditions': report['conditions']})
            replay(trace)
            path = args.output / f'{opponent}-{game}.json'
            path.write_text(json.dumps(trace) + '\n')
            item = {'opponent': opponent, 'color': color, 'status': trace['status'],
                    'winner': trace['winner'], 'reason': trace['reason'],
                    'remaining_ms': trace['remaining_ms'], 'trace': path.name}
            report['games'].append(item)
            print(json.dumps(item), flush=True)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
