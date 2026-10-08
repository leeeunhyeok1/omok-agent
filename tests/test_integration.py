# AI-written by OpenAI Codex, for issue #14.
import json
import unittest
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from offline.replay import replay
from offline.runner import run_game
from omok.player import IterativePlayer, LegalBaseline
from omok.search import FixedDepthSearch
from omok.tactics import TacticalPolicy
from omok.transposition import TranspositionTable
from verification.reference import ReferencePosition


class IntegrationTests(unittest.TestCase):
    def test_integrated_player_runs_with_isolated_engine_only_imports(self):
        result = subprocess.run([sys.executable, '-I', '-S',
            'verification/offline_engine.py', '--iterative'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['engine'], 'iterative')
        self.assertEqual([m['color'] for m in report['moves']], [0, 1])
        self.assertTrue(report['isolated'])
        self.assertTrue(report['no_site'])

    def test_optional_diagnostics_preserve_moves_clocks_and_replay(self):
        def play(record):
            ticks = iter([0, .001, 1, 1.002, 2, 2.003])
            players = [IterativePlayer(c, max_depth=1, search=FixedDepthSearch(
                tactics=TacticalPolicy(cap=1), table=TranspositionTable(), clock=lambda: 0))
                for c in (0, 1)]
            return run_game(*players, move_cap=3, budgets_ms=(100, 200),
                            clock=lambda: next(ticks),
                            diagnostics=(lambda p: p.diagnostics()) if record else None)
        plain, recorded = play(False), play(True)
        self.assertEqual(plain['moves'], recorded['moves'])
        self.assertEqual(plain['remaining_ms'], recorded['remaining_ms'])
        self.assertNotIn('search', plain['events'][0])
        replay(json.loads(json.dumps(recorded)))
        root = ReferencePosition.empty()
        for event in recorded['events']:
            if event['type'] == 'returned':
                report = event['search']
                self.assertEqual(report['move'], event['move'])
                self.assertEqual(report['completed_depth'], 1)
                self.assertEqual(report['root_candidate_count'], 1)
                self.assertTrue(report['tactics']['complete'])
                leaf = root
                for move in report['principal_variation']:
                    leaf = leaf.play(move).position
                self.assertEqual(report['pv_status'], 'complete')
            elif event['type'] == 'applied':
                root = root.play(event['move']).position
        self.assertEqual(recorded['events'][4]['search']['remaining_ms'], 99)

    def test_table_counters_are_per_call_and_report_reused_values(self):
        engine = FixedDepthSearch(tactics=TacticalPolicy(cap=1),
                                  table=TranspositionTable(), clock=lambda: 0)
        player = IterativePlayer(0, max_depth=1, search=engine)
        board = [[-1] * 19 for _ in range(19)]
        player.take_turn(board, -1)
        cold = player.diagnostics()
        player.take_turn(board, -1)
        warm = player.diagnostics()
        self.assertEqual((cold['nodes'], cold['table_probes'], cold['table_hits'],
                          cold['table_value_cutoffs']), (2, 1, 0, 0))
        self.assertEqual((warm['nodes'], warm['table_probes'], warm['table_hits'],
                          warm['table_value_cutoffs']), (2, 1, 1, 1))
        self.assertEqual(cold['score'], warm['score'])
        player.take_turn(board, 0)
        low = player.diagnostics()
        self.assertEqual(low['table_probes'], 0)
        self.assertEqual(low['fallback_reason'], 'low_time')
        self.assertIsNone(low['tactics'])
        self.assertEqual(low['pv_status'], 'unavailable')

    def test_supplied_search_adapter_has_explicit_color_and_legal_turn(self):
        from offline.provided import load_players
        supplied = load_players()
        for color in (0, 1):
            player = supplied.create('search', color)
            self.assertIsInstance(player, supplied.base)
            self.assertEqual(player.color, color)
            board = [[-1] * 19 for _ in range(19)]
            before = [row[:] for row in board]
            self.assertEqual(player.take_turn(board, 0), (0, 0))
            self.assertEqual(board, before)
            self.assertEqual(player.diagnostics()['remaining_ms'], 0)

    def test_cli_selects_search_both_colors_against_retained_baseline(self):
        from offline.replay import load_trace
        with TemporaryDirectory() as directory:
            for color in ('black', 'white'):
                path = Path(directory) / (color + '.json')
                result = subprocess.run([sys.executable, '-m', 'offline', '--engine', 'search',
                    '--opponent', 'baseline', '--agent-color', color, '--diagnostics',
                    '--move-cap', '4', '--output', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                trace = load_trace(path)
                replay(trace)
                self.assertEqual(trace['config']['engine'], 'search')
                self.assertEqual(trace['config']['agent_color'], 0 if color == 'black' else 1)
                reports = [e['search'] for e in trace['events'] if 'search' in e]
                self.assertEqual(len(reports), 2)
                self.assertLess(reports[1]['remaining_ms'], reports[0]['remaining_ms'])

    def test_combined_player_retains_mandatory_wins_and_capture_defenses(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[0][:4] = [color] * 4
            player = IterativePlayer(color, max_depth=1, search=FixedDepthSearch(
                tactics=TacticalPolicy(cap=1, ordinary_rank=lambda p, m, check: -m[1]),
                table=TranspositionTable(), clock=lambda: 0))
            self.assertEqual(player.take_turn(board, -1), (0, 4))
            self.assertEqual(player.diagnostics()['score'], 10000)
            board = [[-1] * 19 for _ in range(19)]
            for row, col in ((9, 6), (9, 7), (9, 8), (9, 9), (8, 7)):
                board[row][col] = 1 - color
            board[10][7] = color
            player = IterativePlayer(color, max_depth=1, search=FixedDepthSearch(
                tactics=TacticalPolicy(cap=1, ordinary_rank=lambda p, m, check: -10000 if m == (7, 7) else 0),
                table=TranspositionTable(), clock=lambda: 0))
            before = [row[:] for row in board]
            move = player.take_turn(board, -1)
            self.assertIn((7, 7), player.last_result.tactics.candidates)
            self.assertIn(move, player.last_result.tactics.defenses)
            child = ReferencePosition(board, color).play(move).position
            from omok.search import legal_moves
            enemy_win = 'white_win' if color == 0 else 'black_win'
            self.assertFalse(any(child.play(m).position.outcome == enemy_win for m in legal_moves(child)))
            self.assertEqual(board, before)

    def test_combined_cached_uncached_and_unpruned_trees_and_every_node_interrupt(self):
        from omok.simulator import Position
        board = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
        for r, c in ((0, 0), (0, 1), (1, 0)):
            board[r][c] = -1
        for color in (0, 1):
            root = Position(board, color)
            policy = TacticalPolicy(full_width=True, cap=1)
            engine = FixedDepthSearch(tactics=policy, table=TranspositionTable(), clock=lambda: 0)
            for depth in (1, 2, 3):
                reference = engine.search(root, depth, reference=True)
                clean = FixedDepthSearch(tactics=policy).search(root, depth)
                for result in (clean, engine.search(root, depth), engine.search(root, depth)):
                    self.assertEqual(result.score, reference.score)
                    self.assertIn(result.move, reference.optimal_moves)
                    leaf = ReferencePosition(board, color)
                    for move in result.principal_variation:
                        leaf = leaf.play(move).position
                    self.assertTrue(len(result.principal_variation) == depth or leaf.outcome != 'ongoing')
            complete = engine.iterative(root, 3)
            for limit in range(complete.nodes):
                interrupted = IterativePlayer(color, max_depth=3, max_nodes=limit,
                    search=FixedDepthSearch(tactics=policy, table=TranspositionTable(), clock=lambda: 0))
                before = [row[:] for row in board]
                root.play(interrupted.take_turn(board, -1))
                self.assertEqual(board, before)
                result = interrupted.last_result
                self.assertEqual(result.cancellation, 'node_limit')
                if result.completed_depth:
                    reference = engine.search(root, result.completed_depth, reference=True)
                    self.assertEqual(result.score, reference.score)
                    self.assertIn(result.move, reference.optimal_moves)
                else:
                    self.assertIsNone(result.score)
                interrupted.max_nodes = 10000
                interrupted.take_turn(board, -1)
                self.assertEqual(interrupted.last_result.score, complete.score)

    def test_diagnostics_errors_and_execution_failures_leave_authoritative_trace(self):
        from tests.test_runner import ReturningPlayer
        class FailingPlayer:
            color = 0
            def take_turn(self, board, time):
                if behavior == 'exception':
                    raise RuntimeError('controlled')
                if behavior == 'mutation':
                    board[0][0] = 0
                return (19, 0) if behavior == 'invalid_move' else (0, 0)
        for behavior in ('exception', 'mutation', 'invalid_move', 'timeout'):
            ticks = iter([0, .020 if behavior == 'timeout' else .001])
            trace = run_game(FailingPlayer(), ReturningPlayer(1, []), budgets_ms=(10, 20),
                clock=lambda: next(ticks), diagnostics=lambda p: {'bad': float('inf')})
            self.assertEqual(trace['failure']['reason'], behavior)
            self.assertEqual(trace['events'][0]['diagnostics_error'], 'ValueError')
            self.assertEqual(trace['moves'], [])
            replay(trace)

    def test_combined_public_deadline_interrupts_tactics_and_retains_commit(self):
        from omok.simulator import Position
        root = Position.empty().play((9, 9)).position
        board = [list(row) for row in root.board]
        calls = [0]
        def measure():
            calls[0] += 1
            return 0
        def player(clock, depth):
            return IterativePlayer(1, max_depth=depth, search=FixedDepthSearch(
                tactics=TacticalPolicy(cap=1), table=TranspositionTable(), clock=clock))
        completed = player(measure, 1)
        completed.take_turn(board, -1)
        stop_after_commit = calls[0] + 10
        for stop in (3, 100, stop_after_commit):
            calls[0] = 0
            def expires():
                calls[0] += 1
                return 1 if calls[0] >= stop else 0
            interrupted = player(expires, 3)
            root.play(interrupted.take_turn(board, -1))
            self.assertEqual(board, [list(row) for row in root.board])
            report = interrupted.diagnostics()
            self.assertEqual(report['cancellation'], 'deadline')
            if stop == stop_after_commit:
                self.assertEqual((report['move'], report['score'], report['completed_depth'],
                                  report['principal_variation']),
                                 (completed.diagnostics()['move'], completed.last_result.score, 1,
                                  completed.diagnostics()['principal_variation']))
            else:
                self.assertEqual(report['completed_depth'], 0)
                self.assertIsNone(report['score'])
            interrupted.search.clock = lambda: 0
            interrupted.take_turn(board, -1)
            self.assertGreater(interrupted.last_result.completed_depth, 0)

    def test_verification_reports_zero_move_resource_caps(self):
        with TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-m', 'verification.integration',
                '--move-cap', '0', '--output-dir', directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(len(summary['games']), 6)
            for game in summary['games']:
                self.assertEqual((game['status'], game['moves'], game['verified_complete_pvs']),
                                 ('capped', 0, 0))
                self.assertEqual(game['max_public_elapsed_ms'], 0)


if __name__ == '__main__':
    unittest.main()
