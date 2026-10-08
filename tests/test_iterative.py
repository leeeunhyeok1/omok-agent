# AI-written by OpenAI Codex, for issue #11.
import unittest

from omok.search import FixedDepthSearch, SearchLimits
from omok.simulator import Position
from omok.player import IterativePlayer, TimePolicy
from verification.reference import ReferencePosition


def candidates(position):
    return [m for m in ((9, 9), (3, 3), (4, 4), (5, 5)) if position.board[m[0]][m[1]] == -1]


class IterativeTests(unittest.TestCase):
    def test_every_interrupted_iteration_preserves_the_last_entire_commit(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][10:13] = [1, 1, 0]
        before = [row[:] for row in board]
        root = Position(board, 0)
        sibling = root.play((0, 0)).position
        engine = FixedDepthSearch(candidates=candidates)
        completions = [engine.iterative(root, depth) for depth in range(1, 5)]
        for limit in range(completions[-1].nodes):
            result = engine.iterative(root, 4, limits=SearchLimits(max_nodes=limit))
            previous = [r for r in completions if r.nodes <= limit]
            if previous:
                committed = previous[-1]
                self.assertEqual((result.move, result.score, result.completed_depth,
                                  result.principal_variation, result.pv_status),
                                 (committed.move, committed.score, committed.completed_depth,
                                  committed.principal_variation, committed.pv_status))
            else:
                self.assertEqual((result.move, result.score, result.completed_depth),
                                 ((0, 0), None, 0))
                self.assertEqual(result.pv_status, 'unavailable')
            self.assertEqual(result.attempted_depth, result.completed_depth + 1)
            self.assertEqual(result.cancellation, 'node_limit')
            self.assertEqual(root, Position(before, 0))
            self.assertEqual(sibling, root.play((0, 0)).position)
            self.assertEqual(board, before)
            self.assertEqual(engine.iterative(root, 3),
                             FixedDepthSearch(candidates=candidates).iterative(root, 3))

    def test_fake_clock_interrupts_scans_ordering_evaluation_and_deeper_recursion(self):
        root = Position.empty()
        for phase in ('candidates', 'ordering', 'evaluation'):
            ticks = [0.0]
            def scan(position, check):
                if phase == 'candidates':
                    ticks[0] = 2
                    check()
                yield from candidates(position)
            def ordering(position, move, check):
                if phase == 'ordering':
                    ticks[0] = 2
                    check()
                return 0
            def evaluate(position, check):
                ticks[0] = 2
                check()
                return 0
            engine = FixedDepthSearch(cooperative_candidates=scan, ordering=ordering,
                                      cooperative_evaluator=evaluate, clock=lambda: ticks[0])
            result = engine.iterative(root, 3, limits=SearchLimits(deadline=1))
            self.assertEqual((result.completed_depth, result.attempted_depth), (0, 1))
            self.assertEqual(result.cancellation, 'deadline')
            self.assertEqual(root, Position.empty())
            ticks[0] = 0
            # Disable the deadline, then compare the recovered engine with a fresh one.
            self.assertEqual(engine.iterative(root, 2),
                             FixedDepthSearch(cooperative_candidates=scan, ordering=ordering,
                                              cooperative_evaluator=evaluate).iterative(root, 2))
        baseline = FixedDepthSearch(candidates=candidates).iterative(root, 4)
        counts = []
        for depth in (1, 3):
            ticks = [0]
            def count_clock():
                ticks[0] += 1
                return 0
            FixedDepthSearch(candidates=candidates, clock=count_clock).iterative(
                root, depth, limits=SearchLimits(deadline=1))
            counts.append(ticks[0])
        for expired_at in (1, counts[0] + 5, counts[1] + 1, counts[1] + 10, counts[1] + 30):
            ticks = [0]
            def clock():
                ticks[0] += 1
                return 2 if ticks[0] >= expired_at else 0
            engine = FixedDepthSearch(candidates=candidates, clock=clock)
            result = engine.iterative(root, 4, limits=SearchLimits(deadline=1))
            self.assertEqual(result.cancellation, 'deadline')
            if result.completed_depth:
                clean = FixedDepthSearch(candidates=candidates).iterative(root, result.completed_depth)
                self.assertEqual((result.move, result.score, result.principal_variation),
                                 (clean.move, clean.score, clean.principal_variation))
            self.assertEqual(engine.iterative(root, 4), baseline)

    def test_completed_principal_variation_replays_independent_rules_and_score(self):
        for color in (0, 1):
            for terminal in (False, True):
                board = [[-1] * 19 for _ in range(19)]
                if terminal:
                    board[9][5:9] = [color] * 4
                root = Position(board, color)
                engine = FixedDepthSearch(candidates=lambda p: [m for m in ((9, 9), (3, 3), (4, 4))
                                                                if p.board[m[0]][m[1]] == -1])
                for depth in (1, 2, 3):
                    result = engine.iterative(root, depth)
                    oracle = ReferencePosition(board, color)
                    leaf = root
                    for move in result.principal_variation:
                        self.assertEqual(oracle.outcome, 'ongoing')
                        oracle = oracle.play(move).position
                        leaf = leaf.play(move).position
                        self.assertEqual(oracle.board, leaf.board)
                        self.assertEqual(oracle.outcome, leaf.outcome)
                    self.assertTrue(len(result.principal_variation) == depth or oracle.outcome != 'ongoing')
                    if oracle.outcome == 'ongoing':
                        value = sum(1 if cell == color else -1 if cell == 1 - color else 0
                                    for row in oracle.board for cell in row)
                    else:
                        value = 0 if oracle.outcome == 'draw' else (10000 if oracle.outcome ==
                                ('black_win' if color == 0 else 'white_win') else -10000)
                    self.assertEqual(result.score, value)
                    self.assertEqual(result.pv_status, 'complete')

    def test_soft_stop_keeps_commit_and_unexpected_errors_are_reported(self):
        ticks = [0.0]
        def evaluator(position):
            ticks[0] = 0.9
            return 1
        engine = FixedDepthSearch(candidates=candidates, evaluator=evaluator, clock=lambda: ticks[0])
        result = engine.iterative(Position.empty(), 3, limits=SearchLimits(deadline=1), soft_deadline=0.8)
        self.assertEqual((result.completed_depth, result.attempted_depth, result.cancellation),
                         (1, 1, 'soft_stop'))
        def broken(position, check):
            raise RuntimeError('evaluation defect')
        player = IterativePlayer(0, search=FixedDepthSearch(cooperative_evaluator=broken, clock=lambda: 0))
        with self.assertRaisesRegex(RuntimeError, 'evaluation defect'):
            player.take_turn([[-1] * 19 for _ in range(19)], -1)
        self.assertIsNone(player.last_result)

    def test_public_cancellation_returns_completed_search_and_validates_limits(self):
        root = Position.empty()
        engine = FixedDepthSearch(candidates=candidates, clock=lambda: 0)
        completed = engine.iterative(root, 2)
        player = IterativePlayer(0, max_nodes=completed.nodes + 1, search=engine)
        self.assertEqual(player.take_turn(root.board, 60000), completed.move)
        result = player.last_result
        self.assertEqual((result.score, result.completed_depth, result.principal_variation),
                         (completed.score, 2, completed.principal_variation))
        self.assertEqual(result.attempted_depth, 3)
        for time in (True, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                player.take_turn(root.board, time)
            self.assertIsNone(player.last_result)
        for options in ({'max_nodes': -1}, {'max_nodes': None}, {'max_depth': 0}, {'color': True}):
            with self.assertRaises(ValueError):
                IterativePlayer(**({'color': 0} | options))
        for options in ({'max_time_ms': -1}, {'return_margin_ms': True},
                        {'reserve_fraction': 1}, {'soft_fraction': 0}, {'turn_fraction': float('nan')}):
            with self.assertRaises(ValueError):
                TimePolicy(**options)

    def test_public_clock_includes_conversion_and_retains_commit(self):
        ticks = [0.0]
        class SlowRow(list):
            def __iter__(self):
                ticks[0] += 0.01
                return super().__iter__()
        board = [SlowRow([-1] * 19) for _ in range(19)]
        player = IterativePlayer(0, search=FixedDepthSearch(clock=lambda: ticks[0]))
        self.assertEqual(player.take_turn(board, 60000), (0, 0))
        self.assertEqual(player.last_result.completed_depth, 0)
        self.assertEqual(player.last_result.cancellation, 'soft_stop')
        self.assertGreaterEqual(player.last_elapsed_ms, 190)
        policy = TimePolicy()
        self.assertEqual(policy.allowance(0), 0)
        self.assertEqual(policy.allowance(-2), 0)
        self.assertEqual(policy.allowance(-1), 100)
        self.assertLess(policy.allowance(60000), 60000)
        for remaining in (0.001, 0, -2, -1):
            board = [[-1] * 19 for _ in range(19)]
            before = [row[:] for row in board]
            player = IterativePlayer(1, max_nodes=0)
            Position(board, 1).play(player.take_turn(board, remaining))
            self.assertEqual(board, before)
            self.assertEqual(player.last_result.completed_depth, 0)


if __name__ == '__main__':
    unittest.main()
