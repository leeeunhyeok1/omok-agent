# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
import unittest
from copy import deepcopy
from time import monotonic

from omok.player import LegalBaseline
from omok.simulator import Position


class PlayerTests(unittest.TestCase):
    def test_low_time_returns_legal_without_mutating_live_fixtures(self):
        empty = [[-1] * 19 for _ in range(19)]
        sparse = deepcopy(empty)
        sparse[9][9] = 1
        capture = deepcopy(empty)
        capture[9][10:13] = [1, 1, 0]
        dense = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
        dense[0][0] = -1
        for color in (0, 1):
            for board in (empty, sparse, capture, dense):
                with self.subTest(color=color, board=board):
                    before = deepcopy(board)
                    start = monotonic()
                    move = LegalBaseline(color).take_turn(board, 0.001)
                    self.assertLess(monotonic() - start, 0.1)
                    Position(board, color).play(move)
                    self.assertEqual(board, before)

    def test_prefers_verified_strict_win_for_each_color(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[9][5:9] = [color] * 4
            move = LegalBaseline(color).take_turn(board, 60000)
            self.assertEqual(Position(board, color).play(move).position.outcome,
                             'black_win' if color == 0 else 'white_win')

    def test_capture_loss_is_avoided_and_simultaneous_draw_is_not_a_strict_win(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][5:11] = [1] * 6
        board[10][10], board[11][10] = 1, 0
        board[8][9], board[7][9] = 0, 0
        move = LegalBaseline(0).take_turn(board, 60000)
        self.assertNotEqual(Position(board, 0).play(move).position.outcome, 'white_win')
        board[8][6:10] = [0] * 4
        board[2][0:4] = [0] * 4
        move = LegalBaseline(0).take_turn(board, 60000)
        self.assertEqual(Position(board, 0).play(move).position.outcome, 'black_win')

    def test_terminal_input_is_rejected(self):
        board = [[-1] * 19 for _ in range(19)]
        board[0][:5] = [0] * 5
        with self.assertRaises(ValueError):
            LegalBaseline(1).take_turn(board, 60000)


if __name__ == '__main__':
    unittest.main()
