# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
import unittest
from offline.runner import run_game
from omok.simulator import Position


class ReturningPlayer:
    def __init__(self, color, moves):
        self.color = color
        self.moves = iter(moves)
        self.times = []
        self.boards = []

    def take_turn(self, board, time):
        self.times.append(time)
        self.boards.append(board)
        return next(self.moves)


class RunnerTests(unittest.TestCase):
    def test_alternation_owns_snapshots_and_debits_only_own_cumulative_clock(self):
        black = ReturningPlayer(0, [(0, 0), (0, 2)])
        white = ReturningPlayer(1, [(0, 1)])
        ticks = iter([0, .0012, 1, 1.002, 2, 2.003])
        result = run_game(black, white, budgets_ms=(10, 20), move_cap=3,
                          clock=lambda: next(ticks))
        self.assertEqual(black.times, [10, 8])
        self.assertEqual(white.times, [20])
        self.assertAlmostEqual(result['remaining_ms'][0], 5.8)
        self.assertAlmostEqual(result['remaining_ms'][1], 18)
        self.assertEqual(result['status'], 'capped')
        self.assertEqual(result['final']['outcome'], 'ongoing')
        self.assertIsNone(result['winner'])
        self.assertEqual(black.boards[0][0][1], -1)
        self.assertIsNot(black.boards[0], black.boards[1])
        self.assertEqual([m['color'] for m in result['moves']], [0, 1, 0])

    def test_distinct_failures_protect_authoritative_board_and_identify_player(self):
        class FailingPlayer:
            color = 1
            def take_turn(self, board, time):
                if behavior == 'exception':
                    raise RuntimeError('controlled failure')
                if behavior == 'mutation':
                    board[5][5] = 1
                    return (0, 1)
                if behavior == 'invalid_move':
                    return (0, 0)
                return (0, 1)
        for behavior in ('exception', 'mutation', 'invalid_move', 'timeout'):
            ticks = iter([0, .001, 1, 1.1 if behavior == 'timeout' else 1.001])
            result = run_game(ReturningPlayer(0, [(0, 0)]), FailingPlayer(),
                              budgets_ms=(10, 10), clock=lambda: next(ticks))
            with self.subTest(behavior=behavior):
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['failure']['reason'], behavior)
                self.assertEqual(result['failure']['color'], 1)
                self.assertEqual(len(result['moves']), 1)
                self.assertEqual(result['final']['board'][5][5], -1)
                self.assertEqual(result['final']['board'][0][1], -1)

    def test_exhaustion_stops_without_call_and_exact_budget_move_can_finish(self):
        black = ReturningPlayer(0, [])
        result = run_game(black, ReturningPlayer(1, []), budgets_ms=(0, 10))
        self.assertEqual(black.times, [])
        self.assertFalse(result['failure']['called'])
        board = [[-1] * 19 for _ in range(19)]
        board[0][:4] = [0] * 4
        ticks = iter([0, .001])
        result = run_game(ReturningPlayer(0, [(0, 4)]), ReturningPlayer(1, []),
                          initial=Position(board, 0), budgets_ms=(1, 10),
                          clock=lambda: next(ticks))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['winner'], 0)

    def test_terminal_fixtures_stop_before_an_extra_turn(self):
        boards = []
        board = [[-1] * 19 for _ in range(19)]
        board[8][6:10] = [0] * 4
        boards.append((board, 'black_win', []))
        board = [[-1] * 19 for _ in range(19)]
        board[9][5:11] = [1] * 6
        board[10][10], board[11][10] = 1, 0
        boards.append((board, 'white_win', [[9, 10], [10, 10]]))
        board = [row[:] for row in board]
        board[8][6:10] = [0] * 4
        boards.append((board, 'draw', [[9, 10], [10, 10]]))
        for board, outcome, captures in boards:
            black, white = ReturningPlayer(0, [(8, 10)]), ReturningPlayer(1, [])
            result = run_game(black, white, initial=Position(board, 0))
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['final']['outcome'], outcome)
            self.assertEqual([c['cell'] for c in result['moves'][0]['captured']], captures)
            self.assertEqual(white.times, [])
            terminal = Position(result['final']['board'], 1)
            result = run_game(ReturningPlayer(0, []), white, initial=terminal)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['moves'], [])

    def test_unlimited_mode_passes_minus_one_and_keeps_unlimited_clocks(self):
        black, white = ReturningPlayer(0, [(9, 9)]), ReturningPlayer(1, [(9, 10)])
        result = run_game(black, white, budgets_ms=(None, None), move_cap=2)
        self.assertEqual(black.times, [-1])
        self.assertEqual(white.times, [-1])
        self.assertEqual(result['remaining_ms'], [None, None])


if __name__ == '__main__':
    unittest.main()
