# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #3.
import unittest

from omok.simulator import Position


def empty_board():
    return [[-1] * 19 for _ in range(19)]


class PositionTests(unittest.TestCase):
    position_type = Position

    def test_empty_position_places_at_row_column_without_mutating_parent(self):
        parent = self.position_type.empty()
        transition = parent.play((1, 0))
        self.assertEqual(transition.position.board[1][0], 0)
        self.assertEqual(transition.position.board[0][1], -1)
        self.assertEqual(parent.board[1][0], -1)
        self.assertEqual(transition.position.side_to_move, 1)
        self.assertEqual(transition.position.outcome, 'ongoing')
        self.assertIsNone(transition.position.reason)
        self.assertEqual(transition.captured, ())
        self.assertEqual((transition.move, transition.color), ((1, 0), 0))

    def test_load_owns_input_and_accepts_explicit_color_without_count_parity(self):
        board = empty_board()
        board[0][0] = 1
        parent = self.position_type(board, side_to_move=1)
        board[0][0] = 0
        board[1][0] = 0
        self.assertEqual(parent.board[0][0], 1)
        self.assertEqual(parent.board[1][0], -1)
        self.assertEqual(parent.side_to_move, 1)
        with self.assertRaises(TypeError):
            parent.board[0][0] = 0

    def test_rejects_malformed_boards_and_colors(self):
        invalid_boards = [[], [[-1] * 19] * 18, [[-1] * 18] * 19,
                          [[-1] * 20] * 19, None]
        for value in (2, -2, 0.0, True, '0', None):
            board = empty_board()
            board[0][0] = value
            invalid_boards.append(board)
        for board in invalid_boards:
            with self.subTest(board=board), self.assertRaises(ValueError):
                self.position_type(board, 0)
        for color in (-1, 2, True, 0.0, None):
            with self.subTest(color=color), self.assertRaises(ValueError):
                self.position_type(empty_board(), color)

    def test_illegal_moves_preserve_complete_state(self):
        parent = self.position_type.empty().play((1, 0)).position
        before = (parent.board, parent.side_to_move, parent.outcome, parent.reason)
        for move in ((-1, 0), (0, -1), (19, 0), (0, 19), (1, 0),
                     (), (1,), (1, 2, 3), (True, 0), (1.0, 0), None, '00'):
            with self.subTest(move=move), self.assertRaises(ValueError):
                parent.play(move)
            self.assertEqual((parent.board, parent.side_to_move,
                              parent.outcome, parent.reason), before)

    def test_captures_all_eight_rays_for_both_colors(self):
        for color in (0, 1):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1),
                           (0, -1), (-1, 0), (-1, -1), (-1, 1)):
                board = empty_board()
                cells = [(9 + n * dr, 9 + n * dc) for n in (1, 2, 3)]
                for row, col in cells[:2]:
                    board[row][col] = 1 - color
                board[cells[2][0]][cells[2][1]] = color
                parent = self.position_type(board, color)
                result = parent.play((9, 9))
                with self.subTest(color=color, direction=(dr, dc)):
                    self.assertEqual({item.cell for item in result.captured}, set(cells[:2]))
                    self.assertEqual({item.prior_value for item in result.captured}, {1 - color})
                    for row, col in cells[:2]:
                        self.assertEqual(result.position.board[row][col], -1)
                        self.assertEqual(parent.board[row][col], 1 - color)
                    self.assertEqual(result.position.board[cells[2][0]][cells[2][1]], color)

    def test_multiple_captures_and_reusable_vacancies(self):
        board = empty_board()
        for row, col in ((9, 10), (9, 11), (10, 9), (11, 9)):
            board[row][col] = 1
        board[9][12] = board[12][9] = 0
        result = self.position_type(board, 0).play((9, 9))
        self.assertEqual({item.cell for item in result.captured},
                         {(9, 10), (9, 11), (10, 9), (11, 9)})
        self.assertEqual(result.position.outcome, 'ongoing')
        reused = result.position.play((9, 10)).position
        self.assertEqual(reused.board[9][10], 1)

    def test_exact_five_in_each_orientation_and_color_at_edges(self):
        for color in (0, 1):
            for origin, direction in (((0, 0), (0, 1)), ((0, 0), (1, 0)),
                                      ((0, 0), (1, 1)), ((0, 18), (1, -1))):
                board = empty_board()
                row, col = origin
                dr, dc = direction
                for n in range(4):
                    board[row + n * dr][col + n * dc] = color
                parent = self.position_type(board, color)
                self.assertEqual(parent.outcome, 'ongoing')
                result = parent.play((row + 4 * dr, col + 4 * dc)).position
                self.assertEqual(result.outcome, 'black_win' if color == 0 else 'white_win')
                self.assertEqual(result.reason, 'exact_five')
                self.assertEqual(result.side_to_move, color)
                with self.assertRaises(ValueError):
                    result.play((18, 0))

    def test_static_five_overline_gap_and_separate_five(self):
        for color in (0, 1):
            for length in (5, 6, 7, 19):
                board = empty_board()
                board[0][:length] = [color] * length
                position = self.position_type(board, 1 - color)
                self.assertEqual(position.outcome,
                                 ('black_win' if color == 0 else 'white_win')
                                 if length == 5 else 'ongoing')
            board = empty_board()
            for col in (0, 1, 3, 4, 5):
                board[2][col] = color
            self.assertEqual(self.position_type(board, color).outcome, 'ongoing')
            board[0][:6] = [color] * 6
            board[5][5:10] = [color] * 5
            self.assertEqual(self.position_type(board, color).outcome,
                             'black_win' if color == 0 else 'white_win')

    def test_joining_groups_into_six_is_not_a_win(self):
        for color in (0, 1):
            board = empty_board()
            for col in (2, 3, 4, 6, 7):
                board[9][col] = color
            self.assertEqual(self.position_type(board, color).play((9, 5)).position.outcome, 'ongoing')

    def test_static_simultaneous_wins(self):
        board = empty_board()
        board[0][:5] = [0] * 5
        board[3][:5] = [1] * 5
        position = self.position_type(board, 1)
        self.assertEqual((position.outcome, position.reason), ('draw', 'simultaneous_wins'))
        self.assertEqual(position.side_to_move, 1)

    def test_capture_induced_opponent_victory_and_simultaneous_draw(self):
        for mover in (0, 1):
            for simultaneous in (False, True):
                board = empty_board()
                board[9][5:11] = [1 - mover] * 6
                board[10][10] = 1 - mover
                board[11][10] = mover
                if simultaneous:
                    board[8][6:10] = [mover] * 4
                parent = self.position_type(board, mover)
                self.assertEqual(parent.outcome, 'ongoing')
                result = parent.play((8, 10))
                self.assertEqual({item.cell for item in result.captured}, {(9, 10), (10, 10)})
                self.assertEqual(result.position.outcome, 'draw' if simultaneous else
                                 ('white_win' if mover == 0 else 'black_win'))
                self.assertEqual(result.position.reason,
                                 'simultaneous_wins' if simultaneous else 'exact_five')
                self.assertEqual(result.position.side_to_move, mover)

    def test_edge_captures_and_noncaptures(self):
        fixtures = [
            # origin, own cells, opponent cells, expected captured cells
            ((0, 0), [(0, 3)], [(0, 1), (0, 2)], {(0, 1), (0, 2)}),
            ((18, 18), [(15, 15)], [(17, 17), (16, 16)], {(17, 17), (16, 16)}),
            ((0, 0), [(16, 0)], [(18, 0), (17, 0)], set()),  # no negative wrapping
            ((17, 0), [], [(18, 0)], set()),  # ray exits board
            ((9, 9), [(9, 12)], [(9, 10)], set()),  # gap
            ((9, 9), [(9, 13)], [(9, 10), (9, 11), (9, 12)], set()),
            ((9, 9), [], [(9, 10), (9, 11)], set()),  # absent endpoint
            ((9, 7), [(9, 5), (9, 9)], [(9, 6), (9, 8)], set()),
        ]
        for color in (0, 1):
            for origin, own, opponent, expected in fixtures:
                board = empty_board()
                for row, col in own:
                    board[row][col] = color
                for row, col in opponent:
                    board[row][col] = 1 - color
                parent = self.position_type(board, color)
                self.assertEqual(parent.outcome, 'ongoing')
                result = parent.play(origin)
                with self.subTest(color=color, origin=origin, own=own):
                    self.assertEqual({item.cell for item in result.captured}, expected)
                    for row, col in opponent:
                        self.assertEqual(result.position.board[row][col],
                                         -1 if (row, col) in expected else 1 - color)

    def test_no_recursive_or_unrelated_captures(self):
        board = empty_board()
        board[9][10] = board[9][11] = 1
        board[9][12] = 0
        board[10][9] = board[13][9] = 0
        board[11][9] = board[12][9] = 1
        result = self.position_type(board, 0).play((9, 9))
        self.assertEqual({item.cell for item in result.captured}, {(9, 10), (9, 11)})
        self.assertEqual(result.position.board[11][9], 1)
        self.assertEqual(result.position.board[12][9], 1)

    def test_dense_full_draw_and_final_move_after_capture_resolution(self):
        # Modulo-four construction: see docs/simulator.md for its independent proof.
        for invert in (0, 1):
            board = [[((r + 2 * c) % 4 // 2) ^ invert for c in range(19)] for r in range(19)]
            full = self.position_type(board, invert)
            self.assertEqual((full.outcome, full.reason), ('draw', 'full_board'))
            with self.assertRaises(ValueError):
                full.play((0, 0))
            board[0][0] = -1
            for mover, expected, captured in ((invert, 'ongoing', {(1, 1), (2, 2)}),
                                              (1 - invert, 'draw', set())):
                parent = self.position_type(board, mover)
                self.assertEqual(parent.outcome, 'ongoing')
                result = parent.play((0, 0))
                self.assertEqual({item.cell for item in result.captured}, captured)
                self.assertEqual(result.position.outcome, expected)
                self.assertEqual(result.position.reason, 'full_board' if expected == 'draw' else None)

    def test_nested_children_and_consecutive_captures_leave_complete_parent_unchanged(self):
        board = empty_board()
        board[9][10] = board[9][11] = 1
        board[9][12] = 0
        board[3][4] = board[3][5] = 0
        board[3][6] = 1
        parent = self.position_type(board, 0)
        before = (parent.board, parent.side_to_move, parent.outcome, parent.reason)
        external_before = [row[:] for row in board]
        child = parent.play((9, 9)).position
        sibling = parent.play((1, 0)).position
        child_before = (child.board, child.side_to_move, child.outcome, child.reason)
        nested = child.play((3, 3))
        self.assertEqual({item.cell for item in nested.captured}, {(3, 4), (3, 5)})
        self.assertEqual({item.prior_value for item in nested.captured}, {0})
        self.assertEqual((parent.board, parent.side_to_move, parent.outcome, parent.reason), before)
        self.assertEqual((child.board, child.side_to_move, child.outcome, child.reason), child_before)
        self.assertEqual(sibling.board[9][10], 1)
        self.assertEqual(board, external_before)
        snapshot = [list(row) for row in nested.position.board]
        snapshot[3][4] = 1
        changed = self.position_type(snapshot, 0)
        self.assertEqual(changed.board[3][4], 1)
        self.assertEqual(nested.position.board[3][4], -1)
        self.assertEqual(child.board[3][4], 0)
        with self.assertRaises(ValueError):
            child.play((9, 9))
        self.assertEqual((parent.board, parent.side_to_move, parent.outcome, parent.reason), before)

    def test_index_protocol_integers_are_normalized_and_booleans_rejected(self):
        class Integer:
            def __init__(self, value):
                self.value = value

            def __index__(self):
                return self.value

        board = empty_board()
        board[0][0] = Integer(1)
        position = self.position_type(board, Integer(0))
        result = position.play((Integer(1), Integer(0)))
        self.assertEqual(result.position.board[1][0], 0)
        self.assertEqual(result.move, (1, 0))

    def test_sixteen_captured_stones_do_not_create_capture_count_victory(self):
        for color in (0, 1):
            board = empty_board()
            expected = set()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if not (dr or dc):
                        continue
                    for n in (1, 2):
                        cell = (9 + n * dr, 9 + n * dc)
                        board[cell[0]][cell[1]] = 1 - color
                        expected.add(cell)
                    board[9 + 3 * dr][9 + 3 * dc] = color
            result = self.position_type(board, color).play((9, 9))
            self.assertEqual({item.cell for item in result.captured}, expected)
            self.assertEqual(result.position.outcome, 'ongoing')


if __name__ == '__main__':
    unittest.main()
