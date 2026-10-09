# AI-written by OpenAI Codex, for issue #21.
"""Bounded evaluator comparisons, with one recorded frozen tactical candidate tree."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from offline.fixtures import NAMES, fixture
from offline.measurement import conditions, engine_sources, evaluation_identity, search_settings
from offline.runner import state
from omok.evaluation import EvaluationConfig
from omok.player import TimePolicy
from omok.search import FixedDepthSearch, SearchLimits
from omok.simulator import Coordinate, Position
from omok.tactics import TacticalPolicy
from omok.transposition import TranspositionTable


def freeze_tree(initial: Position, depth: int, policy: TacticalPolicy
                ) -> dict[Position, tuple[Coordinate, ...]]:
    """Select once independently of evaluator weights; retain mandatory tactics."""
    tree: dict[Position, tuple[Coordinate, ...]] = {}
    visited: dict[Position, int] = {}
    def visit(position: Position, remaining: int) -> None:
        if remaining == 0 or position.outcome != 'ongoing' or visited.get(position, 0) >= remaining:
            return
        visited[position] = remaining
        if position not in tree:
            report = policy.analyze(position)
            if not report.complete:
                raise RuntimeError('Cannot freeze incomplete tactical candidates.')
            protected = {move: 2 for move in report.wins}
            protected.update({move: 1 for move in report.defenses if move not in protected})
            tree[position] = tuple(sorted(report.candidates, key=lambda move: (
                -protected.get(move, 0), -policy.ordinary_rank(position, move, lambda: None))))
        for move in tree[position]:
            visit(position.play(move).position, remaining - 1)
    visit(initial, depth)
    return tree


def compare(configs: list[EvaluationConfig], initial: Position, *, route: str,
            depth: int = 2, cap: int = 3, radius: int = 2, nodes: int = 100,
            profile_every: int = 1, seed: int = 20261009) -> dict[str, Any]:
    if route not in ('fixed-depth', 'node-budget'):
        raise ValueError('Unknown comparison route.')
    if not 1 <= depth <= 3 or not 1 <= cap <= 8 or not 1 <= radius <= 3:
        raise ValueError('Bounded comparison requires depth 1–3, cap 1–8, radius 1–3.')
    if type(profile_every) is not int or profile_every < 1:
        raise ValueError('Paired comparison requires a positive sampling interval.')
    if not configs or len(configs) > 8:
        raise ValueError('Supply between one and eight configurations.')
    limits = SearchLimits(max_nodes=nodes)  # Validates even for the fixed-depth route.
    tree = freeze_tree(initial, depth, TacticalPolicy(radius=radius, cap=cap))
    records = [{'position': state(position), 'moves': [list(move) for move in moves]}
               for position, moves in tree.items()]
    tree_json = json.dumps(records, sort_keys=True, separators=(',', ':'))
    settings = search_settings(depth=depth, nodes=nodes, radius=radius, cap=cap, policy=TimePolicy())
    report: dict[str, Any] = {
        'format': 'omok-evaluator-comparison-v1', 'route': route,
        'engine_version': 'iterative-negamax-v1', 'engine_source_sha256': engine_sources(),
        'conditions': conditions(), 'seed': seed, 'randomness': 'none; deterministic fixture',
        'initial': state(initial), 'search_settings': settings,
        'effective_search': {'reference': route == 'fixed-depth',
                             'clock': 'disabled', 'candidate_order': 'frozen',
                             'table': 'plain/sample disabled; separate cold/warm comparisons' if route == 'fixed-depth' else 'fresh per run',
                             'node_limit': nodes if route == 'node-budget' else None},
        'candidate_tree_id': sha256(tree_json.encode()).hexdigest(),
        'candidate_tree': records, 'runs': [],
    }
    for config in configs:
        pair: dict[str, Any] = {'evaluation': evaluation_identity(config)}
        for name, interval in (('plain', 0), ('sampled', profile_every)):
            engine = FixedDepthSearch(candidates=lambda position: tree[position],
                                      evaluation_config=config, profile_every=interval,
                                      table=None if route == 'fixed-depth' else TranspositionTable(
                                          settings['table_capacity']))
            start = perf_counter_ns()
            result = (engine.search(initial, depth, reference=True) if route == 'fixed-depth' else
                      engine.iterative(initial, depth, limits=limits))
            elapsed = perf_counter_ns() - start
            pair[name] = asdict(result) | {'elapsed_ns': elapsed}
        plain, sampled = pair['plain'], pair['sampled']
        for key in ('move', 'score', 'completed', 'completed_depth', 'nodes', 'cancellation'):
            if plain[key] != sampled[key]:
                raise AssertionError('Instrumentation changed deterministic search: ' + key)
        pair['paired_overhead'] = {
            'elapsed_delta_ns': sampled['elapsed_ns'] - plain['elapsed_ns'],
            'elapsed_ratio': sampled['elapsed_ns'] / plain['elapsed_ns'] if plain['elapsed_ns'] else None,
            'meaning': 'one sequential plain/sample pair; includes noise/order effects; not a calibrated estimate',
        }
        if route == 'fixed-depth':
            for name in ('alpha_beta', 'cached_cold', 'cached_warm'):
                if name != 'cached_warm':
                    engine = FixedDepthSearch(candidates=lambda position: tree[position],
                        evaluation_config=config,
                        table=None if name == 'alpha_beta' else TranspositionTable(
                            settings['table_capacity']))
                start = perf_counter_ns()
                result = engine.search(initial, depth)
                pair[name] = asdict(result) | {'elapsed_ns': perf_counter_ns() - start}
                if not result.completed or result.score != plain['score']:
                    raise AssertionError('Alpha-beta/reference disagreement: ' + name)
        report['runs'].append(pair)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configs', nargs='+', type=Path, required=True)
    parser.add_argument('--route', choices=('fixed-depth', 'node-budget'), default='fixed-depth')
    starts = parser.add_mutually_exclusive_group()
    starts.add_argument('--fixture', choices=NAMES, default='empty')
    starts.add_argument('--start', type=Path, help='JSON board and side_to_move; color override is explicit')
    parser.add_argument('--color', choices=('black', 'white'), default=None)
    parser.add_argument('--depth', type=int, default=2)
    parser.add_argument('--cap', type=int, default=3)
    parser.add_argument('--radius', type=int, default=2)
    parser.add_argument('--nodes', type=int, default=100)
    parser.add_argument('--profile-every', type=int, default=1)
    parser.add_argument('--seed', type=int, default=20261009)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        initial = fixture(args.fixture)
        if args.start:
            data = json.loads(args.start.read_text(encoding='utf-8'))
            initial = Position(data['board'], data['side_to_move'])
        if args.color is not None:
            initial = Position(initial.board, 0 if args.color == 'black' else 1)
        report = compare([EvaluationConfig.load(path) for path in args.configs], initial,
                         route=args.route, depth=args.depth, cap=args.cap, radius=args.radius,
                         nodes=args.nodes, profile_every=args.profile_every, seed=args.seed)
        report['fixture'] = str(args.start) if args.start else args.fixture
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(json.dumps({'route': args.route, 'runs': len(report['runs']),
                          'candidate_tree_id': report['candidate_tree_id']}))
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
