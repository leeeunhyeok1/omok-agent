# AI-written by OpenAI Codex, for issue #19.
import unittest
import json
from pathlib import Path

from omok.player import IterativePlayer
from omok.search import FixedDepthSearch, SearchCancelled, SearchLimits
from omok.tactics import TacticalPolicy
from omok.transposition import TranspositionTable
from dataclasses import replace

from verification.reference import ReferencePosition

from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
from omok.simulator import Position
from tests.test_lines import board_with


class CaptureTests(unittest.TestCase):
    def test_multi_pair_capture_is_one_move_with_explicit_multiplicity(self):
        board = board_with([(9, 12), (12, 9)],
                           [(9, 10), (9, 11), (10, 9), (11, 9)])
        report = ConfiguredEvaluator(EvaluationConfig(feature_version='capture-v1')).inspect(Position(board, 0))
        black = report['captures']['black']
        self.assertEqual(black['capture_move'], 1)
        self.assertEqual(black['capture_pair'], 2)
        self.assertEqual(black['multi_pair_move'], 1)
        self.assertEqual(black['moves'][0]['move'], (9, 9))
        self.assertEqual(black['moves'][0]['pair_count'], 2)
        self.assertEqual(black['moves'][0]['cell_count'], 4)
        self.assertEqual(black['moves'][0]['cells'], [(9, 10), (9, 11), (10, 9), (11, 9)])
        self.assertEqual(report['captures']['white']['vulnerable_pair'], 2)

    def test_invalid_rays_and_actual_vulnerability_control(self):
        evaluator = ConfiguredEvaluator(EvaluationConfig(feature_version='capture-v1'))
        fixtures = [
            ([(9, 12)], [(9, 10), (9, 11), (9, 9)]),  # occupied completion
            ([], [(9, 10), (9, 11)]),  # absent own endpoint
            ([(9, 12)], [(9, 10)]),  # missing enemy
            ([(9, 0)], [(9, 1), (9, 2), (9, 3)]),  # three is not two
            ([], [(9, 17), (9, 18)]),  # truncated ray
        ]
        for own, other in fixtures:
            report = evaluator.inspect(Position(board_with(own, other), 0))
            self.assertEqual(report['captures']['black']['capture_move'], 0)
            self.assertEqual(report['captures']['white']['vulnerable_pair'], 0)
        board = board_with([(10, 7)], [(9, c) for c in range(6, 10)] + [(8, 7)])
        report = evaluator.inspect(Position(board, 0))
        self.assertEqual(report['captures']['white']['vulnerable_pairs'], [((8, 7), (9, 7))])
        child = Position(board, 0).play((7, 7)).position
        self.assertEqual(child.board, ReferencePosition(board, 0).play((7, 7)).position.board)
        self.assertEqual(evaluator.inspect(child)['lines']['white']['verified_win'], 0)
        board[8][7] = -1
        self.assertEqual(evaluator.inspect(Position(board, 0))['captures']['white']['vulnerable_pair'], 0)

    def test_eight_rays_colors_and_symmetries_against_rules_reference(self):
        evaluator = ConfiguredEvaluator(EvaluationConfig(feature_version='capture-v1'))
        directions = ((0, 1), (1, 0), (1, 1), (1, -1), (0, -1), (-1, 0), (-1, -1), (-1, 1))
        for color in (0, 1):
            for dr, dc in directions:
                own = [(9 + 3 * dr, 9 + 3 * dc)]
                enemy = [(9 + n * dr, 9 + n * dc) for n in (1, 2)]
                for reflection in (False, True):
                    for turns in range(4):
                        def transform(cell):
                            r, c = cell
                            if reflection:
                                c = 18 - c
                            for _ in range(turns):
                                r, c = c, 18 - r
                            return r, c
                        colors = [[transform(c) for c in own], [transform(c) for c in enemy]]
                        board = board_with(*colors[::1 if color == 0 else -1])
                        root = Position(board, 1 - color)
                        report = evaluator.inspect(root)
                        values = report['captures']['black' if color == 0 else 'white']
                        self.assertEqual(values['capture_move'], 1)
                        self.assertEqual(values['capture_pair'], 1)
                        move = values['moves'][0]
                        self.assertEqual(move['move'], transform((9, 9)))
                        self.assertEqual(move['cells'], sorted(transform(c) for c in enemy))
                        oracle = ReferencePosition(board, color).play(move['move'])
                        self.assertEqual(move['outcome'], oracle.position.outcome)
                        self.assertEqual(move['cells'], [item.cell for item in oracle.captured])
                        self.assertEqual(report['features']['capture_move'], 1 if color == 0 else -1)
                        self.assertEqual(report['features']['vulnerable_pair'], -1 if color == 0 else 1)
                        self.assertEqual(evaluator(root), report['total'])

    def test_capture_outcomes_never_mislabel_opponent_win_or_draw(self):
        evaluator = ConfiguredEvaluator(EvaluationConfig(feature_version='capture-v1'))
        for color in (0, 1):
            for simultaneous in (False, True):
                board = board_with()
                board[9][5:11] = [1 - color] * 6
                board[10][10], board[11][10] = 1 - color, color
                if simultaneous:
                    board[8][6:10] = [color] * 4
                root = Position(board, color)
                values = evaluator.inspect(root)['captures']['black' if color == 0 else 'white']
                move = next(m for m in values['moves'] if m['move'] == (8, 10))
                oracle = ReferencePosition(board, color).play((8, 10))
                self.assertEqual(move['outcome'], oracle.position.outcome)
                self.assertEqual(move['classification'], 'draw' if simultaneous else 'opponent_win')
                self.assertEqual(move['cells'], [c.cell for c in oracle.captured])
                self.assertLessEqual(abs(evaluator(root)), 4000)
                child_report = evaluator.inspect(root.play((8, 10)).position)
                self.assertEqual(child_report['captures']['black']['capture_move'], 0)
                self.assertEqual(child_report['captures']['white']['capture_move'], 0)

    def test_saved_configuration_validation_ablation_and_interleaving(self):
        config = EvaluationConfig.load('configs/capture-v1.json')
        self.assertEqual(EvaluationConfig.from_json(config.canonical_json()), config)
        self.assertEqual(config.feature_version, 'capture-v1')
        board = board_with([(9, 12)], [(9, 10), (9, 11)])
        root = Position(board, 0)
        capture_only = replace(config, material_enabled=False, lines_enabled=False, potential_enabled=False)
        evaluator = ConfiguredEvaluator(capture_only)
        self.assertEqual(evaluator(root), 80)  # 30 opportunity + 10 pair + 40 enemy risk
        risk_only = ConfiguredEvaluator(replace(capture_only, capture_move=0, capture_pair=0, multi_pair_move=0))
        self.assertEqual(risk_only(root), 40)
        disabled = ConfiguredEvaluator(replace(capture_only, captures_enabled=False))
        self.assertEqual(disabled(root), 0)
        self.assertEqual(disabled.inspect(root)['features']['capture_move'], 1)
        self.assertEqual(disabled.inspect(root)['contributions']['capture_move'], 0)
        self.assertNotEqual(disabled.config.identity, capture_only.identity)
        for _ in range(3):
            self.assertEqual(evaluator(root), 80)
            self.assertEqual(disabled(root), 0)
            self.assertEqual(risk_only(root), 40)
        extreme = ConfiguredEvaluator(replace(capture_only, capture_move=4000, capture_pair=4000, vulnerable_pair=-4000))
        self.assertEqual(extreme.inspect(root)['raw_total'], 12000)
        self.assertEqual(extreme(root), 4000)
        self.assertTrue(extreme.inspect(root)['saturated'])
        for name in ('capture_move', 'capture_pair', 'multi_pair_move', 'vulnerable_pair'):
            for value in (True, 1.5, '30', None, 4001, -4001):
                with self.assertRaises(ValueError):
                    replace(config, **{name: value})
        for value in (1, None, 'true'):
            with self.assertRaises(ValueError):
                replace(config, captures_enabled=value)
        for version in ('material-v1', 'lines-v1', 'potential-v1'):
            legacy = EvaluationConfig.load('configs/' + version + '.json')
            self.assertEqual(legacy.canonical_json(), json.dumps(json.loads(Path('configs/' + version + '.json').read_text()), sort_keys=True, separators=(',', ':')))
            with self.assertRaises(ValueError):
                replace(legacy, capture_move=31)
            with self.assertRaises(ValueError):
                replace(legacy, captures_enabled=False)
        for families in (['captures', 'captures'], ['unknown']):
            data = json.loads(config.canonical_json())
            data['enabled_families'] = families
            with self.assertRaises(ValueError):
                EvaluationConfig.from_json(json.dumps(data))

    def test_cancellation_never_publishes_partial_features_or_exact_scores(self):
        board = board_with([(9, 12), (12, 9)], [(9, 10), (9, 11), (10, 9), (11, 9)])
        root = Position(board, 0)
        config = EvaluationConfig(feature_version='capture-v1', material_enabled=False,
                                  lines_enabled=False, potential_enabled=False)
        evaluator = ConfiguredEvaluator(config)
        ticks = [0]
        def count():
            ticks[0] += 1
        evaluator(root, count)
        total = ticks[0]
        # Sweep checkpoints around hypothetical work as well as scan/publication boundaries.
        for stop in (1, total // 2, total - 1, *range(1440, 1520)):
            ticks[0] = 0
            def cancel():
                ticks[0] += 1
                if ticks[0] >= stop:
                    raise SearchCancelled('capture work')
            with self.assertRaises(SearchCancelled):
                evaluator(root, cancel)
            ticks[0] = 0
            engine = FixedDepthSearch(evaluation_config=config, table=TranspositionTable(32))
            result = engine.search(root, 0, limits=SearchLimits(cancelled=lambda: (cancel() or False)))
            self.assertFalse(result.completed)
            self.assertEqual(len(engine.table), 0)
            self.assertEqual(root.board, tuple(tuple(row) for row in board))
        ticks[0] = 0
        evaluator.inspect(root, check=count)
        inspection_total = ticks[0]
        ticks[0] = 0
        def cancel_late():
            ticks[0] += 1
            if ticks[0] >= inspection_total:
                raise SearchCancelled('inspection')
        # Cancellation of inspection must hide every family, including completed earlier scans.
        report = evaluator.inspect(root, check=cancel_late)
        self.assertTrue(report['incomplete'])
        for key in ('features', 'contributions', 'total', 'captures', 'lines', 'potential'):
            self.assertIsNone(report[key])
        self.assertEqual(root.board, tuple(tuple(row) for row in board))

    def test_matched_tree_public_turns_perspective_and_cache_switching(self):
        config = EvaluationConfig(feature_version='capture-v1')
        board = board_with([(9, 12)], [(9, 10), (9, 11)])
        root = Position(board, 0)
        def candidates(position):
            return [cell for cell in ((9, 9), (8, 10), (8, 11))
                    if position.board[cell[0]][cell[1]] == -1]
        for side in (0, 1):
            engine = FixedDepthSearch(evaluation_config=config, candidates=candidates,
                                      clock=lambda: 0, table=TranspositionTable(128))
            root = Position(board, side)
            self.assertEqual(engine.score(root, 0), -engine.score(root, 1))
            for depth in (0, 1, 2, 3):
                reference = engine.search(root, depth, reference=True)
                result = engine.search(root, depth)
                self.assertEqual(result.score, reference.score)
                if depth:
                    self.assertIn(result.move, reference.optimal_moves)
            player = IterativePlayer(side, max_depth=2, search=engine, evaluation_config=config)
            move = player.take_turn(board, -1)
            reference = engine.search(root, 2, reference=True)
            self.assertIn(move, reference.optimal_moves)
            self.assertEqual(player.last_result.score, reference.score)
            self.assertEqual(board, [list(row) for row in root.board])
            disabled = replace(config, captures_enabled=False)
            engine.set_evaluation_config(disabled)
            self.assertEqual(len(engine.table), 0)
            fresh = FixedDepthSearch(evaluation_config=disabled, candidates=candidates, clock=lambda: 0)
            self.assertEqual(engine.search(root, 2).score, fresh.search(root, 2).score)

    def test_tactical_protection_and_terminal_priority_with_extreme_weights(self):
        config = EvaluationConfig(feature_version='capture-v1', capture_move=-4000,
                                  capture_pair=-4000, multi_pair_move=-4000, vulnerable_pair=4000)
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
            for simultaneous in (False, True):
                board = board_with()
                board[9][5:11] = [1 - color] * 6
                board[10][10], board[11][10] = 1 - color, color
                if simultaneous:
                    board[8][6:10] = [color] * 4
                child = Position(board, color).play((8, 10)).position
                self.assertEqual(player.search.score(child, color), 0 if simultaneous else -10000)
        board = board_with([(10, 7)], [(9, c) for c in range(6, 10)] + [(8, 7)])
        root = Position(board, 0)
        policy = TacticalPolicy(cap=1)
        player = IterativePlayer(0, max_depth=1, search=FixedDepthSearch(tactics=policy, clock=lambda: 0),
                                 evaluation_config=config)
        self.assertIn(player.take_turn(board, -1), policy.analyze(root).defenses)
        self.assertEqual(board, [list(row) for row in root.board])


if __name__ == '__main__':
    unittest.main()
