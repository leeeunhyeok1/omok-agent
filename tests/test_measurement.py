# AI-written by OpenAI Codex, for issue #21.
import unittest
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from offline.replay import load_trace, replay

from omok.evaluation import EvaluationConfig
from omok.player import IterativePlayer
from omok.search import FixedDepthSearch, SearchCancelled, SearchLimits
from omok.simulator import Position
from omok.transposition import TranspositionTable


def candidates(position):
    return [move for move in ((9, 9), (9, 10), (10, 9))
            if position.board[move[0]][move[1]] == -1]


class MeasurementTests(unittest.TestCase):
    def test_public_diagnostics_distinguish_calls_from_cached_leaf_values(self):
        engine = FixedDepthSearch(candidates=candidates, clock=lambda: 0,
                                  evaluation_config=EvaluationConfig(), table=TranspositionTable())
        player = IterativePlayer(0, max_depth=1, search=engine)
        board = [list(row) for row in Position.empty().board]
        player.take_turn(board, -1)
        cold = player.diagnostics()
        self.assertEqual((cold['evaluation_calls'], cold['evaluation_completed'],
                          cold['evaluation_cancelled'], cold['evaluation_cache_hits']), (3, 3, 0, 0))
        player.take_turn(board, -1)
        warm = player.diagnostics()
        self.assertEqual((warm['evaluation_calls'], warm['evaluation_completed'],
                          warm['evaluation_cache_hits']), (0, 0, 3))
        self.assertEqual(cold['score'], warm['score'])
        player.take_turn(board, 0)
        self.assertEqual(player.diagnostics()['evaluation_calls'], 0)
        self.assertEqual(board, [list(row) for row in Position.empty().board])

    def test_sampling_preserves_completed_scores_and_counts_cancelled_work(self):
        plain = FixedDepthSearch(candidates=candidates, evaluation_config=EvaluationConfig())
        measured = FixedDepthSearch(candidates=candidates, evaluation_config=EvaluationConfig(),
                                    profile_every=2)
        root = Position.empty()
        expected = plain.search(root, 2, reference=True)
        result = measured.search(root, 2, reference=True)
        self.assertEqual((result.move, result.score, result.nodes),
                         (expected.move, expected.score, expected.nodes))
        profile = result.evaluation_profile
        self.assertEqual(profile['sampled_calls'], 3)
        self.assertEqual(profile['families']['material']['completed'], 3)
        self.assertGreaterEqual(profile['instrumentation_bookkeeping_ns'], 0)
        self.assertIsNone(expected.evaluation_profile)
        calls = [0]
        def evaluator(position, check):
            calls[0] += 1
            raise SearchCancelled('inside evaluator')
        measured.cooperative_evaluator = evaluator
        cancelled = measured.search(root, 0)
        self.assertEqual((cancelled.evaluation_calls, cancelled.evaluation_completed,
                          cancelled.evaluation_cancelled), (1, 0, 1))
        self.assertEqual(cancelled.cancellation, 'inside evaluator')
        self.assertIsNone(cancelled.score)
        self.assertEqual(root, Position.empty())
        def broken(position, check):
            raise RuntimeError('evaluator failed')
        measured.cooperative_evaluator = broken
        with self.assertRaisesRegex(RuntimeError, 'evaluator failed'):
            measured.search(root, 0)

    def test_terminal_scoring_bypasses_evaluator_and_sampled_shared_costs_are_explicit(self):
        board = [list(row) for row in Position.empty().board]
        board[0][:5] = [0] * 5
        engine = FixedDepthSearch(evaluation_config=EvaluationConfig(feature_version='potential-v1'),
                                  profile_every=1)
        terminal = engine.search(Position(board, 0), 2)
        self.assertEqual((terminal.score, terminal.evaluation_calls), (10000, 0))
        result = engine.search(Position.empty(), 0)
        self.assertIn('lines+potential', result.evaluation_profile['families'])
        self.assertNotIn('lines', result.evaluation_profile['families'])
        self.assertNotIn('potential', result.evaluation_profile['families'])

    def test_cli_reloads_configuration_records_conditions_and_replays_both_colors(self):
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / 'config.json'
            EvaluationConfig(material=2).save(config_path)
            for color in ('black', 'white'):
                path = Path(directory) / (color + '.json')
                result = subprocess.run([sys.executable, '-m', 'offline', '--engine', 'search',
                    '--evaluation-config', str(config_path), '--profile-every', '2',
                    '--max-depth', '1', '--max-nodes', '100', '--candidate-cap', '2',
                    '--opponent', 'smoke', '--agent-color', color, '--diagnostics',
                    '--move-cap', '4', '--output', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                trace = load_trace(path)
                replay(trace)
                config = trace['config']
                self.assertEqual(config['evaluation']['configuration_id'], EvaluationConfig(2).identity)
                self.assertEqual(config['conditions']['workers'], 1)
                self.assertIn('cpu_count', config['conditions'])
                self.assertIn('engine_source_sha256', config)
                reports = [event['search'] for event in trace['events'] if 'search' in event]
                self.assertEqual(len(reports), 2)
                self.assertLess(reports[1]['remaining_ms'], reports[0]['remaining_ms'])
                self.assertEqual(reports[0]['config']['max_depth'], 1)
                self.assertEqual(reports[0]['evaluation_profile']['every'], 2)

    def test_comparison_cli_freezes_identical_trees_and_labels_node_budget_results(self):
        with TemporaryDirectory() as directory:
            paths = [Path(directory) / (str(weight) + '.json') for weight in (1, -1)]
            for weight, path in zip((1, -1), paths):
                EvaluationConfig(weight).save(path)
            output = Path(directory) / 'comparison.json'
            for route in ('fixed-depth', 'node-budget'):
                result = subprocess.run([sys.executable, '-m', 'offline.compare',
                    '--configs', *map(str, paths), '--route', route, '--fixture', 'empty',
                    '--depth', '1', '--cap', '2', '--nodes', '1', '--profile-every', '1',
                    '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(output.read_text())
                self.assertEqual(report['route'], route)
                self.assertEqual(len(report['runs']), 2)
                self.assertIn('candidate_tree', report)
                for run in report['runs']:
                    self.assertIn('paired_overhead', run)
                    self.assertEqual(run['plain']['score'], run['sampled']['score'])
                if route == 'fixed-depth':
                    self.assertEqual([run['plain']['nodes'] for run in report['runs']], [2, 2])
                    self.assertEqual([run['plain']['score'] for run in report['runs']], [1, -1])
                else:
                    self.assertEqual([run['plain']['cancellation'] for run in report['runs']],
                                     ['node_limit', 'node_limit'])

    def test_game_batch_rejects_changed_configuration_or_opponent_identity_on_resume(self):
        evidence = Path('docs/verification/issue-22')
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'gate.json').write_text((evidence / 'gate.json').read_text())
            report = json.loads((evidence / 'integration.json').read_text())
            report['batch_identity'] = {'configurations': 'changed', 'opponents': 'changed'}
            (output / 'integration.json').write_text(json.dumps(report))
            result = subprocess.run([sys.executable, '-m', 'verification.evaluation_acceptance',
                                    'integration', '--output-dir', str(output)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Batch identity changed', result.stderr)

    def test_complete_evaluator_agrees_on_cached_uncached_and_reference_trees(self):
        from offline.compare import compare
        report = compare([EvaluationConfig.load('configs/effects-v1.json')],
                         Position.empty(), route='fixed-depth', depth=2, cap=2)
        run = report['runs'][0]
        for name in ('alpha_beta', 'cached_cold', 'cached_warm'):
            self.assertTrue(run[name]['completed'])
            self.assertEqual(run[name]['score'], run['plain']['score'])
            self.assertEqual(run[name]['move'], run['plain']['move'])
        self.assertGreater(run['cached_warm']['table_hits'], 0)

    def test_cancellation_during_sampled_material_scan_keeps_partial_cost_explicit(self):
        checks = [0]
        def cancel():
            checks[0] += 1
            return checks[0] == 10
        engine = FixedDepthSearch(evaluation_config=EvaluationConfig(),
                                  profile_every=1, table=TranspositionTable())
        result = engine.search(Position.empty(), 0, limits=SearchLimits(cancelled=cancel))
        self.assertEqual((result.evaluation_calls, result.evaluation_completed,
                          result.evaluation_cancelled), (1, 0, 1))
        self.assertEqual(result.evaluation_profile['families']['material']['incomplete'], 1)
        self.assertEqual(result.evaluation_profile['families']['evaluator_total']['incomplete'], 1)
        self.assertEqual(len(engine.table), 0)
        self.assertIsNone(result.score)

    def test_supplied_player_constructor_preserves_config_profiling_and_public_inheritance(self):
        from offline.provided import load_players
        supplied = load_players()
        for color in (0, 1):
            engine = FixedDepthSearch(candidates=candidates, clock=lambda: 0,
                                      evaluation_config=EvaluationConfig(2), profile_every=1)
            player = supplied.create('search', color, max_depth=1, max_nodes=20, search=engine)
            self.assertIsInstance(player, supplied.base)
            board = [list(row) for row in Position.empty().board]
            move = player.take_turn(board, -1)
            self.assertIn(move, candidates(Position.empty()))
            report = player.diagnostics()
            self.assertEqual(report['evaluation']['configuration_id'], EvaluationConfig(2).identity)
            self.assertEqual(report['evaluation_profile']['sampled_calls'], 3)
            self.assertEqual(report['config']['max_depth'], 1)
            self.assertEqual(board, [list(row) for row in Position.empty().board])


if __name__ == '__main__':
    unittest.main()
