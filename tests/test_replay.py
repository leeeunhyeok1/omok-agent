# AI-written by OpenAI Codex, for issues #4 and #6.
import unittest
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from offline.fixtures import fixture
from offline.replay import load_trace, replay
from offline.runner import run_game
from omok.simulator import Position
from tests.test_runner import ReturningPlayer


class ReplayTests(unittest.TestCase):
    def test_retained_simple_player_loss_has_independent_exact_five_label(self):
        import gzip
        from verification.reference import ReferencePosition
        source = Path('docs/verification/issue-15/official-simple-black-20261009.json.gz')
        with gzip.open(source, 'rt') as stream:
            trace = json.load(stream)
        reference = ReferencePosition(trace['initial']['board'], trace['initial']['side_to_move'])
        for event in trace['moves']:
            reference = reference.play(event['move']).position
        self.assertEqual(reference.outcome, 'white_win')
        self.assertEqual(reference.reason, 'exact_five')
        self.assertEqual(replay(trace).board, reference.board)

    def test_trace_reader_rejects_overflowing_json_numbers(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.json'
            for number in ('1e999', '-1e999'):
                path.write_text('{"config": {"seed": ' + number + '}}')
                with self.subTest(number=number), self.assertRaisesRegex(ValueError, 'Nonfinite'):
                    load_trace(path)

    def test_versioned_events_distinguish_returned_applied_and_failed_moves(self):
        ticks = iter([0, .001, 1, 1.020])
        trace = run_game(ReturningPlayer(0, [(0, 0)]), ReturningPlayer(1, [(0, 1)]),
                         budgets_ms=(10, 10), clock=lambda: next(ticks),
                         config={'seed': 42})
        self.assertEqual(trace['format'], 'omok-game-v2')
        self.assertEqual([e['type'] for e in trace['events']],
                         ['returned', 'applied', 'returned', 'failure'])
        self.assertEqual(trace['events'][2]['move'], [0, 1])
        self.assertEqual(trace['events'][2]['remaining_ms'], 0)
        self.assertEqual(trace['players'][0]['source']['module'], 'tests.test_runner')
        self.assertEqual(len(trace['players'][0]['source']['sha256']), 64)
        self.assertEqual(replay(trace).board[0][1], -1)

    def test_event_corruption_is_rejected(self):
        trace = run_game(ReturningPlayer(0, [(0, 0)]), ReturningPlayer(1, []), move_cap=1)
        for damage in ('missing', 'order', 'returned', 'applied', 'state', 'clock', 'extra', 'source'):
            broken = deepcopy(trace)
            if damage == 'missing':
                del broken['events']
            elif damage == 'order':
                broken['events'].reverse()
            elif damage == 'returned':
                broken['events'][0]['move'] = [0, 1]
            elif damage == 'applied':
                broken['events'][1]['move'] = [0, 1]
            elif damage == 'state':
                broken['events'][1]['state']['board'][0][0] = -1
            elif damage == 'clock':
                broken['events'][0]['remaining_ms'] = 0
            elif damage == 'extra':
                broken['events'].append(deepcopy(broken['events'][0]))
            else:
                broken['players'][0]['source']['sha256'] = 'unknown'
            with self.subTest(damage=damage), self.assertRaisesRegex(ValueError, 'trace'):
                replay(broken)

    def test_json_round_trip_completed_games_and_rules_fixtures(self):
        for name, outcome in (('mover-win', 'black_win'), ('opponent-win', 'white_win'),
                              ('simultaneous', 'draw'), ('dense', 'draw')):
            initial = fixture(name)
            move = (0, 0) if name == 'dense' else (8, 10)
            players = [ReturningPlayer(0, [move]), ReturningPlayer(1, [move])]
            trace = json.loads(json.dumps(run_game(*players, initial=initial)))
            with self.subTest(fixture=name):
                self.assertEqual(trace['status'], 'completed')
                self.assertEqual(replay(trace).outcome, outcome)
                for event in trace['events']:
                    if event['type'] == 'applied':
                        event['captured'].reverse()
                self.assertEqual(replay(trace).outcome, outcome)
        trace = run_game(ReturningPlayer(0, [(0, c) for c in range(5)]),
                         ReturningPlayer(1, [(2, c) for c in range(4)]))
        self.assertEqual(len(trace['moves']), 9)
        self.assertEqual(replay(json.loads(json.dumps(trace))).outcome, 'black_win')

    def test_all_execution_failures_and_exhausted_clocks_replay_as_metadata(self):
        class FailingPlayer:
            color = 0
            def take_turn(self, board, time):
                if behavior == 'exception':
                    raise RuntimeError('controlled')
                if behavior == 'mutation':
                    board[0][0] = 0
                return (19, 0) if behavior == 'invalid_move' else (0, 0)
        for behavior in ('exception', 'mutation', 'invalid_move', 'timeout', 'exhausted'):
            ticks = iter([0, .020 if behavior == 'timeout' else .001])
            trace = run_game(FailingPlayer(), ReturningPlayer(1, []),
                             budgets_ms=(0 if behavior == 'exhausted' else 10, 10),
                             clock=lambda: next(ticks))
            with self.subTest(behavior=behavior):
                self.assertEqual(replay(json.loads(json.dumps(trace))).outcome, 'ongoing')
                broken = deepcopy(trace)
                broken['events'][-1]['reason'] = 'unknown'
                with self.assertRaises(ValueError):
                    replay(broken)

    def test_legacy_v1_trace_remains_replayable(self):
        trace = run_game(ReturningPlayer(0, [(0, 0)]), ReturningPlayer(1, []), move_cap=1)
        trace['format'] = 'omok-game-v1'
        del trace['events']
        for player in trace['players']:
            del player['source']
        self.assertEqual(replay(trace).board[0][0], 0)

    def test_cli_rejects_malformed_truncated_and_duplicate_key_json(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.json'
            trace = run_game(ReturningPlayer(0, []), ReturningPlayer(1, []), move_cap=0)
            valid = json.dumps(trace)
            for content in ('{', 'null', valid[:-1], valid[:-1] + ', "status": "capped"}',
                            valid.replace('"config": {}', '"config": {"x": NaN}')):
                path.write_text(content)
                result = subprocess.run([sys.executable, '-m', 'offline', '--replay', str(path)],
                                        capture_output=True, text=True, timeout=10)
                with self.subTest(content=content[:30]):
                    self.assertEqual(result.returncode, 2)
                    self.assertIn('error:', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
            path.write_text(valid)
            result = subprocess.run([sys.executable, '-m', 'offline', '--replay', str(path)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['outcome'], 'ongoing')

    def test_malformed_containers_coordinates_and_failure_claims_are_rejected(self):
        trace = run_game(ReturningPlayer(0, [(0, 0)]), ReturningPlayer(1, []), move_cap=1)
        for value in (None, [], 42, 'trace'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replay(value)
        for damage in ('version', 'players', 'events', 'initial', 'coordinate', 'duplicate_capture',
                       'event_color', 'event_bool', 'config'):
            broken = deepcopy(trace)
            if damage == 'version':
                broken['format'] = 'omok-game-v99'
            elif damage in ('players', 'events', 'initial'):
                broken[damage] = None
            elif damage == 'coordinate':
                broken['moves'][0]['move'] = [0.0, 0]
            elif damage == 'duplicate_capture':
                broken['moves'][0]['captured'] = [{'cell': [1, 1], 'prior_value': 1}] * 2
            elif damage == 'event_color':
                broken['events'][1]['color'] = 0.0
            elif damage == 'event_bool':
                broken['events'][1]['state']['board'][0][0] = False
            else:
                broken['config']['seed'] = float('inf')
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                replay(broken)
        failed = run_game(ReturningPlayer(0, [(19, 0)]), ReturningPlayer(1, []))
        failed['events'][0]['move'] = [0, 0]
        with self.assertRaises(ValueError):
            replay(failed)

    def test_capture_game_replays_and_damaged_or_truncated_trace_is_rejected(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][5:11] = [1] * 6
        board[10][10], board[11][10] = 1, 0
        trace = run_game(ReturningPlayer(0, [(8, 10)]), ReturningPlayer(1, []),
                         initial=Position(board, 0))
        self.assertEqual(replay(trace).board, Position(trace['final']['board'], 0).board)
        for damage in ('capture', 'board', 'color', 'truncate', 'status', 'reason', 'clock'):
            broken = deepcopy(trace)
            if damage == 'capture':
                broken['moves'][0]['captured'] = []
            elif damage == 'board':
                broken['final']['board'][9][10] = 1
            elif damage == 'color':
                broken['moves'][0]['color'] = 1
            elif damage == 'truncate':
                del broken['final']
            elif damage == 'status':
                broken['status'] = 'capped'
            elif damage == 'reason':
                broken['reason'] = 'full_board'
            else:
                broken['remaining_ms'][0] = 99999
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                replay(broken)

    def test_capped_and_failed_traces_replay_without_fabricating_a_rules_result(self):
        for move, cap in (((0, 0), 1), ((19, 0), 10)):
            trace = run_game(ReturningPlayer(0, [move]), ReturningPlayer(1, []), move_cap=cap)
            self.assertEqual(replay(trace).outcome, 'ongoing')
            self.assertIsNone(trace['winner'])

    def test_malformed_boolean_integers_are_rejected_in_final_state_and_captures(self):
        board = [[-1] * 19 for _ in range(19)]
        board[9][5:11] = [1] * 6
        board[10][10], board[11][10] = 1, 0
        trace = run_game(ReturningPlayer(0, [(8, 10)]), ReturningPlayer(1, []),
                         initial=Position(board, 0))
        for damage in ('cell', 'winner', 'capture'):
            broken = deepcopy(trace)
            if damage == 'cell':
                broken['final']['board'][8][10] = False
            elif damage == 'winner':
                broken['winner'] = True
            else:
                broken['moves'][0]['captured'][0]['prior_value'] = True
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                replay(broken)


if __name__ == '__main__':
    unittest.main()
