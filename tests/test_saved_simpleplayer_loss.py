# AI-written by OpenAI Codex.
"""A captured SimplePlayer loss, with deterministic cooperative-work limits."""
import json
from pathlib import Path
import unittest

from offline.worker_players import create
from omok.search import SearchLimits
from omok.simulator import Position
from omok.tactics import TacticalPolicy
from verification.reference import ReferencePosition


FIXTURE = Path(__file__).resolve().parents[1] / 'verification/fixtures/simpleplayer-ply22.json'


class SavedSimplePlayerLossTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text())
        self.position = Position(**self.fixture['position'])

    def test_saved_blunder_loses_but_recorded_alternative_wins_after_same_reply(self):
        # The independent board oracle checks both continuations. The tactical
        # scan enumerates every legal defense, including capture defenses.
        for constructor in (Position, ReferencePosition):
            position = constructor(**self.fixture['position'])
            blunder = position.play(self.fixture['recorded_move']).position
            attacked = blunder.play(self.fixture['opponent_reply']).position
            for endpoint in self.fixture['reply_winning_endpoints']:
                opponent = constructor(attacked.board, 1)
                self.assertEqual(opponent.play(endpoint).position.outcome, 'white_win')
            safe = position.play(self.fixture['known_safe_move']).position
            safe = safe.play(self.fixture['opponent_reply']).position
            self.assertEqual(safe.play(self.fixture['winning_response_after_reply']).position.outcome,
                             'black_win')
        attacked = self.position.play(self.fixture['recorded_move']).position
        attacked = attacked.play(self.fixture['opponent_reply']).position
        tactics = TacticalPolicy().analyze(attacked)
        self.assertTrue(tactics.complete)
        self.assertTrue(tactics.threats)
        self.assertFalse(tactics.wins)
        self.assertFalse(tactics.defenses)

    def test_bounded_search_avoids_saved_forced_loss(self):
        configuration = self.fixture['configuration']
        search = create(0, name='search', settings=configuration['settings'],
                        evaluation=json.dumps(configuration['evaluation'])).search
        checks = 0

        def cancelled():
            nonlocal checks
            checks += 1
            return checks > 100000

        result = search.iterative(self.position, 1,
                                  limits=SearchLimits(max_nodes=10000, cancelled=cancelled))
        child = self.position.play(result.move).position
        self.assertNotEqual(child.outcome, 'white_win')
        reply = self.fixture['opponent_reply']
        if child.outcome != 'ongoing' or child.board[reply[0]][reply[1]] != -1:
            return
        attacked = child.play(reply).position
        self.assertNotEqual(attacked.outcome, 'white_win')
        tactics = TacticalPolicy().analyze(attacked)
        self.assertTrue(tactics.complete)
        self.assertFalse(tactics.threats and not tactics.wins and not tactics.defenses,
                         f'Chosen {result.move} permits the saved forced loss; '
                         f'{result.evaluation_completed} evaluations, '
                         f'depth {result.completed_depth}, checks {checks}')


if __name__ == '__main__':
    unittest.main()
