# AI-written by OpenAI Codex, for issue #31.
import unittest
from copy import deepcopy

from offline.replay import replay
from offline.supervised import PlayerSpec, run_supervised_game
from offline.runner import run_game
from offline.fixtures import fixture
from tests.test_runner import ReturningPlayer


class InspectionTests(unittest.TestCase):
    def test_unattributed_infrastructure_and_unmeasured_cleanup_remain_inspectable(self):
        from offline.inspection import inspect_loss
        spec = PlayerSpec('tests.test_supervised', 'StatefulPlayer')
        for reason in ('supervisor_error', 'cleanup_error'):
            trace = run_supervised_game(spec, spec, move_cap=0)
            if reason == 'cleanup_error':
                trace['prior_result'] = {key: trace[key] for key in ('status', 'reason', 'failure')}
                trace['workers'][0].update(pid=123, startup_ms=1, reaped=False,
                    cleanup_ms=None, cleanup_error='controlled close failure')
            failure = {'color': None, 'player': None, 'reason': reason, 'violations': [reason],
                       'called': False, 'elapsed_ms': 0, 'returned': None,
                       'exception': None, 'detail': 'controlled infrastructure fact'}
            trace.update(status='supervisor_error', reason=reason, failure=failure)
            trace['events'].append({'type': 'failure', **failure, 'remaining_ms': None})
            with self.subTest(reason=reason):
                self.assertEqual(replay(trace).outcome, 'ongoing')
                self.assertEqual(inspect_loss(trace)['positions'], [])

    def test_capture_results_export_before_move_and_confirm_only_checked_expectations(self):
        from offline.inspection import inspect_loss, checked_fixture, verify_fixture
        for name, outcome, reason in (('mover-win', 'black_win', 'exact_five'),
                                     ('opponent-win', 'white_win', 'exact_five'),
                                     ('simultaneous', 'draw', 'simultaneous_wins')):
            trace = run_game(ReturningPlayer(0, [(8, 10)]), ReturningPlayer(1, []), initial=fixture(name))
            with self.subTest(name=name):
                record = inspect_loss(trace, color=0)['positions'][0]
                self.assertEqual(record['position']['board'][8][10], -1)
                self.assertEqual(record['chosen_move'], [8, 10])
                self.assertEqual(replay(trace).outcome, outcome)
                checked = checked_fixture(trace, ply=0, color=0,
                    expected_outcome=outcome, expected_reason=reason)
                verify_fixture(checked)
                with self.assertRaises(ValueError):
                    checked_fixture(trace, ply=0, color=0, expected_outcome='ongoing', expected_reason=None)

    def test_bounded_exports_reject_bad_selections_and_execution_assertions(self):
        from offline.inspection import inspect_loss, checked_fixture
        trace = run_game(ReturningPlayer(0, [(0, 0), (0, 1)]),
                         ReturningPlayer(1, [(1, 0), (1, 1)]), move_cap=4)
        record = inspect_loss(trace, color=0, max_positions=1, history_limit=1)['positions'][0]
        self.assertEqual(record['ply'], 2)
        self.assertEqual(record['preceding_moves'][0]['move'], [1, 0])
        self.assertEqual(len(record['preceding_moves']), 1)
        for kwargs in ({'max_positions': 0}, {'plies': [0, 0]}, {'plies': [1]}, {'plies': [99]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                inspect_loss(trace, color=0, **kwargs)
        failed = run_game(ReturningPlayer(0, [(19, 0)]), ReturningPlayer(1, []))
        with self.assertRaises(ValueError):
            checked_fixture(failed, ply=0, color=0, expected_outcome='black_win', expected_reason='exact_five')

    def test_export_preserves_position_before_failed_call_and_diagnostics(self):
        from offline.inspection import inspect_loss
        specs = [PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
                 PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'raise'})]
        trace = run_supervised_game(*specs, move_cap=4, diagnostics=True)
        report = inspect_loss(trace)
        record = report['positions'][0]
        self.assertEqual(record['ply'], 1)
        self.assertEqual(record['color'], 1)
        self.assertEqual(record['position']['board'][0][0], 0)
        self.assertEqual(record['chosen_move'], None)
        self.assertEqual(record['preceding_moves'][0]['move'], [0, 0])
        self.assertEqual(record['player']['spec']['options'], {'behavior': 'raise'})
        self.assertEqual(record['clocks_before_ms'][1], 60000)
        self.assertEqual(record['execution']['reason'], 'exception')
        self.assertEqual(record['tags'][0]['status'], 'hypothesis')
        self.assertEqual(report['board_outcome'], 'ongoing')

    def test_supervision_evidence_is_versioned_and_required(self):
        spec = PlayerSpec('tests.test_supervised', 'StatefulPlayer')
        trace = run_supervised_game(spec, spec, move_cap=2, diagnostics=True)
        self.assertEqual(trace['format'], 'omok-game-v4')
        self.assertEqual(replay(trace).side_to_move, 0)
        for field in ('supervision', 'workers', 'spec', 'timing', 'truncated', 'diagnostics'):
            broken = deepcopy(trace)
            if field in ('supervision', 'workers'):
                del broken[field]
            elif field == 'spec':
                del broken['players'][0]['spec']
            elif field == 'timing':
                broken['events'][0]['overhead_ms'] = -1
            elif field == 'truncated':
                broken['events'].pop()
            else:
                broken['events'][0]['search'] = []
            with self.subTest(field=field), self.assertRaises(ValueError):
                replay(broken)
        legacy = deepcopy(trace)
        legacy['format'] = 'omok-game-v3'
        self.assertEqual(replay(legacy).side_to_move, 0)
