# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
import unittest
from copy import deepcopy
from offline.replay import replay
from offline.runner import run_game
from omok.simulator import Position
from tests.test_runner import ReturningPlayer


class ReplayTests(unittest.TestCase):
    def test_capture_game_replays_and_damaged_or_truncated_trace_is_rejected(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][5:11] = [1] * 6
        board[10][10], board[11][10] = 1, 0
        trace = run_game(ReturningPlayer(0, [(8, 10)]), ReturningPlayer(1, []),
                         initial=Position(board, 0))
        self.assertEqual(replay(trace).board, Position(trace['final']['board'], 0).board)
        for damage in ('capture', 'board', 'color', 'truncate', 'status', 'reason', 'clock'):
            broken = deepcopy(trace)
            if damage == 'capture':
                broken['moves'][0]['captured'] = []
            elif damage == 'board':
                broken['final']['board'][9][10] = 1
            elif damage == 'color':
                broken['moves'][0]['color'] = 1
            elif damage == 'truncate':
                del broken['final']
            elif damage == 'status':
                broken['status'] = 'capped'
            elif damage == 'reason':
                broken['reason'] = 'full_board'
            else:
                broken['remaining_ms'][0] = 99999
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                replay(broken)

    def test_capped_and_failed_traces_replay_without_fabricating_a_rules_result(self):
        for move, cap in (((0, 0), 1), ((19, 0), 10)):
            trace = run_game(ReturningPlayer(0, [move]), ReturningPlayer(1, []), move_cap=cap)
            self.assertEqual(replay(trace).outcome, 'ongoing')
            self.assertIsNone(trace['winner'])

    def test_malformed_boolean_integers_are_rejected_in_final_state_and_captures(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][5:11] = [1] * 6
        board[10][10], board[11][10] = 1, 0
        trace = run_game(ReturningPlayer(0, [(8, 10)]), ReturningPlayer(1, []),
                         initial=Position(board, 0))
        for damage in ('cell', 'winner', 'capture'):
            broken = deepcopy(trace)
            if damage == 'cell':
                broken['final']['board'][8][10] = False
            elif damage == 'winner':
                broken['winner'] = True
            else:
                broken['moves'][0]['captured'][0]['prior_value'] = True
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                replay(broken)


if __name__ == '__main__':
    unittest.main()
