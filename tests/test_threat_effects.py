# AI-written by OpenAI Codex, for issue #20.
import unittest

from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
from omok.simulator import Position
from tests.test_lines import board_with


class ThreatEffectTests(unittest.TestCase):
    def test_capture_defense_explains_destroyed_four_and_shared_endpoints(self):
        board = board_with([(10, 7)], [(9, c) for c in range(6, 10)] + [(8, 7)])
        evaluator = ConfiguredEvaluator(EvaluationConfig(feature_version='effects-v1'))
        report = evaluator.inspect(Position(board, 0))
        effect = next(e for e in report['effects']['black']['moves'] if e['move'] == (7, 7))
        self.assertEqual(effect['after']['white']['open_four'], 0)
        self.assertEqual(effect['before']['white']['open_four'], 1)
        self.assertEqual(effect['removed'], [(8, 7), (9, 7)])
        self.assertEqual(report['effects']['black']['capture_break_four'], 1)
        threats = report['multiplicity']['white']
        self.assertEqual(threats['verified_endpoints'], [(9, 5), (9, 10)])
        self.assertIn((7, 7), threats['shared_capture_defenders'])
        self.assertEqual(threats['independence'], 'refuted')
        board[8][7] = -1
        control = evaluator.inspect(Position(board, 0))
        self.assertEqual(control['effects']['black']['capture_break_four'], 0)
        self.assertEqual(control['multiplicity']['white']['independence'], 'verified')

    def test_captured_blockers_reopen_a_broken_three_without_becoming_own_stones(self):
        # Capturing (9,8)/(10,8) vertically opens the internal gap of black's
        # horizontal three. The placement itself is off that line.
        board = board_with([(11, 8), (9, 6), (9, 7), (9, 9)], [(9, 8), (10, 8)])
        root = Position(board, 0)
        report = ConfiguredEvaluator(EvaluationConfig(feature_version='effects-v1')).inspect(root)
        effect = next(e for e in report['effects']['black']['moves'] if e['move'] == (8, 8))
        self.assertEqual(effect['after']['black']['broken_three'], 1)
        self.assertEqual(effect['before']['black']['broken_three'], 0)
        self.assertEqual(effect['capture_opened_units']['potential'], [((8, 8), (11, 8)), ((9, 6), (9, 7), (9, 9))])
        self.assertEqual(report['effects']['black']['capture_remove_blocker'], 1)
        self.assertEqual(root.play((8, 8)).position.board[9][8], -1)
        self.assertEqual(root.board[9][8], 1)

    def test_move_created_multiplicity_deduplicates_intersecting_endpoints(self):
        board = board_with([(9, 6), (9, 7), (9, 8), (6, 9), (7, 9), (8, 9)])
        evaluator = ConfiguredEvaluator(EvaluationConfig(feature_version='effects-v1'))
        report = evaluator.inspect_move(Position(board, 0), (9, 9))
        self.assertFalse(report['incomplete'])
        self.assertEqual(report['created_verified_endpoints']['black'],
                         [(5, 9), (9, 5), (9, 10), (10, 9)])
        self.assertEqual(report['after']['multiplicity']['black']['independence'], 'verified')
        # Two perpendicular broken fours share one completion: not two threats.
        board = board_with([(9, 7), (9, 8), (9, 10), (9, 11),
                            (7, 9), (8, 9), (10, 9), (11, 9)])
        report = evaluator.inspect(Position(board, 0))
        self.assertEqual(report['lines']['black']['broken_four'], 2)
        self.assertEqual(report['multiplicity']['black']['geometric_endpoints'], [(9, 9)])
        self.assertEqual(report['multiplicity']['black']['verified_multiple'], 0)

    def test_capture_affects_intersecting_fours_and_exposes_opponent_five(self):
        from verification.reference import ReferencePosition
        evaluator = ConfiguredEvaluator(EvaluationConfig(feature_version='effects-v1'))
        board = board_with([(10, 7)], [(9, c) for c in range(6, 10)] + [(8, 7), (7, 6), (6, 5)])
        report = evaluator.inspect(Position(board, 0))
        effect = next(e for e in report['effects']['black']['moves'] if e['move'] == (7, 7))
        self.assertEqual(effect['before']['white']['open_four'], 2)
        self.assertEqual(effect['after']['white']['open_four'], 0)
        self.assertEqual(len(effect['changed_units']['white']['fours']['removed']), 2)
        for color in (0, 1):
            for simultaneous in (False, True):
                board = board_with()
                board[9][5:11] = [1 - color] * 6
                board[10][10], board[11][10] = 1 - color, color
                if simultaneous:
                    board[8][6:10] = [color] * 4
                report = evaluator.inspect(Position(board, color))
                effects = report['effects']['black' if color == 0 else 'white']
                effect = next(e for e in effects['moves'] if e['move'] == (8, 10))
                self.assertEqual(effect['outcome'], ReferencePosition(board, color).play((8, 10)).position.outcome)
                enemy = 'white' if color == 0 else 'black'
                self.assertEqual(effect['before'][enemy]['overlines'], [tuple((9, c) for c in range(5, 11))])
                self.assertEqual(effect['after'][enemy]['exact_fives'], [tuple((9, c) for c in range(5, 10))])
                self.assertEqual(effects['capture_expose_five'], 1)
                self.assertEqual(effects['capture_create_four'], 0)

    def test_color_and_geometric_symmetry_and_public_capture_defense_under_caps(self):
        from omok.player import IterativePlayer
        from omok.search import FixedDepthSearch
        from omok.tactics import TacticalPolicy
        from verification.reference import ReferencePosition
        config = EvaluationConfig(feature_version='effects-v1', capture_break_four=-4000,
                                  capture_move=-4000, vulnerable_pair=4000)
        evaluator = ConfiguredEvaluator(config)
        base = board_with([(10, 7)], [(9, c) for c in range(6, 10)] + [(8, 7)])
        baseline = evaluator(Position(base, 0))
        for color in (0, 1):
            for reflected in (False, True):
                for turns in range(4):
                    def transform(cell):
                        r, c = cell
                        if reflected:
                            c = 18 - c
                        for _ in range(turns):
                            r, c = c, 18 - r
                        return r, c
                    board = board_with()
                    for r in range(19):
                        for c in range(19):
                            if base[r][c] != -1:
                                x, y = transform((r, c))
                                board[x][y] = base[r][c] if color == 0 else 1 - base[r][c]
                    root = Position(board, color)
                    report = evaluator.inspect(root)
                    self.assertEqual(report['total'], baseline if color == 0 else -baseline)
                    threat_color = 'white' if color == 0 else 'black'
                    self.assertIn(transform((7, 7)), report['multiplicity'][threat_color]['shared_capture_defenders'])
                    engine = FixedDepthSearch(tactics=TacticalPolicy(cap=1, radius=0), clock=lambda: 0,
                                              evaluation_config=config)
                    self.assertEqual(engine.score(root, 0), -engine.score(root, 1))
                    player = IterativePlayer(color, max_depth=1, search=engine)
                    move = player.take_turn(board, -1)
                    self.assertIn(transform((7, 7)), player.last_result.tactics.candidates)
                    self.assertIn(move, player.last_result.tactics.defenses)
                    child = ReferencePosition(board, color).play(move).position
                    self.assertEqual(child.outcome, 'ongoing')
                    self.assertEqual(child.board[transform((9, 7))[0]][transform((9, 7))[1]], -1)
                    self.assertEqual(board, [list(row) for row in root.board])

    def test_context_ablation_validation_bounds_and_legacy_configuration_identity(self):
        import json
        from pathlib import Path
        from dataclasses import replace
        from omok.search import FixedDepthSearch
        config = EvaluationConfig(feature_version='effects-v1', material_enabled=False, lines_enabled=False,
                                  potential_enabled=False, captures_enabled=False, effects_enabled=False)
        evaluator = ConfiguredEvaluator(config)
        board = board_with([(9, c) for c in range(6, 10)])
        self.assertEqual(evaluator(Position(board, 0)), 170)
        self.assertEqual(evaluator(Position(board, 1)), 250)
        swapped = board_with([], [(9, c) for c in range(6, 10)])
        self.assertEqual(evaluator(Position(swapped, 1)), -170)
        self.assertEqual(evaluator(Position(swapped, 0)), -250)
        engine = FixedDepthSearch(evaluation_config=config)
        self.assertEqual(engine.score(Position(board, 1), 0), 250)
        self.assertEqual(engine.score(Position(board, 1), 1), -250)
        disabled = ConfiguredEvaluator(replace(config, multiplicity_enabled=False))
        self.assertEqual(disabled(Position(board, 0)), 0)
        self.assertEqual(disabled.inspect(Position(board, 0))['features']['verified_multiple'], 1)
        extreme = ConfiguredEvaluator(replace(config, verified_multiple=4000, offensive_opportunity=4000))
        self.assertEqual(extreme(Position(board, 0)), 4000)
        self.assertTrue(extreme.inspect(Position(board, 0))['saturated'])
        self.assertEqual(EvaluationConfig.from_json(config.canonical_json()), config)
        for name in ('capture_break_four', 'capture_break_potential', 'capture_create_four',
                     'capture_create_potential', 'capture_remove_blocker', 'capture_expose_five',
                     'geometric_multiple', 'verified_multiple', 'offensive_opportunity', 'defensive_urgency'):
            for invalid in (True, 1.5, None, 4001, -4001):
                with self.assertRaises(ValueError):
                    replace(config, **{name: invalid})
        for family in ('effects', 'multiplicity'):
            with self.assertRaises(ValueError):
                replace(config, **{family + '_enabled': 1})
        for version in ('material-v1', 'lines-v1', 'potential-v1', 'capture-v1'):
            path = Path('configs/' + version + '.json')
            legacy = EvaluationConfig.load(path)
            self.assertEqual(legacy.canonical_json(), json.dumps(json.loads(path.read_text()), sort_keys=True, separators=(',', ':')))
            with self.assertRaises(ValueError):
                replace(legacy, effects_enabled=False)
            with self.assertRaises(ValueError):
                replace(legacy, defensive_urgency=101)

    def test_cancellation_hides_partial_evidence_and_preserves_parent_and_search_table(self):
        from omok.search import FixedDepthSearch, SearchCancelled, SearchLimits
        from omok.transposition import TranspositionTable
        root = Position(board_with([(10, 7)], [(9, c) for c in range(6, 10)] + [(8, 7)]), 0)
        config = EvaluationConfig(feature_version='effects-v1')
        evaluator = ConfiguredEvaluator(config)
        ticks = [0]
        def count():
            ticks[0] += 1
        evaluator.inspect(root, check=count)
        total = ticks[0]
        for stop in (1, total // 2, total - 1):
            ticks[0] = 0
            def cancel():
                ticks[0] += 1
                if ticks[0] >= stop:
                    raise SearchCancelled('effect inspection')
            report = evaluator.inspect(root, check=cancel)
            self.assertTrue(report['incomplete'])
            for key in ('total', 'features', 'lines', 'captures', 'effects', 'multiplicity'):
                self.assertIsNone(report[key])
        ticks[0] = 0
        report = evaluator.inspect_move(root, (7, 7), check=cancel)
        self.assertTrue(report['incomplete'])
        self.assertIsNone(report['after'])
        ticks[0] = 0
        evaluator(root, count)
        stop = ticks[0] - 1
        ticks[0] = 0
        with self.assertRaises(SearchCancelled):
            evaluator(root, cancel)
        ticks[0] = 0
        engine = FixedDepthSearch(evaluation_config=config, table=TranspositionTable(32))
        result = engine.search(root, 0, limits=SearchLimits(cancelled=lambda: (cancel() or False)))
        self.assertFalse(result.completed)
        self.assertEqual(len(engine.table), 0)
        self.assertEqual(root.board[9][7], 1)
        self.assertEqual(root.play((7, 7)).position.board[9][7], -1)

    def test_matched_trees_interleaving_and_configuration_switch(self):
        from dataclasses import replace
        from omok.search import FixedDepthSearch
        from omok.transposition import TranspositionTable
        config = EvaluationConfig(feature_version='effects-v1')
        disabled = replace(config, effects_enabled=False, multiplicity_enabled=False)
        root = Position(board_with([(9, 12)], [(9, 10), (9, 11)]), 0)
        def candidates(position):
            return [m for m in ((9, 9), (8, 10), (8, 11)) if position.board[m[0]][m[1]] == -1]
        engine = FixedDepthSearch(evaluation_config=config, candidates=candidates, clock=lambda: 0,
                                  table=TranspositionTable(128))
        for side in (0, 1):
            position = Position(root.board, side)
            for depth in (0, 1, 2, 3):
                reference = engine.search(position, depth, reference=True)
                actual = engine.search(position, depth)
                self.assertEqual(actual.score, reference.score)
                if depth:
                    self.assertIn(actual.move, reference.optimal_moves)
        old = ConfiguredEvaluator(config)(root)
        for _ in range(2):
            ConfiguredEvaluator(disabled)(root)
            self.assertEqual(ConfiguredEvaluator(config)(root), old)
        engine.set_evaluation_config(disabled)
        self.assertEqual(len(engine.table), 0)
        fresh = FixedDepthSearch(evaluation_config=disabled, candidates=candidates, clock=lambda: 0)
        self.assertEqual(engine.search(root, 3).score, fresh.search(root, 3).score)
