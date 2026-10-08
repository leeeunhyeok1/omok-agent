# AI-written by OpenAI Codex, for issues #4 and #5.
import unittest
from copy import deepcopy
from time import monotonic
from unittest.mock import patch

from omok.player import LegalBaseline
from omok.simulator import Position, Transition


class PlayerTests(unittest.TestCase):
    def test_evaluation_exception_after_capture_preserves_parent_and_later_choices(self):
        # Diagnostic fault injection; assertions stay at take_turn/Position seams.
        class FailingEvaluation(LegalBaseline):
            failed_child: Position | None = None

            def _score(self, transition: Transition) -> int:
                if transition.captured and self.failed_child is None:
                    self.failed_child = transition.position
                    raise RuntimeError('injected evaluation failure after capture')
                return super()._score(transition)

        board = [[-1] * 19 for _ in range(19)]
        board[9][10:13] = [1, 1, 0]
        parent = Position(board, 0)
        before = deepcopy(board)
        player = FailingEvaluation(0)
        with patch('omok.player.monotonic', return_value=0):
            interrupted = player.take_turn(parent.board, 60000)
            recovered = player.take_turn(parent.board, 60000)
        self.assertIsNotNone(player.failed_child)
        assert player.failed_child is not None
        self.assertEqual(player.failed_child.board[9][9:13], (0, -1, -1, 0))
        self.assertEqual(parent, Position(before, 0))
        self.assertEqual(board, before)
        self.assertEqual(parent.play(interrupted).position.outcome, 'ongoing')
        self.assertEqual(recovered, (9, 9))

    def test_unique_strict_wins_in_all_orientations_for_both_colors(self):
        for color in (0, 1):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                board = [[-1] * 19 for _ in range(19)]
                board[6 - dr][9 - dc] = 1 - color
                for step in range(4):
                    board[6 + step * dr][9 + step * dc] = color
                before = deepcopy(board)
                with patch('omok.player.monotonic', return_value=0):
                    move = LegalBaseline(color).take_turn(board, 60000)
                self.assertEqual(move, (6 + 4 * dr, 9 + 4 * dc))
                self.assertEqual(Position(board, color).play(move).position.outcome,
                                 'black_win' if color == 0 else 'white_win')
                self.assertEqual(board, before)

    def test_deadline_after_conversion_or_child_keeps_legal_fallback(self):
        board = [[-1] * 19 for _ in range(19)]
        capture = deepcopy(board)
        capture[8][9] = 0
        capture[9][10:13] = [1, 1, 0]
        for incoming in (board, capture):
            parent = Position(incoming, 0)
            before = deepcopy(incoming)
            for ticks, expected in (([0, .2], (0, 0)),
                                    ([0, 0, 0, .2, .2], (9, 9))):
                player = LegalBaseline(0)
                with patch('omok.player.monotonic', side_effect=ticks):
                    move = player.take_turn(parent.board, 60000)
                self.assertEqual(move, expected)
                self.assertEqual(incoming, before)
                self.assertEqual(parent, Position(before, 0))
                parent.play(move)

    def test_modest_capture_score_can_outweigh_locality_for_both_colors(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[9][10:13] = [1 - color, 1 - color, color]
            board[4][4:6] = [color, color]
            before = deepcopy(board)
            with patch('omok.player.monotonic', return_value=0):
                move = LegalBaseline(color).take_turn(board, 60000)
            self.assertEqual(move, (9, 9))
            self.assertEqual(board, before)

    def test_returns_legal_without_mutating_live_fixtures_at_each_time_mode(self):
        empty = [[-1] * 19 for _ in range(19)]
        sparse = deepcopy(empty)
        sparse[9][9] = 1
        capture = deepcopy(empty)
        capture[9][10:13] = [1, 1, 0]
        dense = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
        dense[0][0] = -1
        for color in (0, 1):
            for board in (empty, sparse, capture, dense):
                for time in (0.001, 60000, -1):
                    with self.subTest(color=color, board=board, time=time):
                        before = deepcopy(board)
                        start = monotonic()
                        move = LegalBaseline(color).take_turn(board, time)
                        self.assertLess(monotonic() - start, 0.1 if time == 0.001 else 1.0)
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
