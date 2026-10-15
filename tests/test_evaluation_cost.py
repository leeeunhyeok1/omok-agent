# AI-written by OpenAI Codex.
"""Deterministic work regression from an uploaded Colab loss, round 0, ply 4."""
import unittest

from omok.evaluation import EvaluationConfig
from omok.search import FixedDepthSearch, SearchLimits
from omok.simulator import Position
from omok.tactics import TacticalPolicy
from omok.transposition import TranspositionTable


def loss_position():
    board = [[-1] * 19 for _ in range(19)]
    for row, col, color in ((0, 0, 0), (0, 1, 0), (7, 8, 1),
                            (8, 9, 1), (9, 9, 0), (9, 10, 1)):
        board[row][col] = color
    return Position(board, 0)


class EvaluationCostTests(unittest.TestCase):
    def test_full_evaluator_finishes_first_iteration_with_bounded_work(self):
        checks = 0

        def cancelled():
            nonlocal checks
            checks += 1
            return checks > 250000

        search = FixedDepthSearch(
            evaluation_config=EvaluationConfig(feature_version='effects-v1'),
            tactics=TacticalPolicy(), table=TranspositionTable())
        result = search.iterative(loss_position(), 1,
                                  limits=SearchLimits(max_nodes=10000, cancelled=cancelled))
        self.assertEqual(result.completed_depth, 1)
        self.assertEqual((result.move, result.score), ((10, 11), 1))
        self.assertEqual(result.evaluation_completed, 24)
