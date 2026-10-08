# AI-written by OpenAI Codex, for issue #12.
import unittest

from omok.player import IterativePlayer
from omok.search import FixedDepthSearch, WIN_SCORE, legal_moves, SearchCancelled, SearchLimits
from omok.simulator import Position
from omok.tactics import TacticalPolicy, classify, immediate_wins, checked_sorted
from verification.reference import ReferencePosition
from verification.tactics import reference_tactics, small_fixture


class TacticalTests(unittest.TestCase):
    def test_public_wins_survive_cap_and_poor_ordering_in_both_colors_and_axes(self):
        for color in (0, 1):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                board = [[-1] * 19 for _ in range(19)]
                board[6 - dr][9 - dc] = 1 - color
                for step in range(4):
                    board[6 + step * dr][9 + step * dc] = color
                win = (6 + 4 * dr, 9 + 4 * dc)
                root = Position(board, color)
                engine = FixedDepthSearch(tactics=TacticalPolicy(cap=1),
                                          ordering=lambda p, m, check: -100000 if m == win else 100000,
                                          clock=lambda: 0)
                player = IterativePlayer(color, max_depth=1, search=engine)
                self.assertEqual(player.take_turn(board, -1), win)
                self.assertEqual(player.last_result.score, WIN_SCORE)
                self.assertEqual(ReferencePosition(board, color).play(win).position.outcome,
                                 'black_win' if color == 0 else 'white_win')
                self.assertEqual(board, [list(row) for row in root.board])

    def test_capture_defense_retained_and_both_direct_blocks_refuted_independently(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            for row, col in ((9, 6), (9, 7), (9, 8), (9, 9), (8, 7)):
                board[row][col] = 1 - color
            board[10][7] = color
            root = Position(board, color)
            policy = TacticalPolicy(cap=1, ordinary_rank=lambda p, m, check: -100000 if m == (7, 7) else 0)
            report = policy.analyze(root)
            self.assertTrue(report.complete)
            self.assertEqual(report.threats, ((9, 5), (9, 10)))
            self.assertIn((7, 7), report.defenses)
            self.assertIn((7, 7), report.candidates)
            for move, reply in (((9, 5), (9, 10)), ((9, 10), (9, 5))):
                oracle = ReferencePosition(board, color).play(move).position.play(reply).position
                self.assertEqual(oracle.outcome, 'white_win' if color == 0 else 'black_win')
                self.assertNotIn(move, report.defenses)
            safe = ReferencePosition(board, color).play((7, 7)).position
            # Full-width independent reply enumeration, including reopened capture cells.
            wins = [m for m in legal_moves(safe) if safe.play(m).position.outcome ==
                    ('white_win' if color == 0 else 'black_win')]
            self.assertEqual(wins, [])
            engine = FixedDepthSearch(tactics=policy, clock=lambda: 0)
            player = IterativePlayer(color, max_depth=1, search=engine)
            self.assertIn(player.take_turn(board, -1), report.defenses)
            self.assertEqual(board, [list(row) for row in root.board])

    def test_overlines_and_capture_terminal_results_are_not_strict_wins(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            for col in (2, 3, 4, 6, 7):
                board[3][col] = color
            board[12][5:9] = [color] * 4
            root = Position(board, color)
            report = TacticalPolicy(cap=1).analyze(root)
            self.assertNotIn((3, 5), report.wins)
            self.assertEqual(ReferencePosition(board, color).play((3, 5)).position.outcome, 'ongoing')
            player = IterativePlayer(color, max_depth=1, search=FixedDepthSearch(tactics=TacticalPolicy(cap=1), clock=lambda: 0))
            self.assertIn(player.take_turn(board, -1), ((12, 4), (12, 9)))
            for simultaneous in (False, True):
                board = [[-1] * 19 for _ in range(19)]
                board[9][5:11] = [1 - color] * 6
                board[10][10], board[11][10] = 1 - color, color
                if simultaneous:
                    board[8][6:10] = [color] * 4
                root = Position(board, color)
                child = root.play((8, 10)).position
                oracle = ReferencePosition(board, color).play((8, 10)).position
                self.assertEqual(child.outcome, oracle.outcome)
                self.assertEqual(classify(child, color), 'draw' if simultaneous else 'opponent_win')
                self.assertNotIn((8, 10), TacticalPolicy().analyze(root).wins)
                if simultaneous:
                    player = IterativePlayer(color, max_depth=1, search=FixedDepthSearch(tactics=TacticalPolicy(cap=1), clock=lambda: 0))
                    self.assertEqual(player.take_turn(board, -1), (8, 5))
                    self.assertEqual(player.last_result.score, WIN_SCORE)
            dense = [[((r + 2 * c) % 4 // 2) ^ color for c in range(19)] for r in range(19)]
            dense[0][0] = -1
            draw = Position(dense, 1 - color).play((0, 0)).position
            self.assertEqual(classify(draw, 1 - color), 'draw')

    def test_direct_defense_and_complete_independent_wins_on_sparse_fixtures(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[0][:4] = [1 - color] * 4
            root = Position(board, color)
            policy = TacticalPolicy(cap=1, ordinary_rank=lambda p, m, check: -100000 if m == (0, 4) else 0)
            report = policy.analyze(root)
            self.assertEqual(report.threats, ((0, 4),))
            self.assertEqual(report.defenses, ((0, 4),))
            self.assertEqual(report.candidates, ((0, 4),))
            oracle = ReferencePosition(board, 1 - color)
            expected = tuple(m for m in legal_moves(oracle) if classify(oracle.play(m).position, 1 - color) == 'win')
            self.assertEqual(report.threats, expected)
            player = IterativePlayer(color, max_depth=1, search=FixedDepthSearch(tactics=policy, clock=lambda: 0))
            self.assertEqual(player.take_turn(board, -1), (0, 4))

    def test_complete_reply_scan_rejects_new_threat_after_a_capture(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[8][6:12] = [1 - color] * 6
            board[9][5:9] = [1 - color] * 4
            board[10][6], board[10][9] = color, color
            root = Position(board, color)
            child = root.play((7, 6)).position
            self.assertEqual(child.outcome, 'ongoing')
            self.assertEqual(ReferencePosition(board, color).play((7, 6)).position.board, child.board)
            self.assertEqual(immediate_wins(child, lambda: None), ((8, 7), (8, 12)))
            report = TacticalPolicy().analyze(root)
            self.assertEqual(report.threats, ((9, 4), (9, 9)))
            self.assertNotIn((7, 6), report.defenses)
            for reply in ((8, 7), (8, 12)):
                oracle = ReferencePosition(board, color).play((7, 6)).position.play(reply).position
                self.assertEqual(oracle.outcome, 'white_win' if color == 0 else 'black_win')

    def test_local_membership_opening_fallback_legality_and_full_width(self):
        policy = TacticalPolicy(radius=1, cap=3)
        self.assertEqual(policy.analyze(Position.empty()).candidates, ((9, 9),))
        root = Position.empty().play((9, 9)).position
        report = policy.analyze(root)
        self.assertEqual(len(report.candidates), 3)
        self.assertEqual(len(set(report.candidates)), 3)
        for row, col in report.candidates:
            self.assertLessEqual(max(abs(row - 9), abs(col - 9)), 1)
            root.play((row, col))
        fallback = TacticalPolicy(radius=0, cap=2).analyze(root)
        self.assertEqual(len(fallback.candidates), 2)
        for move in fallback.candidates:
            root.play(move)
        wide = TacticalPolicy(full_width=True, cap=1).analyze(root)
        self.assertEqual(wide.candidates, tuple(legal_moves(root)))
        for options in ({'radius': -1}, {'radius': True}, {'cap': 0}, {'cap': 1.5}, {'full_width': 1}):
            with self.assertRaises(ValueError):
                TacticalPolicy(**options)

    def test_interrupted_scans_keep_all_legal_choices_and_never_prove_safety(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][6:10] = [1] * 4
        board[8][7], board[10][7] = 1, 0
        root = Position(board, 0)
        counts = [0]
        def measure():
            counts[0] += 1
        complete = TacticalPolicy(cap=1).analyze(root, measure)
        total = counts[0]
        for stop in (1, total // 8, total // 4, total // 2, total - 1):
            counts[0] = 0
            def cancel():
                counts[0] += 1
                if counts[0] >= stop:
                    raise SearchCancelled('requested')
            result = TacticalPolicy(cap=1).analyze(root, cancel)
            self.assertFalse(result.complete)
            self.assertEqual(result.cancellation, 'requested')
            self.assertEqual(result.candidates, tuple(legal_moves(root)))
            self.assertTrue(set(result.defenses) <= set(complete.defenses))
            self.assertEqual(root, Position(board, 0))
        # Cancellation inside comparison work, after every key has been made.
        counts[0] = 0
        def during_sort():
            counts[0] += 1
            if counts[0] == 20:
                raise SearchCancelled('sort')
        with self.assertRaisesRegex(SearchCancelled, 'sort'):
            checked_sorted(range(15, 0, -1), lambda x: (x,), during_sort)

    def test_public_interruption_diagnostics_and_verified_win_fallback(self):
        board = [[-1] * 19 for _ in range(19)]
        board[0][:4] = [0] * 4
        root = Position(board, 0)
        def expired_ranking(position, move, check):
            ticks[0] = 2
            check()
            return 0
        ticks = [0]
        engine = FixedDepthSearch(tactics=TacticalPolicy(ordinary_rank=expired_ranking), clock=lambda: ticks[0])
        player = IterativePlayer(0, search=engine)
        self.assertEqual(player.take_turn(board, -1), (0, 4))
        result = player.last_result
        self.assertEqual(result.completed_depth, 0)
        self.assertIsNone(result.score)
        self.assertFalse(result.tactics.complete)
        self.assertTrue(result.tactics.wins_complete)
        self.assertEqual(result.cancellation, 'deadline')
        self.assertEqual(board, [list(row) for row in root.board])
        for remaining in (0.001, 1, 3, 20):
            move = IterativePlayer(0).take_turn(board, remaining)
            root.play(move)
            self.assertEqual(board, [list(row) for row in root.board])
        # A caller-supplied ordering hook consumes exactly the same deadline.
        ticks[0] = 0
        engine = FixedDepthSearch(tactics=TacticalPolicy(cap=2), ordering=expired_ranking, clock=lambda: ticks[0])
        result = engine.iterative(root, 2, limits=SearchLimits(deadline=1))
        self.assertEqual(result.move, (0, 4))
        self.assertEqual(result.cancellation, 'deadline')
        self.assertTrue(result.tactics.complete)

    def test_full_width_tactical_reference_and_matched_search_after_integration(self):
        board = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
        for row, col in ((0, 0), (0, 1), (1, 0)):
            board[row][col] = -1
        for color in (0, 1):
            root = Position(board, color)
            oracle = ReferencePosition(board, color)
            expected_wins = tuple(m for m in legal_moves(oracle) if classify(oracle.play(m).position, color) == 'win')
            policy = TacticalPolicy(full_width=True)
            report = policy.analyze(root)
            self.assertEqual(report.wins, expected_wins)
            self.assertEqual(report.candidates, tuple(legal_moves(root)))
            for depth in (1, 2, 3):
                engine = FixedDepthSearch(tactics=policy)
                reference = engine.search(root, depth, reference=True)
                pruned = engine.search(root, depth)
                self.assertEqual(pruned.score, reference.score)
                self.assertIn(pruned.move, reference.optimal_moves)
                self.assertEqual(pruned.score, FixedDepthSearch().search(root, depth, reference=True).score)
            for ordinary_rank in (lambda p, m, check: 0, lambda p, m, check: -m[0] * 19 - m[1]):
                policy = TacticalPolicy(cap=2, ordinary_rank=ordinary_rank)
                engine = FixedDepthSearch(tactics=policy)
                for depth in (1, 2, 3):
                    reference = engine.search(root, depth, reference=True)
                    pruned = engine.search(root, depth)
                    self.assertEqual(pruned.score, reference.score)
                    self.assertIn(pruned.move, reference.optimal_moves)

    def test_absent_defenses_are_not_a_forced_loss_and_partial_iteration_keeps_commit(self):
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[9][6:10] = [1 - color] * 4
            root = Position(board, color)
            report = TacticalPolicy(cap=1).analyze(root)
            self.assertTrue(report.complete)
            self.assertEqual(report.defenses, ())
            self.assertTrue(report.candidates)
            result = FixedDepthSearch(tactics=TacticalPolicy(cap=1)).search(root, 1)
            self.assertGreater(result.score, -WIN_SCORE)
        root = Position.empty().play((9, 9)).position
        count = [0]
        def clock():
            count[0] += 1
            return 0
        engine = FixedDepthSearch(tactics=TacticalPolicy(cap=2), clock=clock)
        commit = engine.iterative(root, 1, limits=SearchLimits(deadline=1))
        stop = count[0] + 10
        count[0] = 0
        def expires():
            count[0] += 1
            return 2 if count[0] >= stop else 0
        engine = FixedDepthSearch(tactics=TacticalPolicy(cap=2), clock=expires)
        result = engine.iterative(root, 3, limits=SearchLimits(deadline=1))
        self.assertEqual((result.move, result.score, result.completed_depth, result.principal_variation),
                         (commit.move, commit.score, 1, commit.principal_variation))
        self.assertEqual(result.attempted_depth, 2)
        self.assertFalse(result.tactics.complete)
        self.assertEqual(result.cancellation, 'deadline')

    def test_complete_defenses_match_exhaustive_independent_reference(self):
        for color in (0, 1):
            board = small_fixture(color)
            expected = reference_tactics(ReferencePosition(board, color))
            report = TacticalPolicy(full_width=True).analyze(Position(board, color))
            self.assertEqual(report.wins, expected['wins'])
            self.assertEqual(report.threats, expected['threats'])
            self.assertEqual(report.defenses, expected['defenses'])
            self.assertEqual(report.defenses, ((0, 4),))
            self.assertTrue(report.complete)

    def test_every_public_checkpoint_cancellation_includes_locality_and_sorting(self):
        root = Position.empty().play((9, 9)).position
        board = [list(row) for row in root.board]
        sibling = root.play((8, 8)).position
        count = [0]
        def measure():
            count[0] += 1
            return 0
        policy = TacticalPolicy(radius=2, cap=1)
        player = IterativePlayer(1, max_depth=1, search=FixedDepthSearch(tactics=policy, clock=measure))
        player.take_turn(board, -1)
        total = count[0]
        # Sweep every clock checkpoint of the completed call, including all local
        # neighborhood generation and comparison checks, without replacing code.
        incomplete = 0
        for stop in range(2, total):
            count[0] = 0
            def expires():
                count[0] += 1
                return 1 if count[0] >= stop else 0
            player = IterativePlayer(1, max_depth=1, search=FixedDepthSearch(tactics=policy, clock=expires))
            move = player.take_turn(board, -1)
            root.play(move)
            report = player.last_result.tactics
            if report is not None and not report.complete:
                incomplete += 1
                self.assertEqual(report.candidates, tuple(legal_moves(root)))
                self.assertEqual(report.cancellation, 'deadline')
            self.assertEqual(board, [list(row) for row in root.board])
            self.assertEqual(root, Position(board, 1))
            self.assertEqual(sibling, root.play((8, 8)).position)
        self.assertGreater(incomplete, 0)
        # The same root is reusable after every interrupted generation/sort.
        recovered = FixedDepthSearch(tactics=policy).search(root, 1)
        fresh = FixedDepthSearch(tactics=TacticalPolicy(radius=2, cap=1)).search(root, 1)
        self.assertEqual(recovered, fresh)


if __name__ == '__main__':
    unittest.main()
