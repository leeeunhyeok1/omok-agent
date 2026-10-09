# AI-written by OpenAI Codex, for issue #17.
import unittest

from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
from omok.simulator import Position
from omok.player import IterativePlayer
from omok.search import FixedDepthSearch, SearchCancelled, SearchLimits
from omok.tactics import TacticalPolicy
from omok.transposition import TranspositionTable
from verification.reference import ReferencePosition


def board_with(black=(), white=()):
    board = [[-1] * 19 for _ in range(19)]
    for color, cells in enumerate((black, white)):
        for row, col in cells:
            board[row][col] = color
    return board


def line_config(**kwargs):
    return EvaluationConfig(feature_version='lines-v1', **kwargs)


class LineTests(unittest.TestCase):
    def test_open_four_has_two_unique_rule_verified_completions(self):
        board = board_with([(9, c) for c in range(6, 10)])
        report = ConfiguredEvaluator(line_config()).inspect(Position(board, 0))
        black = report['lines']['black']
        self.assertEqual(black['open_four'], 1)
        self.assertEqual(black['closed_four'], 0)
        self.assertEqual(black['broken_four'], 0)
        self.assertEqual(black['geometric_completions'], [(9, 5), (9, 10)])
        self.assertEqual(black['verified_wins'], [(9, 5), (9, 10)])
        for move in black['verified_wins']:
            self.assertEqual(ReferencePosition(board, 0).play(move).position.outcome, 'black_win')
        self.assertEqual(report['features']['verified_win'], 2)
        self.assertEqual(report['contributions']['open_four'], 300)
        self.assertEqual(report['total'], 904)

    def test_required_geometry_in_both_colors_and_all_board_symmetries(self):
        fixtures = [
            ([(9, c) for c in range(6, 10)], [(9, 5)], (0, 1, 0), [(9, 10)], []),
            ([(9, c) for c in (6, 7, 9, 10)], [], (0, 0, 1), [(9, 8)], []),
            ([(9, c) for c in (6, 7, 8, 10, 11)], [], (0, 0, 0), [], [(9, 9)]),
            ([(9, c) for c in range(4)], [], (0, 1, 0), [(9, 4)], []),
            ([(9, c) for c in (6, 7, 8, 9, 11)], [], (1, 0, 0), [(9, 5)], [(9, 10)]),
        ]
        evaluator = ConfiguredEvaluator(line_config())
        for own, other, counts, completions, traps in fixtures:
            baseline = evaluator.inspect(Position(board_with(own, other), 0))['total']
            for color in (0, 1):
                for reflection in (False, True):
                    for turns in range(4):
                        def transform(cell):
                            r, c = cell
                            if reflection:
                                c = 18 - c
                            for _ in range(turns):
                                r, c = c, 18 - r
                            return r, c
                        colors = [[transform(cell) for cell in own],
                                  [transform(cell) for cell in other]]
                        board = board_with(*colors[::1 if color == 0 else -1])
                        root = Position(board, 1 - color)
                        report = evaluator.inspect(root)
                        values = report['lines']['black' if color == 0 else 'white']
                        self.assertEqual(tuple(values[k] for k in ('open_four', 'closed_four', 'broken_four')), counts)
                        expected = sorted(transform(cell) for cell in completions)
                        self.assertEqual(values['geometric_completions'], expected)
                        self.assertEqual(values['verified_wins'], expected)
                        self.assertEqual(values['overline_traps'], sorted(transform(cell) for cell in traps))
                        self.assertEqual(report['total'], baseline * (1 if color == 0 else -1))
                        self.assertEqual(evaluator(root), report['total'])
                        oracle = ReferencePosition(board, color)
                        for move in expected:
                            self.assertEqual(oracle.play(move).position.outcome,
                                             'black_win' if color == 0 else 'white_win')
                        for move in values['overline_traps']:
                            self.assertEqual(oracle.play(move).position.outcome, 'ongoing')

    def test_shared_completions_and_overline_windows_are_not_multiplied(self):
        own = [(9, c) for c in range(5, 9)] + [(r, 9) for r in range(5, 9)]
        report = ConfiguredEvaluator(line_config()).inspect(Position(board_with(own), 0))
        black = report['lines']['black']
        self.assertEqual(black['open_four'], 2)
        self.assertEqual(black['geometric_completions'], [(4, 9), (9, 4), (9, 9)])
        self.assertEqual(black['verified_win'], 3)
        board = board_with([(9, c) for c in range(5, 11)])
        black = ConfiguredEvaluator(line_config()).inspect(Position(board, 0))['lines']['black']
        self.assertEqual(black['open_four'], 0)
        self.assertEqual(black['geometric_completions'], [])
        self.assertEqual(black['verified_wins'], [])

    def test_capture_exposing_opponent_five_excludes_geometric_draw(self):
        for color in (0, 1):
            for simultaneous in (False, True):
                board = board_with()
                board[9][5:11] = [1 - color] * 6
                board[10][10], board[11][10] = 1 - color, color
                if simultaneous:
                    board[8][6:10] = [color] * 4
                report = ConfiguredEvaluator(line_config()).inspect(Position(board, color))
                values = report['lines']['black' if color == 0 else 'white']
                if simultaneous:
                    self.assertIn((8, 10), values['geometric_completions'])
                    self.assertIn((8, 5), values['verified_wins'])
                self.assertNotIn((8, 10), values['verified_wins'])
                oracle = ReferencePosition(board, color).play((8, 10)).position
                self.assertEqual(oracle.outcome, 'draw' if simultaneous else
                                 ('white_win' if color == 0 else 'black_win'))

    def test_capturable_open_four_is_not_labeled_as_an_independent_forced_win(self):
        board = board_with([(10, 7)], [(9, c) for c in range(6, 10)] + [(8, 7)])
        evaluator = ConfiguredEvaluator(line_config())
        root = Position(board, 0)
        self.assertEqual(evaluator.inspect(root)['lines']['white']['verified_win'], 2)
        after = root.play((7, 7)).position
        self.assertEqual(after.board, ReferencePosition(board, 0).play((7, 7)).position.board)
        self.assertEqual(evaluator.inspect(after)['lines']['white']['verified_win'], 0)
        policy = TacticalPolicy(cap=1)
        player = IterativePlayer(0, max_depth=1, search=FixedDepthSearch(tactics=policy, clock=lambda: 0),
                                 evaluation_config=line_config())
        self.assertIn(player.take_turn(board, -1), policy.analyze(root).defenses)
        self.assertEqual(root.board, tuple(tuple(row) for row in board))

    def test_saved_configuration_bounds_ablation_and_cache_switching(self):
        config = line_config(material=4000, open_four=4000, verified_win=4000)
        self.assertEqual(EvaluationConfig.from_json(config.canonical_json()), config)
        self.assertEqual(EvaluationConfig.from_json(config.canonical_json()).identity, config.identity)
        root = Position(board_with([(9, c) for c in range(6, 10)]), 0)
        report = ConfiguredEvaluator(config).inspect(root)
        self.assertEqual(report['raw_total'], 28000)
        self.assertEqual(report['total'], 4000)
        self.assertTrue(report['saturated'])
        disabled = ConfiguredEvaluator(line_config(lines_enabled=False))
        self.assertEqual(disabled(root), 4)
        self.assertEqual(disabled.inspect(root)['features']['open_four'], 1)
        self.assertEqual(disabled.inspect(root)['contributions']['open_four'], 0)
        self.assertNotEqual(disabled.config.identity, line_config().identity)
        for value in (True, 1.5, '1', None, -4001, 4001):
            with self.assertRaises(ValueError):
                line_config(open_four=value)
        for families in (['lines', 'lines'], ['unknown'], ['material', 1]):
            import json
            data = json.loads(config.canonical_json())
            data['enabled_families'] = families
            with self.assertRaises(ValueError):
                EvaluationConfig.from_json(json.dumps(data))
        engine = FixedDepthSearch(evaluation_config=line_config(), table=TranspositionTable(32))
        engine.search(root, 1)
        self.assertGreater(len(engine.table), 0)
        engine.set_evaluation_config(disabled.config)
        self.assertEqual(len(engine.table), 0)
        self.assertEqual(engine.search(root, 0).score, 4)
        self.assertEqual(engine.search(root, 0).score,
                         FixedDepthSearch(evaluation_config=disabled.config).search(root, 0).score)

    def test_expensive_scan_cancellation_preserves_positions_and_partial_status(self):
        board = board_with([(11, 10)] + [(8, c) for c in range(6, 10)],
                           [(9, c) for c in range(5, 11)] + [(10, 10)])
        root = Position(board, 0)
        child = root.play((8, 10)).position
        evaluator = ConfiguredEvaluator(line_config())
        ticks = [0]
        def measure():
            ticks[0] += 1
        evaluator(root, measure)
        total = ticks[0]
        for stop in (1, total // 4, total // 2, 3 * total // 4, total - 1):
            ticks[0] = 0
            def cancel():
                ticks[0] += 1
                if ticks[0] >= stop:
                    raise SearchCancelled('line scan')
            report = evaluator.inspect(root, check=cancel)
            self.assertTrue(report['incomplete'])
            self.assertIsNone(report['features'])
            self.assertIsNone(report['lines'])
            self.assertIsNone(report['total'])
            ticks[0] = 0
            with self.assertRaisesRegex(SearchCancelled, 'line scan'):
                evaluator(root, cancel)
            ticks[0] = 0
            engine = FixedDepthSearch(evaluation_config=line_config(), table=TranspositionTable(32))
            result = engine.search(root, 0, limits=SearchLimits(cancelled=lambda: (cancel() or False)))
            self.assertFalse(result.completed)
            self.assertIsNone(result.score)
            self.assertEqual(len(engine.table), 0)
            self.assertEqual(root.board, tuple(tuple(row) for row in board))
            self.assertEqual(child, root.play((8, 10)).position)
        self.assertEqual(evaluator(root), evaluator.inspect(root)['total'])

    def test_matched_trees_public_wins_and_terminal_priorities(self):
        board = board_with([(9, c) for c in (6, 7, 9, 10)], [(3, 3)])
        def candidates(position):
            return [move for move in ((9, 8), (9, 5), (9, 11), (3, 4))
                    if position.board[move[0]][move[1]] == -1]
        for side in (0, 1):
            root = Position(board, side)
            engine = FixedDepthSearch(evaluation_config=line_config(), candidates=candidates,
                                      table=TranspositionTable(128))
            for depth in (0, 1, 2, 3):
                reference = engine.search(root, depth, reference=True)
                actual = engine.search(root, depth)
                self.assertEqual(actual.score, reference.score)
                if depth:
                    self.assertIn(actual.move, reference.optimal_moves)
            self.assertEqual(engine.score(root, 0), -engine.score(root, 1))
        for color in (0, 1):
            board = board_with()
            board[9][6:10] = [color] * 4
            board[9][5] = 1 - color
            engine = FixedDepthSearch(tactics=TacticalPolicy(cap=1), clock=lambda: 0)
            config = line_config(open_four=-4000, closed_four=-4000, verified_win=-4000)
            player = IterativePlayer(color, max_depth=1, search=engine, evaluation_config=config)
            self.assertEqual(player.take_turn(board, -1), (9, 10))
            self.assertEqual(player.last_result.score, 10000)
            self.assertEqual(ReferencePosition(board, color).play((9, 10)).position.outcome,
                             'black_win' if color == 0 else 'white_win')
            for remaining in (0.001, 1):
                move = player.take_turn(board, remaining)
                Position(board, color).play(move)
            self.assertEqual(board[9][10], -1)
        board = board_with([(0, c) for c in range(5)])
        engine = FixedDepthSearch(evaluation_config=line_config(material=-4000))
        root = Position(board, 0)
        self.assertEqual(engine.score(root, 0), 10000)
        self.assertEqual(engine.score(root, 1), -10000)
        board[1][:5] = [1] * 5
        root = Position(board, 0)
        self.assertEqual(engine.score(root, 0), 0)
        self.assertEqual(ConfiguredEvaluator(line_config()).inspect(root)['lines']['black']['verified_wins'], [])


if __name__ == '__main__':
    unittest.main()
