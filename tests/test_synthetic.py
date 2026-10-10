# AI-written by OpenAI Codex, for issue #30.
"""Synthetic behavior is observed at the complete game operation."""
import unittest

from offline.runner import run_game
from offline.opponents import SeededSmokePlayer
from omok.simulator import Position


class SyntheticTests(unittest.TestCase):
    def move(self, strategy, stones, color=0, seed=7):
        from offline.synthetic import create
        board = [[-1] * 19 for _ in range(19)]
        for r, c, side in stones:
            board[r][c] = side
        bot = create(color, strategy=strategy, seed=seed)
        other = SeededSmokePlayer(1 - color, 1)
        players = (bot, other) if color == 0 else (other, bot)
        trace = run_game(*players, initial=Position(board, color), move_cap=1)
        self.assertIsNone(trace['failure'])
        return tuple(trace['moves'][0]['move'])

    def test_local_density_prefers_cluster_over_remote_line(self):
        stones = [(3, c, 0) for c in range(3, 6)] + [(r, c, 0) for r, c in
                  ((10, 10), (10, 12), (12, 10), (12, 12))]
        self.assertEqual(self.move('local', stones), (11, 11))

    def test_aggressive_extends_own_line_instead_of_dense_cluster(self):
        stones = [(3, c, 0) for c in range(3, 6)] + [(r, c, 0) for r, c in
                  ((10, 10), (10, 12), (12, 10), (12, 12))]
        self.assertEqual(self.move('aggressive', stones), (3, 6))

    def test_defensive_blocks_unique_win_before_attacking(self):
        stones = [(5, c, 1) for c in range(5, 9)] + [(5, 4, 0)]
        stones += [(12, c, 0) for c in range(10, 13)]
        self.assertEqual(self.move('defensive', stones), (5, 9))

    def test_capture_collects_pair_before_extending_own_line(self):
        stones = [(5, 6, 1), (5, 7, 1), (5, 8, 0)]
        stones += [(12, c, 0) for c in range(10, 13)]
        self.assertEqual(self.move('capture', stones), (5, 5))

    def test_pattern_fills_broken_four(self):
        stones = [(3, c, 0) for c in (3, 4, 6, 7)]
        self.assertEqual(self.move('pattern', stones), (3, 5))

    def test_pattern_builds_crossing_windows_instead_of_extending_remote_run(self):
        stones = ([(3, c, 0) for c in range(3, 6)]
                  + [(9, c, 0) for c in (7, 10, 11)]
                  + [(r, 9, 0) for r in (7, 10, 11)])
        self.assertEqual(self.move('pattern', stones), (9, 9))
        self.assertEqual(self.move('aggressive', stones), (3, 6))

    def test_two_ply_search_sees_reply_that_one_ply_misses(self):
        stones = [(5, c, 1) for c in range(5, 9)] + [(5, 4, 0)]
        stones += [(12, c, 0) for c in range(10, 13)]
        self.assertIn(self.move('search1', stones), ((12, 9), (12, 13)))
        self.assertEqual(self.move('search2', stones), (5, 9))

    def test_frontier_random_is_reproducible_and_varies_across_seeds(self):
        stones = [(9, 9, 0)]
        first = self.move('random', stones, color=1, seed=7)
        self.assertEqual(first, self.move('random', stones, color=1, seed=7))
        moves = {self.move('random', stones, color=1, seed=seed) for seed in range(8)}
        self.assertGreater(len(moves), 1)
        self.assertTrue(all(max(abs(r - 9), abs(c - 9)) == 1 for r, c in moves))

    def test_catalog_runs_synthetic_and_protects_actual_holdout(self):
        from offline.registry import default_catalog, run_registered_game
        from offline.replay import replay
        from offline.experiments import ExperimentPlan
        catalog, snapshot = default_catalog()
        plan = ExperimentPlan.resolve(catalog['phase2'], snapshot, games_per_opponent=2, move_cap=2)
        self.assertNotIn('synthetic-space', [j['opponent']['logical_id'] for j in plan.data['jobs']])
        with self.assertRaisesRegex(ValueError, 'protected holdout'):
            run_registered_game(catalog['phase2'], snapshot, 'synthetic-space', move_cap=1)
        trace = run_registered_game(catalog['synthetic-local'], snapshot, 'synthetic-random',
                                    seed=7, move_cap=4)
        self.assertIsNone(trace['failure'])
        self.assertEqual(len(trace['moves']), 4)
        replay(trace)
