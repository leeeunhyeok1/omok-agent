# AI-written by OpenAI Codex, for issue #25.
import unittest
import os
import subprocess
import sys
import time
from unittest.mock import patch

from offline.supervised import PlayerSpec, Supervision, run_supervised_game
from offline.replay import replay
from omok.simulator import Position


class StatefulPlayer:
    def __init__(self, color):
        self.color = color
        self.turn = 0
        self.times = []

    def take_turn(self, board, time):
        self.times.append(time)
        move = (self.color, self.turn)
        self.turn += 1
        return move

    def diagnostics(self):
        return {"times": self.times[:]}


class BrokenPlayer:
    def __init__(self, color, behavior):
        self.color, self.behavior = color, behavior
        if behavior == 'constructor_loop':
            while True:
                pass
        if behavior == 'constructor_raise':
            raise ImportError('missing controlled dependency')

    def take_turn(self, board, time):
        if self.behavior == 'loop':
            while True:
                pass
        if self.behavior == 'sleep':
            time_module.sleep(60)
        if self.behavior == 'raise':
            raise RuntimeError('controlled player exception')
        if self.behavior == 'exit':
            os._exit(7)
        if self.behavior == 'mutate':
            board[5][5] = self.color
        if self.behavior == 'malformed':
            return [True, 0]
        if self.behavior == 'occupied':
            return (0, 0)
        if self.behavior == 'flood':
            for _ in range(128):
                os.write(1, b'o' * 4096)
                os.write(2, b'e' * 4096)
        return (9, 9)


time_module = time


class SupervisedTests(unittest.TestCase):
    def test_workers_preserve_turn_state_but_each_game_starts_fresh(self):
        specs = [PlayerSpec('tests.test_supervised', 'StatefulPlayer') for _ in range(2)]
        for _ in range(2):
            trace = run_supervised_game(*specs, move_cap=3)
            self.assertEqual(trace['status'], 'capped')
            self.assertEqual([m['move'] for m in trace['moves']], [[0, 0], [1, 0], [0, 1]])
            self.assertTrue(all(w['reaped'] for w in trace['workers']))
            self.assertEqual(replay(trace).board, Position(trace['final']['board'], 1).board)

    def test_nonreturning_player_is_bounded_and_next_game_runs(self):
        policy = Supervision(startup_ms=1000, cleanup_ms=200, unlimited_call_ms=40)
        for behavior, budgets, status, reason in (
                ('loop', (40, 100), 'failed', 'timeout'),
                ('sleep', (40, 100), 'failed', 'timeout'),
                ('loop', (None, None), 'capped', 'unlimited_call_cap')):
            started = time.monotonic()
            trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': behavior}),
                PlayerSpec('tests.test_supervised', 'StatefulPlayer'), budgets_ms=budgets, supervision=policy)
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual((trace['status'], trace['reason']), (status, reason))
            self.assertEqual(trace['moves'], [])
            self.assertTrue(all(w['reaped'] for w in trace['workers']))
            replay(trace)
        fresh = run_supervised_game(PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), move_cap=2)
        self.assertEqual(len(fresh['moves']), 2)

    def test_broken_players_have_distinct_failures_and_never_change_valid_state(self):
        for behavior, reason in (('raise', 'exception'), ('exit', 'player_exit'),
                ('mutate', 'mutation'), ('malformed', 'invalid_move'), ('occupied', 'invalid_move')):
            root = Position.empty().play((0, 0)).position
            trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
                PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': behavior}), initial=root)
            with self.subTest(behavior=behavior):
                self.assertEqual(trace['reason'], reason)
                self.assertEqual(trace['failure']['color'], 1)
                self.assertEqual(trace['final']['board'], [list(r) for r in root.board])
                self.assertEqual(trace['moves'], [])
                self.assertTrue(all(w['reaped'] for w in trace['workers']))
                replay(trace)

    def test_native_output_is_separate_bounded_and_cannot_corrupt_protocol(self):
        trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'flood'}),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), move_cap=1,
            supervision=Supervision(output_bytes=1024))
        self.assertEqual(trace['status'], 'capped')
        worker = trace['workers'][0]
        self.assertTrue(worker['output_drained'])
        for stream, character in (('stdout', 'o'), ('stderr', 'e')):
            self.assertEqual(worker[stream]['text'], character * 1024)
            self.assertEqual(worker[stream]['bytes_seen'], 524288)
            self.assertTrue(worker[stream]['truncated'])
        replay(trace)

    def test_setup_failures_are_bounded_and_not_game_losses(self):
        for spec, reason in ((PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'constructor_loop'}),
                               'startup_timeout'),
                (PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'constructor_raise'}), 'player_setup'),
                (PlayerSpec('nonexistent_issue25_module', 'Player'), 'player_setup')):
            trace = run_supervised_game(spec, PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
                # Allow normal process/import startup before classifying setup defects.
                supervision=Supervision(startup_ms=1000, cleanup_ms=100))
            self.assertEqual((trace['status'], trace['reason']), ('setup_failed', reason))
            self.assertEqual(trace['remaining_ms'], [60000, 60000])
            self.assertTrue(all(w['reaped'] for w in trace['workers']))
            replay(trace)

    def test_zero_clock_does_not_invoke_player_and_terminal_games_do_not_start_workers(self):
        trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'raise'}),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), budgets_ms=(0, 100))
        self.assertFalse(trace['failure']['called'])
        replay(trace)
        board = [[-1] * 19 for _ in range(19)]
        board[0][:5] = [0] * 5
        trace = run_supervised_game(PlayerSpec('missing', 'Player'), PlayerSpec('missing', 'Player'),
            initial=Position(board, 1))
        self.assertEqual((trace['status'], trace['winner']), ('completed', 0))
        self.assertTrue(all(w['pid'] is None for w in trace['workers']))
        replay(trace)

    def test_controlled_envelope_debits_only_active_clock_and_passes_floor(self):
        ticks = iter([0, .0012, 1, 1.002, 2, 2.003])
        trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), budgets_ms=(10, 20), move_cap=3,
            diagnostics=True, clock=lambda: next(ticks))
        self.assertEqual(trace['status'], 'capped')
        self.assertAlmostEqual(trace['remaining_ms'][0], 5.8)
        self.assertAlmostEqual(trace['remaining_ms'][1], 18)
        returned = [e for e in trace['events'] if e['type'] == 'returned']
        self.assertEqual([e['search']['times'] for e in returned], [[10], [20], [10, 8]])
        replay(trace)

    def test_late_reply_is_rejected_even_when_move_is_legal(self):
        ticks = iter([0, .011])
        trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), budgets_ms=(10, 20),
            clock=lambda: next(ticks))
        self.assertEqual(trace['reason'], 'timeout')
        self.assertEqual(trace['moves'], [])
        self.assertEqual(trace['remaining_ms'], [0, 20])
        replay(trace)

    def test_capture_induced_opponent_and_simultaneous_outcomes_are_preserved(self):
        for simultaneous in (False, True):
            board = [[-1] * 19 for _ in range(19)]
            board[9][5:11] = [1] * 6
            board[10][10], board[11][10] = 1, 0
            if simultaneous:
                board[8][6:10] = [0] * 4
            trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'FixedMovePlayer', {'move': [8, 10]}),
                PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'raise'}), initial=Position(board, 0))
            self.assertEqual(trace['status'], 'completed')
            self.assertEqual(trace['final']['outcome'], 'draw' if simultaneous else 'white_win')
            self.assertEqual([c['cell'] for c in trace['moves'][0]['captured']], [[9, 10], [10, 10]])
            replay(trace)

    def test_precise_exhaustion_exact_limit_and_fractional_argument(self):
        ticks = iter([0, .002, 1, 1.001])
        trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), budgets_ms=(2, 10), clock=lambda: next(ticks))
        self.assertEqual(len(trace['moves']), 2)
        self.assertFalse(trace['failure']['called'])
        replay(trace)
        ticks = iter([0, .0001])
        trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), budgets_ms=(.9, 10), move_cap=1,
            diagnostics=True, clock=lambda: next(ticks))
        self.assertEqual(trace['events'][0]['search']['times'], [0])
        self.assertAlmostEqual(trace['remaining_ms'][0], .8)
        replay(trace)

    def test_supervisor_resource_error_is_distinct_from_player_failure(self):
        with patch('subprocess.Popen', side_effect=OSError('controlled resource failure')):
            trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
                PlayerSpec('tests.test_supervised', 'StatefulPlayer'))
        self.assertEqual(trace['status'], 'supervisor_error')
        self.assertIsNone(trace['failure']['color'])
        replay(trace)

    def test_late_exception_preserves_diagnostics_and_replays_as_timeout(self):
        ticks = iter([0, .011])
        trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'raise'}),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), budgets_ms=(10, 20),
            clock=lambda: next(ticks))
        self.assertEqual(trace['reason'], 'timeout')
        self.assertEqual(trace['failure']['exception']['type'], 'RuntimeError')
        replay(trace)

    def test_cleanup_error_preserves_prior_game_failure_and_replay(self):
        original_wait = subprocess.Popen.wait
        calls = [0]
        def wait_then_fail(process, *args, **kwargs):
            result = original_wait(process, *args, **kwargs)
            calls[0] += 1
            if calls[0] == 1:
                raise OSError('controlled cleanup observation error')
            return result
        with patch.object(subprocess.Popen, 'wait', wait_then_fail):
            trace = run_supervised_game(
                PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'raise'}),
                PlayerSpec('tests.test_supervised', 'StatefulPlayer'))
        self.assertEqual((trace['status'], trace['reason']), ('supervisor_error', 'cleanup_error'))
        self.assertEqual(trace['prior_result']['failure']['reason'], 'exception')
        self.assertTrue(all(w['reaped'] for w in trace['workers']))
        replay(trace)


class FixedMovePlayer:
    def __init__(self, color, move):
        self.color, self.move = color, move

    def take_turn(self, board, time):
        return self.move


if __name__ == '__main__':
    unittest.main()
