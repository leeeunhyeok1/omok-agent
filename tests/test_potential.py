# AI-written by OpenAI Codex, for issue #18.
from pathlib import Path
import json
import unittest
from dataclasses import replace

from omok.player import IterativePlayer
from omok.search import FixedDepthSearch, SearchCancelled, SearchLimits
from omok.tactics import TacticalPolicy
from omok.transposition import TranspositionTable
from verification.reference import ReferencePosition

from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
from omok.simulator import Position
from tests.test_lines import board_with


class PotentialTests(unittest.TestCase):
    def test_contiguous_three_is_counted_once_across_development_windows(self):
        root = Position(board_with([(9, c) for c in (7, 8, 9)]), 0)
        evaluator = ConfiguredEvaluator(EvaluationConfig(feature_version='potential-v1'))
        report = evaluator.inspect(root)
        self.assertEqual(report['potential']['black']['open_three'], 1)
        self.assertEqual(report['potential']['black']['broken_three'], 0)
        self.assertEqual(report['potential']['black']['two_stone'], 0)
        self.assertEqual(report['contributions']['open_three'], 40)
        self.assertEqual(report['total'], 43)

    def test_literal_geometry_both_colors_and_all_symmetries(self):
        # Expected counts are literal worked examples, independent of scan helpers.
        fixtures = [
            ((7, 8, 9), (), (1, 0, 0)),
            ((7, 8, 10), (), (0, 1, 0)),
            ((7, 9, 10), (), (0, 1, 0)),
            ((7, 9, 11), (), (0, 0, 0)),
            ((7, 8), (), (0, 0, 1)),
            ((7, 9), (), (0, 0, 1)),
            ((7, 10), (), (0, 0, 1)),
            ((7, 11), (), (0, 0, 0)),
            ((7, 8, 9), (6,), (0, 0, 0)),
            ((7, 8, 10), (6,), (0, 0, 0)),
            ((7, 10), (6,), (0, 0, 0)),
            ((0, 1, 2), (), (0, 0, 0)),
            ((1, 2, 3), (), (1, 0, 0)),
            ((0, 2, 3), (), (0, 0, 0)),
            ((5, 7, 8, 9), (), (0, 0, 0)),
            ((7, 8, 9, 12), (), (1, 0, 0)),
            ((7, 8, 9, 10), (), (0, 0, 0)),
            ((7, 8, 10, 11), (), (0, 0, 0)),
        ]
        evaluator = ConfiguredEvaluator(EvaluationConfig(feature_version='potential-v1'))
        for own, other, expected in fixtures:
            baseline = evaluator(Position(board_with([(9, c) for c in own],
                                                      [(9, c) for c in other]), 0))
            for color in (0, 1):
                for reflect in (False, True):
                    for turns in range(4):
                        def transform(cell):
                            r, c = cell
                            if reflect:
                                c = 18 - c
                            for _ in range(turns):
                                r, c = c, 18 - r
                            return r, c
                        colors = [[transform((9, c)) for c in own],
                                  [transform((9, c)) for c in other]]
                        root = Position(board_with(*colors[::1 if color == 0 else -1]), color)
                        report = evaluator.inspect(root)
                        counts = report['potential']['black' if color == 0 else 'white']
                        with self.subTest(own=own, other=other, color=color, turns=turns, reflect=reflect):
                            self.assertEqual(tuple(counts[n] for n in
                                             ('open_three', 'broken_three', 'two_stone')), expected)
                            self.assertEqual(evaluator(root), report['total'])
                            self.assertEqual(report['total'], baseline * (1 if color == 0 else -1))

    def test_intersecting_lines_count_separate_stone_sets_and_development_is_geometric(self):
        own = [(9, c) for c in (7, 8, 9)] + [(r, 9) for r in (7, 8)]
        root = Position(board_with(own), 0)
        evaluator = ConfiguredEvaluator(EvaluationConfig(feature_version='potential-v1'))
        report = evaluator.inspect(root)
        self.assertEqual(report['potential']['black']['open_three'], 2)
        self.assertEqual(report['potential']['black']['units']['open_three'],
                         [((7, 9), (8, 9), (9, 9)), ((9, 7), (9, 8), (9, 9))])
        # Independent rules oracle verifies a documented development, not the counter.
        board = board_with([(9, c) for c in (7, 8, 9)])
        developed = ReferencePosition(board, 0).play((9, 10)).position
        self.assertEqual(developed.outcome, 'ongoing')
        for endpoint in ((9, 6), (9, 11)):
            self.assertEqual(ReferencePosition(developed.board, 0).play(endpoint).position.outcome,
                             'black_win')

    def test_potential_ablation_validation_bounds_and_legacy_identity(self):
        config = EvaluationConfig.load('configs/potential-v1.json')
        self.assertEqual(EvaluationConfig.from_json(config.canonical_json()), config)
        root = Position(board_with([(9, c) for c in (7, 8, 9)]), 0)
        evaluator = ConfiguredEvaluator(config)
        disabled = ConfiguredEvaluator(replace(config, potential_enabled=False))
        report = disabled.inspect(root)
        self.assertEqual(report['potential']['black']['open_three'], 1)
        self.assertEqual(report['contributions']['open_three'], 0)
        self.assertNotIn('potential', report['enabled_families'])
        self.assertEqual(disabled(root), 3)
        self.assertNotEqual(disabled.config.identity, config.identity)
        potential_only = ConfiguredEvaluator(replace(config, lines_enabled=False, material_enabled=False))
        self.assertEqual(potential_only(root), 40)
        self.assertEqual(potential_only.inspect(root)['total'], 40)
        saturated = ConfiguredEvaluator(replace(config, open_three=4000))
        self.assertEqual(saturated.inspect(root)['raw_total'], 4003)
        self.assertEqual(saturated(root), 4000)
        engine = FixedDepthSearch(evaluation_config=config, table=TranspositionTable(32))
        engine.search(root, 0)
        engine.set_evaluation_config(disabled.config)
        self.assertEqual(len(engine.table), 0)
        self.assertEqual(engine.search(root, 0).score, 3)
        for name in ('open_three', 'broken_three', 'two_stone'):
            for value in (True, 1.2, '40', None, -4001, 4001):
                with self.assertRaises(ValueError):
                    replace(config, **{name: value})
        for version in ('material-v1', 'lines-v1'):
            legacy = EvaluationConfig.load('configs/' + version + '.json')
            self.assertEqual(legacy.canonical_json(),
                             json.dumps(json.loads(Path('configs/' + version + '.json').read_text()),
                                        sort_keys=True, separators=(',', ':')))
            self.assertNotIn('open_three', legacy.coefficients())
            with self.assertRaises(ValueError):
                replace(legacy, open_three=41)
            with self.assertRaises(ValueError):
                replace(legacy, potential_enabled=False)
        for families in (['potential', 'potential'], ['unknown']):
            data = json.loads(config.canonical_json())
            data['enabled_families'] = families
            with self.assertRaises(ValueError):
                EvaluationConfig.from_json(json.dumps(data))

    def test_quiet_matched_trees_public_turns_and_cancellation(self):
        config = EvaluationConfig(feature_version='potential-v1')
        board = board_with([(9, c) for c in (7, 8, 9)], [(4, 4), (4, 6)])
        def candidates(position):
            return [cell for cell in ((9, 6), (9, 10), (4, 5))
                    if position.board[cell[0]][cell[1]] == -1]
        for side in (0, 1):
            root = Position(board, side)
            engine = FixedDepthSearch(evaluation_config=config, candidates=candidates,
                                      clock=lambda: 0, table=TranspositionTable(128))
            for depth in (0, 1, 2, 3):
                reference = engine.search(root, depth, reference=True)
                result = engine.search(root, depth)
                self.assertEqual(result.score, reference.score)
                if depth:
                    self.assertIn(result.move, reference.optimal_moves)
            self.assertEqual(engine.score(root, 0), -engine.score(root, 1))
            player = IterativePlayer(side, max_depth=2, search=engine, evaluation_config=config)
            move = player.take_turn(board, -1)
            reference = engine.search(root, 2, reference=True)
            self.assertIn(move, reference.optimal_moves)
            self.assertEqual(player.last_result.score, reference.score)
            self.assertEqual(board, [list(row) for row in root.board])
        evaluator = ConfiguredEvaluator(replace(config, lines_enabled=False))
        root = Position(board, 0)
        ticks = [0]
        def count():
            ticks[0] += 1
        evaluator(root, count)
        total = ticks[0]
        for stop in (1, total // 2, total - 1):
            ticks[0] = 0
            def cancel():
                ticks[0] += 1
                if ticks[0] >= stop:
                    raise SearchCancelled('potential scan')
            report = evaluator.inspect(root, check=cancel)
            self.assertTrue(report['incomplete'])
            self.assertIsNone(report['potential'])
            self.assertIsNone(report['total'])
            ticks[0] = 0
            engine = FixedDepthSearch(evaluation_config=evaluator.config, table=TranspositionTable(32))
            result = engine.search(root, 0, limits=SearchLimits(cancelled=lambda: (cancel() or False)))
            self.assertFalse(result.completed)
            self.assertEqual(len(engine.table), 0)
            self.assertEqual(root.board, tuple(tuple(row) for row in board))

    def test_mandatory_tactics_low_time_and_terminal_scores(self):
        config = EvaluationConfig(feature_version='potential-v1', open_three=-4000,
                                  broken_three=-4000, two_stone=-4000)
        for color in (0, 1):
            board = board_with()
            board[9][6:10] = [color] * 4
            board[9][5] = 1 - color
            player = IterativePlayer(color, max_depth=1,
                                     search=FixedDepthSearch(tactics=TacticalPolicy(cap=1), clock=lambda: 0),
                                     evaluation_config=config)
            self.assertEqual(player.take_turn(board, -1), (9, 10))
            self.assertEqual(player.last_result.score, 10000)
            for remaining in (0.001, 1):
                Position(board, color).play(player.take_turn(board, remaining))
            board[9][10] = color
            self.assertEqual(player.search.score(Position(board, 1 - color), color), 10000)
        board = board_with([(10, 7)], [(9, c) for c in range(6, 10)] + [(8, 7)])
        root = Position(board, 0)
        policy = TacticalPolicy(cap=1)
        player = IterativePlayer(0, max_depth=1,
                                 search=FixedDepthSearch(tactics=policy, clock=lambda: 0),
                                 evaluation_config=config)
        self.assertIn(player.take_turn(board, -1), policy.analyze(root).defenses)
        self.assertEqual(board, [list(row) for row in root.board])


if __name__ == '__main__':
    unittest.main()
