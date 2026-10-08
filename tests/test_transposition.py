# AI-written by OpenAI Codex, for issue #13.
import unittest
import random

from omok.search import FixedDepthSearch, SearchLimits, SearchCancelled
from omok.player import IterativePlayer
from omok.simulator import Position
from omok.tactics import TacticalPolicy
from omok.transposition import TableEntry, TranspositionTable


CELLS = ((0, 0), (0, 1), (1, 0), (1, 1))


def candidates(position):
    return [m for m in CELLS if position.board[m[0]][m[1]] == -1]


class TranspositionTests(unittest.TestCase):
    def assert_reference(self, engine, root, depth):
        reference = engine.search(root, depth, reference=True)
        result = engine.search(root, depth)
        self.assertEqual(result.score, reference.score)
        self.assertIn(result.move, reference.optimal_moves)
        leaf = root
        for move in result.principal_variation:
            leaf = leaf.play(move).position
        self.assertTrue(len(result.principal_variation) == depth or leaf.outcome != 'ongoing')
        self.assertEqual(engine.score(leaf, root.side_to_move), result.score)
        return result

    def test_repeated_search_reuses_only_compatible_completed_values(self):
        engine = FixedDepthSearch(candidates=candidates, table=TranspositionTable(128))
        for side in (0, 1):
            root = Position(Position.empty().board, side)
            reference = engine.search(root, 4, reference=True)
            cold = engine.search(root, 4)
            warm = engine.search(root, 4)
            self.assertEqual(warm.score, reference.score)
            self.assertIn(warm.move, reference.optimal_moves)
            self.assertLess(warm.nodes, cold.nodes)
            self.assertGreater(engine.table.hits, 0)

    def test_bounds_are_classified_against_the_tightened_window(self):
        root = Position.empty()
        child = root.play(CELLS[0]).position
        for bound, resulting in (('lower', 'upper'), ('upper', 'lower')):
            table = TranspositionTable(128)
            engine = FixedDepthSearch(candidates=candidates, table=table)
            policy = engine.cache_compatibility()
            # Material at this white-to-move one-ply node is exactly zero.
            table.store(child, policy, TableEntry(1, 0, bound, CELLS[1], (CELLS[1],)))
            self.assert_reference(engine, root, 2)
            self.assertEqual(table.probe(child, policy, 1).bound, resulting)
            self.assert_reference(engine, root, 2)

    def test_cached_bounds_close_windows_without_changing_optimal_moves(self):
        root = Position.empty()
        table = TranspositionTable(128)
        engine = FixedDepthSearch(candidates=candidates, table=table)
        policy = engine.cache_compatibility()
        # After the first root move proves zero, other children have beta=0.
        for move in CELLS[1:]:
            child = root.play(move).position
            reply = next(m for m in CELLS if m != move)
            table.store(child, policy, TableEntry(1, 0, 'lower', reply, (reply,)))
        result = self.assert_reference(engine, root, 2)
        self.assertGreaterEqual(result.cutoffs, 3)

    def test_depth_side_and_policy_changes_match_uncached_and_unpruned_trees(self):
        for capacity in (4, 128):
            for seed in range(6):
                weights = random.Random(seed).sample(range(-20, 21), 4)
                def evaluate(position):
                    return sum(w if position.board[r][c] == 0 else -w
                               for (r, c), w in zip(CELLS, weights)
                               if position.board[r][c] != -1)
                engine = FixedDepthSearch(candidates=candidates, evaluator=evaluate,
                                          table=TranspositionTable(capacity))
                for depth in (4, 1, 3, 2, 4):
                    for side in (0, 1):
                        root = Position(Position.empty().board, side)
                        result = self.assert_reference(engine, root, depth)
                        clean = FixedDepthSearch(candidates=candidates, evaluator=evaluate).search(root, depth)
                        self.assertEqual(result.score, clean.score)
                        self.assertLessEqual(len(engine.table), capacity)
                if capacity == 4:
                    self.assertGreater(engine.table.evictions, 0)

    def test_compatibility_versions_and_replaced_callbacks_segregate_values(self):
        value = [1]
        engine = FixedDepthSearch(candidates=candidates, evaluator=lambda p: value[0],
                                  table=TranspositionTable(128), compatibility='eval-v1')
        root = Position.empty()
        self.assertEqual(engine.search(root, 2).score, 1)
        old = engine.cache_compatibility()
        value[0] = 7
        engine.compatibility = 'eval-v2'
        self.assertNotEqual(old, engine.cache_compatibility())
        self.assertEqual(engine.search(root, 2).score, 7)
        engine.evaluator = lambda p: -9
        self.assertEqual(engine.search(root, 2).score, -9)
        old = engine.cache_compatibility()
        engine.candidates = lambda p: [m for m in CELLS[:3] if p.board[m[0]][m[1]] == -1]
        self.assertNotEqual(old, engine.cache_compatibility())
        self.assert_reference(engine, root, 2)
        for policy in (TacticalPolicy(cap=1), TacticalPolicy(cap=2), None):
            old = engine.cache_compatibility()
            engine.tactics = policy
            self.assertNotEqual(old, engine.cache_compatibility())
            self.assert_reference(engine, root, 1)

    def test_illegal_or_excluded_hints_cannot_change_membership_or_values(self):
        root = Position.empty()
        child = root.play(CELLS[0]).position
        for hint in ((-1, 0), (19, 0), CELLS[0], (9, 9), (True, 0)):
            engine = FixedDepthSearch(candidates=candidates, table=TranspositionTable(128))
            # Poison value only becomes usable if the invalid hint is accepted.
            entry = TableEntry(1, 999, 'exact', hint, (hint,))
            engine.table.store(child, engine.cache_compatibility(), entry)
            self.assert_reference(engine, root, 2)
            # A different depth can supply ordering hints, never this value.
            engine.table.store(root, engine.cache_compatibility(), TableEntry(8, 999, 'exact', hint, (hint,)))
            self.assert_reference(engine, root, 3)

    def test_every_node_interruption_keeps_only_completed_entries_and_commits(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][10:13] = [1, 1, 0]
        root = Position(board, 0)
        cells = ((9, 9), (3, 3), (4, 4), (5, 5))
        def moves(position):
            return [m for m in cells if position.board[m[0]][m[1]] == -1]
        baseline = FixedDepthSearch(candidates=moves, table=TranspositionTable(128)).iterative(root, 4)
        retained = False
        for limit in range(baseline.nodes):
            engine = FixedDepthSearch(candidates=moves, table=TranspositionTable(128))
            result = engine.iterative(root, 4, limits=SearchLimits(max_nodes=limit))
            self.assertEqual(result.cancellation, 'node_limit')
            self.assertIsNone(engine.table.probe(root, engine.cache_compatibility(), result.attempted_depth))
            retained |= len(engine.table) > 0
            if result.completed_depth:
                reference = engine.search(root, result.completed_depth, reference=True)
                self.assertEqual(result.score, reference.score)
                self.assertIn(result.move, reference.optimal_moves)
            else:
                self.assertIsNone(result.score)
            self.assertEqual(root, Position(board, 0))
            self.assert_reference(engine, root, 4)
        self.assertTrue(retained)

    def test_controlled_errors_and_callback_cancellation_leave_clean_subsequent_search(self):
        root = Position.empty()
        for error in (RuntimeError('controlled defect'), SearchCancelled('requested')):
            calls = [0]
            broken = [True]
            def evaluator(position):
                calls[0] += 1
                if broken[0] and calls[0] == 3:
                    raise error
                return 5
            engine = FixedDepthSearch(candidates=candidates, evaluator=evaluator,
                                      table=TranspositionTable(128), clock=lambda: 0)
            player = IterativePlayer(0, max_depth=4, search=engine)
            board = [list(row) for row in root.board]
            if isinstance(error, SearchCancelled):
                player.take_turn(board, -1)
                self.assertEqual(player.last_result.cancellation, 'requested')
                self.assertFalse(player.last_result.completed)
            else:
                with self.assertRaisesRegex(RuntimeError, 'controlled defect'):
                    player.take_turn(board, -1)
                self.assertIsNone(player.last_result)
            self.assertGreater(len(engine.table), 0)
            self.assertIsNone(engine.table.probe(root, engine.cache_compatibility(), 1))
            self.assertEqual(board, [list(row) for row in root.board])
            broken[0] = False
            self.assert_reference(engine, root, 3)

    def test_bounded_replacement_reset_and_default_player(self):
        for capacity in (0, 1, 16):
            table = TranspositionTable(capacity)
            engine = FixedDepthSearch(candidates=candidates, table=table)
            self.assert_reference(engine, Position.empty(), 4)
            self.assertLessEqual(len(table), capacity)
            table.clear()
            self.assertEqual((len(table), table.hits, table.evictions), (0, 0, 0))
            self.assertIsNone(table.hint(Position.empty(), engine.cache_compatibility()))
        for capacity in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                TranspositionTable(capacity)
        player = IterativePlayer(0, max_depth=1)
        board = [[-1] * 19 for _ in range(19)]
        self.assertEqual(player.take_turn(board, -1), (9, 9))
        self.assertGreater(len(player.search.table), 0)

    def test_hash_collisions_do_not_merge_identities_and_long_lines_are_not_retained(self):
        class Collision:
            def __init__(self, value):
                self.value = value
            def __hash__(self):
                return 0
            def __eq__(self, other):
                return isinstance(other, Collision) and self.value == other.value
        table = TranspositionTable(2)
        root = Position.empty()
        first, second = Collision('first'), Collision('second')
        table.store(root, first, TableEntry(1, 3, 'exact', CELLS[0], (CELLS[0],)))
        table.store(root, second, TableEntry(1, -7, 'exact', CELLS[1], (CELLS[1],)))
        self.assertEqual(table.probe(root, first, 1).score, 3)
        self.assertEqual(table.probe(root, second, 1).score, -7)
        self.assertIsNone(table.probe(Position(root.board, 1), first, 1))
        table.store(root, first, TableEntry(65, 3, 'exact', CELLS[0], (CELLS[0],) * 65))
        self.assertIsNone(table.probe(root, first, 65))
        # Replacement and eviction must also release the corresponding hints.
        table.store(root, first, TableEntry(1, 3, 'exact'))
        self.assertIsNone(table.hint(root, first))
        table.store(root, 'third', TableEntry(1, 4, 'exact'))
        self.assertIsNone(table.probe(root, second, 1))
        self.assertIsNone(table.hint(root, second))


if __name__ == '__main__':
    unittest.main()
