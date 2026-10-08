# AI-written by OpenAI Codex, for issue #7.
import sys
import unittest

from offline.provided import load_players
from offline.runner import run_game
from offline.replay import replay
from omok.simulator import Position


class ProvidedTests(unittest.TestCase):
    def test_actual_inheritance_explicit_color_and_fresh_state(self):
        previous = sys.modules.get('player')
        loaded = load_players()
        self.assertIs(sys.modules.get('player'), previous)
        for name in ('random', 'simple', 'baseline'):
            for color in (0, 1):
                with self.subTest(name=name, color=color):
                    player = loaded.create(name, color)
                    self.assertIsInstance(player, loaded.base)
                    self.assertEqual(player.color, color)
                    self.assertIsNot(player, loaded.create(name, color))
                    board = [[-1] * 19 for _ in range(19)]
                    original = [row[:] for row in board]
                    move = player.take_turn(board, 60000)
                    self.assertEqual(move, (9, 9))
                    self.assertEqual(board, original)
                    Position(board, color).play(move)
        first = loaded.create('random', 0)
        second = loaded.create('random', 0)
        first.take_turn([[-1] * 19 for _ in range(19)], 60000)
        self.assertIsNone(second._prev_board)

    def test_real_baseline_boundary_wins_for_both_colors(self):
        loaded = load_players()
        for color in (0, 1):
            board = [[-1] * 19 for _ in range(19)]
            board[9][4] = 1 - color
            board[9][5:9] = [color] * 4
            original = [row[:] for row in board]
            player = loaded.create('baseline', color)
            move = player.take_turn(board, 60000)
            self.assertEqual(move, (9, 9))
            self.assertEqual(board, original)
            expected = 'black_win' if color == 0 else 'white_win'
            self.assertEqual(Position(board, color).play(move).position.outcome, expected)

    def test_supplied_players_run_and_replay_with_owned_snapshots(self):
        loaded = load_players()
        for name in ('random', 'simple'):
            for color in (0, 1):
                players = [loaded.create('baseline', color), loaded.create(name, 1 - color)]
                if color == 1:
                    players.reverse()
                result = run_game(*players, move_cap=4)
                self.assertEqual(result['status'], 'capped')
                self.assertIsNone(result['failure'])
                self.assertEqual(len(result['moves']), 4)
                replay(result)


if __name__ == '__main__':
    unittest.main()
