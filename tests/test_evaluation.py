# AI-written by OpenAI Codex, for issues #16 and #23.
import json
from pathlib import Path
import tempfile
import unittest

from omok.evaluation import EvaluationConfig, ConfiguredEvaluator
from omok.search import FixedDepthSearch, material_evaluation, SearchCancelled, SearchLimits
from omok.simulator import Position
from omok.player import IterativePlayer
from omok.transposition import TranspositionTable


def candidates(position):
    return [move for move in ((9, 9), (3, 3), (4, 4), (5, 5))
            if position.board[move[0]][move[1]] == -1]


class EvaluationTests(unittest.TestCase):
    def test_restored_phase_checkpoints_load_inspect_and_keep_agents_independent(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'restoration.json'
            process = subprocess.run([sys.executable, '-m', 'verification.checkpoint',
                                      '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report['phase2']['probe']['material_score'], 1)
            probe = report['phase3']['probe']
            self.assertEqual(probe['features']['open_four'], 1)
            self.assertEqual(probe['features']['verified_win'], 2)
            self.assertEqual(probe['terminal_score'], 10000)
            self.assertTrue(probe['agent_isolation'])
            self.assertTrue(probe['input_unchanged'])
            self.assertEqual(len(probe['configurations']), 5)

    def test_invalid_saved_configurations_fail_before_changing_live_engine(self):
        valid = json.loads(EvaluationConfig().canonical_json())
        invalid = [None, [], {}, dict(valid, unknown=1),
                   dict(valid, feature_version='future-v9'),
                   dict(valid, enabled_families=['threats']),
                   dict(valid, enabled_families=['material', 'material']),
                   dict(valid, enabled_families='material'),
                   dict(valid, coefficients={'material': 1, 'typo': 2})]
        invalid += [dict(valid, coefficients={'material': value})
                    for value in (True, 1.5, '1', None, float('nan'),
                                  float('inf'), -4001, 4001)]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                EvaluationConfig.from_json(json.dumps(data))
        with self.assertRaises(ValueError):
            EvaluationConfig.from_json('{"feature_version":"material-v1","feature_version":"material-v1"}')
        with self.assertRaises(ValueError):
            EvaluationConfig(material_enabled=1)
        engine = FixedDepthSearch(evaluation_config=EvaluationConfig())
        old = engine.cache_compatibility()
        with self.assertRaises(ValueError):
            engine.set_evaluation_config({'material': 2})
        self.assertEqual(engine.cache_compatibility(), old)

    def test_inspection_explains_bounding_ablation_and_cancelled_work(self):
        board = [list(row) for row in Position.empty().board]
        board[0][:3] = [0, 0, 1]
        root = Position(board, 1)
        for weight, expected in ((1, 1), (-1, -1), (4000, 4000), (-4000, -4000)):
            evaluator = ConfiguredEvaluator(EvaluationConfig(weight))
            report = evaluator.inspect(root)
            self.assertEqual(report['features'], {'material': 1})
            self.assertEqual(report['contributions'], {'material': expected})
            self.assertEqual(report['total'], expected)
            self.assertFalse(report['saturated'])
            self.assertFalse(report['incomplete'])
        board[0][3] = 0
        root = Position(board, 1)
        evaluator = ConfiguredEvaluator(EvaluationConfig(4000))
        report = evaluator.inspect(root)
        self.assertEqual((report['raw_total'], report['total'], report['saturated']),
                         (8000, 4000, True))
        disabled = ConfiguredEvaluator(EvaluationConfig(4000, False))
        self.assertEqual(disabled(root), 0)
        self.assertEqual(disabled.inspect(root)['features'], {'material': 2})
        calls = [0]
        def check():
            calls[0] += 1
            if calls[0] == 4:
                raise SearchCancelled('requested')
        report = evaluator.inspect(root, check=check)
        self.assertTrue(report['incomplete'])
        self.assertIsNone(report['total'])
        self.assertIsNone(report['features'])
        calls[0] = 0
        engine = FixedDepthSearch(evaluation_config=evaluator.config,
                                  table=TranspositionTable(128))
        result = engine.search(root, 0, limits=SearchLimits(cancelled=lambda: (check() or False)))
        self.assertFalse(result.completed)
        self.assertIsNone(result.score)
        self.assertEqual(len(engine.table), 0)
        self.assertEqual(root.board, tuple(tuple(row) for row in board))
        self.assertEqual(engine.search(root, 0).score, -4000)

    def test_material_matched_trees_and_terminal_contract_are_retained(self):
        board = [list(row) for row in Position.empty().board]
        board[9][10:13] = [1, 1, 0]
        for side in (0, 1):
            root = Position(board, side)
            engine = FixedDepthSearch(candidates=candidates, table=TranspositionTable(128),
                                      evaluation_config=EvaluationConfig())
            old = FixedDepthSearch(candidates=candidates)
            for depth in (1, 3, 2, 3):
                reference = old.search(root, depth, reference=True)
                result = engine.search(root, depth)
                self.assertEqual(result.score, reference.score)
                self.assertIn(result.move, reference.optimal_moves)
        board[0][:5] = [0] * 5
        root = Position(board, 0)
        engine = FixedDepthSearch(evaluation_config=EvaluationConfig(-4000))
        self.assertEqual(engine.score(root, 0), 10000)
        self.assertEqual(engine.score(root, 1), -10000)
        board[1][:5] = [1] * 5
        self.assertEqual(engine.score(Position(board, 0), 0), 0)

    def test_public_player_loads_and_switches_without_agent_leakage(self):
        board = [list(row) for row in Position.empty().board]
        board[9][10:13] = [1, 1, 0]
        root = Position(board, 0)
        engines = [FixedDepthSearch(candidates=candidates, clock=lambda: 0,
                                   table=TranspositionTable(128)) for _ in range(2)]
        players = [IterativePlayer(0, max_depth=3, search=engine,
                                   evaluation_config=EvaluationConfig(weight))
                   for engine, weight in zip(engines, (1, -7))]
        for index in (0, 1, 0):
            player = players[index]
            self.assertEqual(player.search.score(root, 0), (-1, 7)[index])
            move = player.take_turn(board, -1)
            reference = player.search.search(root, 3, reference=True)
            self.assertIn(move, reference.optimal_moves)
            self.assertEqual(player.last_result.score, reference.score)
            self.assertEqual(board, [list(row) for row in root.board])
        old = engines[0].cache_compatibility()
        players[0].set_evaluation_config(EvaluationConfig(-7))
        self.assertEqual(len(engines[0].table), 0)
        self.assertIsNone(engines[0].table.hint(root, old))
        players[0].take_turn(board, -1)
        fresh = FixedDepthSearch(candidates=candidates, evaluation_config=EvaluationConfig(-7))
        self.assertEqual(players[0].last_result.score, fresh.search(root, 3).score)
        self.assertEqual(players[0].diagnostics()['evaluation']['configuration_id'],
                         EvaluationConfig(-7).identity)
        self.assertEqual(engines[1].evaluator.config.material, -7)

    def test_saved_material_configuration_reproduces_phase_two(self):
        board = [list(row) for row in Position.empty().board]
        board[9][10:13] = [1, 1, 0]
        config = EvaluationConfig()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'material.json'
            config.save(path)
            loaded = EvaluationConfig.load(path)
        self.assertEqual(config.identity, loaded.identity)
        self.assertEqual(json.loads(config.canonical_json()), {
            'feature_version': 'material-v1',
            'coefficients': {'material': 1}, 'enabled_families': ['material']})
        for side in (0, 1):
            position = Position(board, side)
            evaluator = ConfiguredEvaluator(loaded)
            self.assertEqual(evaluator(position), material_evaluation(position))
            engine = FixedDepthSearch(evaluation_config=loaded)
            self.assertEqual(engine.search(position, 0).score,
                             FixedDepthSearch().search(position, 0).score)


if __name__ == '__main__':
    unittest.main()
