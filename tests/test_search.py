# AI-written by OpenAI Codex, for issue #10.
import unittest
import random

from omok.search import FixedDepthSearch, SearchLimits, WIN_SCORE
from omok.simulator import Position
from omok.player import FixedDepthPlayer


class SearchTests(unittest.TestCase):
    def test_capture_removal_does_not_consume_extra_search_depth(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][10:13] = [1, 1, 0]
        root = Position(board, 0)
        engine = FixedDepthSearch(candidates=lambda p: [m for m in ((9, 9), (0, 0))
                                                       if p.board[m[0]][m[1]] == -1])
        for reference in (False, True):
            self.assertEqual(engine.search(root, 1, reference=reference).score, 2)
            self.assertEqual(engine.search(root, 2, reference=reference).score, 1)

    def test_player_selects_unique_exact_five_in_all_orientations(self):
        for color in (0, 1):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                board = [[-1] * 19 for _ in range(19)]
                board[6 - dr][9 - dc] = 1 - color
                for step in range(4):
                    board[6 + step * dr][9 + step * dc] = color
                player = FixedDepthPlayer(color, search=FixedDepthSearch(clock=lambda: 0))
                self.assertEqual(player.take_turn(board, -1), (6 + 4 * dr, 9 + 4 * dc))

    def test_matched_trees_through_depth_four_include_nonterminal_leaves_and_ties(self):
        cells = ((0, 0), (0, 1), (1, 0), (1, 1))
        for seed in range(10):
            rng = random.Random(seed)
            weights = [rng.randrange(-20, 21) for _ in cells]

            def moves(position):
                return [m for m in cells if position.board[m[0]][m[1]] == -1]

            def evaluation(position):
                return sum(w * (1 if position.board[r][c] == 0 else -1)
                           for (r, c), w in zip(cells, weights)
                           if position.board[r][c] != -1)

            engine = FixedDepthSearch(candidates=moves, evaluator=evaluation)
            for color in (0, 1):
                root = Position([[-1] * 19 for _ in range(19)], color)
                for depth in range(1, 5):
                    with self.subTest(seed=seed, color=color, depth=depth):
                        reference = engine.search(root, depth, reference=True)
                        pruned = engine.search(root, depth)
                        self.assertEqual(pruned.score, reference.score)
                        self.assertIn(pruned.move, reference.optimal_moves)

    def test_full_width_late_board_tree_matches_reference_through_depth_three(self):
        board = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
        for row, col in ((0, 0), (0, 1), (1, 0)):
            board[row][col] = -1
        engine = FixedDepthSearch()
        for side in (0, 1):
            root = Position(board, side)
            for depth in (1, 2, 3):
                reference = engine.search(root, depth, reference=True)
                pruned = engine.search(root, depth)
                self.assertEqual(pruned.score, reference.score)
                self.assertIn(pruned.move, reference.optimal_moves)

    def test_unrelated_errors_after_capture_propagate_and_leave_state_reusable(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][10:13] = [1, 1, 0]
        root = Position(board, 0)
        sibling = root.play((3, 3)).position
        captured_children = []

        def broken_evaluator(position):
            captured_children.append(position)
            raise RuntimeError('controlled evaluation defect')

        engine = FixedDepthSearch(candidates=lambda p: [(9, 9)], evaluator=broken_evaluator)
        player = FixedDepthPlayer(0, search=engine)
        for reference in (False, True):
            with self.assertRaisesRegex(RuntimeError, 'controlled evaluation defect'):
                engine.search(root, 1, reference=reference)
        with self.assertRaisesRegex(RuntimeError, 'controlled evaluation defect'):
            player.take_turn(board, -1)
        self.assertIsNone(player.last_result)
        self.assertEqual(root, Position(board, 0))
        self.assertEqual(sibling, root.play((3, 3)).position)
        self.assertEqual(captured_children[0].board[9][9:13], (0, -1, -1, 0))
        self.assertEqual(FixedDepthSearch().search(root, 1).score, 2)

    def test_cancellation_inside_candidate_generation_and_evaluation(self):
        root = Position.empty()
        for phase in ('candidates', 'evaluation'):
            ticks = [0.0]

            def candidates(position):
                if phase == 'candidates':
                    ticks[0] = 2.0
                yield (9, 9)

            def evaluation(position):
                ticks[0] = 2.0
                return 1

            engine = FixedDepthSearch(candidates=candidates, evaluator=evaluation,
                                      clock=lambda: ticks[0])
            result = engine.search(root, 1, limits=SearchLimits(deadline=1.0))
            self.assertEqual(result.cancellation, 'deadline')
            self.assertIsNone(result.score)
            self.assertFalse(result.completed)
            root.play(result.move)
            self.assertEqual(root, Position.empty())

    def test_candidate_and_configuration_errors_propagate(self):
        root = Position.empty().play((9, 9)).position
        for candidates in ([(9, 9)], [(-1, 0)], [(True, 0)], [(0.5, 0)]):
            with self.assertRaises(ValueError):
                FixedDepthSearch(candidates=lambda p: candidates).search(root, 1)
        for depth in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                FixedDepthSearch().search(root, depth)
        for nodes in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                SearchLimits(max_nodes=nodes)

    def test_player_returns_legal_moves_and_preserves_inputs_under_bounded_execution(self):
        for color in (0, 1):
            for incoming in (-1, 60000, 2, 0, -2):
                board = [[-1] * 19 for _ in range(19)]
                board[9][10:13] = [1 - color, 1 - color, color]
                root = Position(board, color)
                player = FixedDepthPlayer(color, max_nodes=0)
                move = player.take_turn(board, incoming)
                root.play(move)
                self.assertEqual(board, [list(row) for row in root.board])
                self.assertFalse(player.last_result.completed)
                self.assertIsNone(player.last_result.score)

    def test_player_uses_explicit_color_and_completed_search_move(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[9][5:9] = [color] * 4
            engine = FixedDepthSearch(clock=lambda: 0)
            player = FixedDepthPlayer(color, search=engine)
            self.assertEqual(player.take_turn(board, -1), (9, 4))
            self.assertTrue(player.last_result.completed)
            self.assertEqual(player.last_result.score, WIN_SCORE)
            board[9][9] = color
            with self.assertRaises(ValueError):
                player.take_turn(board, -1)
            self.assertIsNone(player.last_result)

    def test_every_node_cancellation_preserves_root_siblings_and_caller(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][10:13] = [1, 1, 0]
        root = Position(board, 0)
        sibling = root.play((0, 0)).position
        before = [row[:] for row in board]

        def moves(position):
            return [m for m in ((9, 9), (3, 3), (4, 4)) if position.board[m[0]][m[1]] == -1]

        engine = FixedDepthSearch(candidates=moves)
        for reference in (False, True):
            complete = engine.search(root, 3, reference=reference)
            for limit in range(complete.nodes):
                result = engine.search(root, 3, reference=reference,
                                       limits=SearchLimits(max_nodes=limit))
                self.assertFalse(result.completed)
                self.assertIsNone(result.score)
                self.assertIsNone(result.optimal_moves)
                self.assertEqual(result.cancellation, 'node_limit')
                self.assertLessEqual(result.nodes, limit)
                root.play(result.move)
                self.assertEqual(root, Position(before, 0))
                self.assertEqual(sibling, root.play((0, 0)).position)
                self.assertEqual(board, before)
            self.assertEqual(engine.search(root, 3, reference=reference), complete)

    def test_deadline_and_requested_cancellation_are_control_signals(self):
        root = Position.empty()
        engine = FixedDepthSearch(clock=lambda: 2.0)
        for limits, reason in ((SearchLimits(deadline=1.0), 'deadline'),
                               (SearchLimits(cancelled=lambda: True), 'requested')):
            result = engine.search(root, 1, limits=limits)
            self.assertFalse(result.completed)
            self.assertEqual(result.cancellation, reason)
            root.play(result.move)

    def test_capture_loss_draw_overline_and_full_draw_scores(self):
        for mover in (0, 1):
            for simultaneous in (False, True):
                board = [[-1] * 19 for _ in range(19)]
                board[9][5:11] = [1 - mover] * 6
                board[10][10], board[11][10] = 1 - mover, mover
                if simultaneous:
                    board[8][6:10] = [mover] * 4
                root = Position(board, mover)
                engine = FixedDepthSearch(candidates=lambda p: [(8, 10)])
                expected = 0 if simultaneous else -WIN_SCORE
                for reference in (False, True):
                    self.assertEqual(engine.search(root, 1, reference=reference).score, expected)
                terminal = root.play((8, 10)).position
                self.assertEqual(engine.score(terminal, mover), expected)
                self.assertEqual(engine.score(terminal, 1 - mover), -expected)

            overline = [[-1] * 19 for _ in range(19)]
            for col in (2, 3, 4, 6, 7):
                overline[9][col] = mover
            root = Position(overline, mover)
            engine = FixedDepthSearch(candidates=lambda p: [(9, 5)])
            self.assertEqual(engine.search(root, 1).score, 6)

        dense = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
        for side in (0, 1):
            engine = FixedDepthSearch()
            self.assertEqual(engine.search(Position(dense, side), 2).score, 0)
        dense[0][0] = -1
        root = Position(dense, 1)
        for reference in (False, True):
            self.assertEqual(FixedDepthSearch().search(root, 2, reference=reference).score, 0)

    def test_empty_candidates_fall_back_and_evaluation_is_bounded_zero_sum(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][9] = 0
        root = Position(board, 1)
        engine = FixedDepthSearch(candidates=lambda p: [])
        self.assertEqual((engine.score(root, 0), engine.score(root, 1)), (1, -1))
        for reference in (False, True):
            result = engine.search(root, 1, reference=reference)
            root.play(result.move)
            self.assertEqual(result.score, 0)
        for bad in (4001, -4001, float('nan'), float('inf'), True, 1.5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                FixedDepthSearch(evaluator=lambda p: bad).search(root, 0)

    def test_strict_win_beats_draw_and_overline_for_both_colors(self):
        for mover in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[9][5:11] = [1 - mover] * 6
            board[10][10], board[11][10] = 1 - mover, mover
            board[8][6:10] = [mover] * 4
            board[2][0:4] = [mover] * 4
            for col in (2, 3, 4, 6, 7):
                board[16][col] = mover
            root = Position(board, mover)
            engine = FixedDepthSearch(candidates=lambda p: [(8, 10), (16, 5), (2, 4)])
            for reference in (False, True):
                result = engine.search(root, 1, reference=reference)
                self.assertEqual((result.move, result.score), ((2, 4), WIN_SCORE))

    def test_alpha_beta_matches_worked_nonterminal_tree_and_prunes(self):
        weights = {(0, 0): 9, (0, 1): 5, (0, 2): 1}

        def moves(position):
            return [m for m in weights if position.board[m[0]][m[1]] == -1]

        def evaluation(position):
            return sum(weight * (1 if position.board[r][c] == 0 else -1)
                       for (r, c), weight in weights.items()
                       if position.board[r][c] != -1)

        engine = FixedDepthSearch(candidates=moves, evaluator=evaluation)
        for color in (0, 1):
            root = Position([[-1] * 19 for _ in range(19)], color)
            for depth, expected in ((0, 0), (1, 9), (2, 4), (3, 5)):
                reference = engine.search(root, depth, reference=True)
                pruned = engine.search(root, depth)
                self.assertEqual(reference.score, expected)
                self.assertEqual(pruned.score, expected)
                if depth:
                    self.assertIn(pruned.move, reference.optimal_moves)
                    self.assertLessEqual(pruned.nodes, reference.nodes)
            self.assertGreater(pruned.cutoffs, 0)
            self.assertLess(pruned.nodes, reference.nodes)

    def test_live_depth_counts_placements_and_terminal_child_uses_opponent_perspective(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[9][5:9] = [color] * 4
            position = Position(board, color)
            engine = FixedDepthSearch(candidates=lambda p: [(9, 9), (0, 0)])
            for reference in (False, True):
                result = engine.search(position, 1, reference=reference)
                self.assertEqual((result.move, result.score), ((9, 9), WIN_SCORE))
            self.assertEqual(position, Position(board, color))

    def test_terminal_entry_scores_both_colors_without_expanding(self):
        for winner in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[0][:5] = [winner] * 5
            for side in (0, 1):
                position = Position(board, side)
                for reference in (False, True):
                    result = FixedDepthSearch().search(position, 3, reference=reference)
                    self.assertEqual(result.score, WIN_SCORE if side == winner else -WIN_SCORE)
                    self.assertIsNone(result.move)
                    self.assertTrue(result.completed)


if __name__ == '__main__':
    unittest.main()
