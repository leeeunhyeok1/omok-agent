# AI-written by OpenAI Codex, for issue #28.
import copy
import unittest

from offline.experiments import ExperimentPlan
from offline.matches import score_experiment
from offline.registry import Entry, PoolSnapshot
from offline.runner import run_game
from omok.player import LegalBaseline
from omok.simulator import Position
from tests.test_experiments import entry


def scoring_start():
    board = [[-1] * 19 for _ in range(19)]
    board[2][:4] = [0] * 4
    board[8][6:10] = [0] * 4
    board[9][5:11] = [1] * 6
    board[10][10], board[11][10] = 1, 0
    board[8][5], board[10][5] = 1, 0
    return Position(board, 0)


class MovePlayer:
    def __init__(self, color, move):
        self.color, self.move = color, move

    def take_turn(self, board, time):
        return self.move


def terminal_trace(winner):
    # Known rule fixtures: black completes a separate five; black captures the
    # left end of white's overline; or black makes both colors exactly five.
    move = {0: (2, 4), 1: (7, 5), None: (8, 10)}[winner]
    return run_game(MovePlayer(0, move), MovePlayer(1, (0, 1)),
                    initial=scoring_start(), move_cap=2)


class FailurePlayer:
    def __init__(self, color, reason):
        self.color, self.reason = color, reason

    def take_turn(self, board, time):
        if self.reason == 'exception':
            raise RuntimeError('controlled crash')
        if self.reason == 'mutation':
            board[0][0] = self.color
        return (-1, -1)


class MatchTests(unittest.TestCase):
    def setUp(self):
        snapshot = PoolSnapshot.freeze({'training': [entry('opponent')], 'validation': [], 'holdout': []})
        self.plan = ExperimentPlan.resolve(entry('candidate'), snapshot, mode='fixture',
                                          fixture=scoring_start(), move_cap=2)

    def results(self, outcomes):
        records = []
        for job, outcome in zip(self.plan.data['jobs'], outcomes):
            color = job['candidate_color']
            trace = terminal_trace(color if outcome == 'win' else 1 - color if outcome == 'loss' else None)
            records.append({k: job[k] for k in ('game_id', 'match_id', 'slot', 'candidate_color')} |
                           {'status': trace['status'], 'trace': trace, 'error': None})
        return {'format': 'omok-experiment-results-v1', 'manifest_identity': self.plan.identity,
                'results': records}

    def score(self, raw):
        return score_experiment(self.plan, raw)['matches'][0]

    def fail_slot(self, raw, index, role, reason='exception'):
        job = self.plan.data['jobs'][index]
        color = job['candidate_color'] if role == 'candidate' else 1 - job['candidate_color']
        players = [MovePlayer(0, (0, 0)), MovePlayer(1, (0, 1))]
        players[color] = FailurePlayer(color, reason)
        ticks = iter([0, 61] if color == 0 else [0, 0, 0, 61])
        options = {'clock': lambda: next(ticks)} if reason == 'timeout' else {}
        trace = run_game(*players, initial=scoring_start(), move_cap=2, **options)
        raw['results'][index].update(trace=trace, status=trace['status'])

    def test_threshold_tournament_and_coins_are_separate(self):
        table = [(5, 3, 0, True, 'win', [2, 0]),
                 (4, 3, 1, False, 'win', [2, 0]),
                 (4, 4, 0, False, 'draw', [1, 1]),
                 (3, 4, 1, False, 'loss', [0, 2]),
                 (0, 0, 8, False, 'draw', [1, 1])]
        for wins, losses, draws, qualifies, outcome, coins in table:
            with self.subTest(wins=wins, losses=losses, draws=draws):
                raw = self.results(['win'] * wins + ['loss'] * losses + ['draw'] * draws)
                before = copy.deepcopy(raw)
                match = self.score(raw)
                self.assertEqual(match['recognized'], {'candidate_wins': wins, 'opponent_wins': losses, 'draws': draws})
                self.assertEqual(match['qualification']['qualified'], qualifies)
                self.assertEqual(match['tournament']['outcome'], outcome)
                self.assertEqual(match['tournament']['coins'], coins)
                self.assertEqual(match['counts']['planned'], 8)
                self.assertEqual(match['colors'], [4, 4])
                self.assertEqual(raw, before)

    def test_missing_capped_and_infrastructure_slots_are_unresolved(self):
        complete = self.results(['win'] * 8)
        capped = run_game(MovePlayer(0, (0, 0)), MovePlayer(1, (0, 1)),
                          initial=scoring_start(), move_cap=2)
        for kind in ('pending', 'capped', 'setup_failed', 'invalid_trace'):
            with self.subTest(kind=kind):
                raw = copy.deepcopy(complete)
                last = raw['results'][-1]
                if kind == 'pending':
                    raw['results'].pop()
                elif kind == 'capped':
                    last.update(trace=capped, status='capped')
                elif kind == 'setup_failed':
                    last.update(trace=None, status='setup_failed', error={'message': 'missing dependency'})
                else:
                    last['trace']['winner'] = 7
                match = self.score(raw)
                self.assertIsNone(match['qualification']['qualified'])
                self.assertEqual(match['tournament'], {'outcome': 'unresolved', 'coins': None, 'override': None})
                self.assertFalse(match['complete'])
                self.assertEqual(len(match['slots']), 8)
                self.assertEqual(match['recognized']['draws'], 0)
                self.assertIn({'pending': 'incomplete', 'capped': 'capped',
                    'setup_failed': 'infrastructure_invalid', 'invalid_trace': 'infrastructure_invalid'}[kind], match['flags'])

    def test_non_eight_game_plan_has_no_match_coins(self):
        snapshot = PoolSnapshot.from_record(self.plan.data['pool_snapshot'])
        self.plan = ExperimentPlan.resolve(entry('candidate'), snapshot, games_per_opponent=6,
            mode='fixture', fixture=scoring_start(), move_cap=2)
        match = self.score(self.results(['win'] * 6))
        self.assertEqual(match['colors'], [3, 3])
        self.assertIn('invalid_schedule', match['flags'])
        self.assertIsNone(match['tournament']['coins'])

    def test_foreign_duplicate_or_misassigned_results_are_rejected(self):
        for kind in ('manifest', 'duplicate', 'foreign', 'color', 'slot', 'match'):
            with self.subTest(kind=kind):
                raw = self.results(['win'] * 8)
                if kind == 'manifest':
                    raw['manifest_identity'] = 'other'
                elif kind == 'duplicate':
                    raw['results'].append(copy.deepcopy(raw['results'][0]))
                else:
                    key = {'foreign': 'game_id', 'color': 'candidate_color', 'slot': 'slot', 'match': 'match_id'}[kind]
                    raw['results'][0][key] = 'wrong'
                with self.assertRaises(ValueError):
                    self.score(raw)

    def test_crash_overrides_raw_lead_but_never_creates_five_strict_wins(self):
        raw = self.results(['win'] * 6 + ['loss'] * 2)
        self.fail_slot(raw, 7, 'candidate')
        match = self.score(raw)
        self.assertEqual(match['rules_score'], {'candidate_wins': 6, 'opponent_wins': 1, 'draws': 0})
        self.assertEqual(match['recognized'], {'candidate_wins': 6, 'opponent_wins': 2, 'draws': 0})
        self.assertFalse(match['qualification']['qualified'])
        self.assertEqual(match['tournament'], {'outcome': 'loss', 'coins': [0, 2], 'override': 'candidate_crash'})
        raw = self.results(['win'] * 2 + ['loss'] * 6)
        self.fail_slot(raw, 7, 'opponent')
        match = self.score(raw)
        self.assertEqual(match['recognized']['opponent_wins'], 5)
        self.assertFalse(match['qualification']['qualified'])
        self.assertEqual(match['tournament'], {'outcome': 'win', 'coins': [2, 0], 'override': 'opponent_crash'})
        self.fail_slot(raw, 6, 'candidate')
        match = self.score(raw)
        self.assertIn('both_crash', match['flags'])
        self.assertIsNone(match['tournament']['coins'])
        self.assertEqual(match['tournament']['outcome'], 'unresolved')
        self.assertFalse(match['qualification']['qualified'])

    def test_other_player_failures_are_game_forfeits_without_crash_override(self):
        for reason in ('timeout', 'invalid_move', 'mutation'):
            for role in ('candidate', 'opponent'):
                with self.subTest(reason=reason, role=role):
                    raw = self.results(['win'] * 6 + ['loss'] * 2)
                    self.fail_slot(raw, 7, role, reason)
                    match = self.score(raw)
                    self.assertTrue(match['qualification']['qualified'])
                    self.assertEqual(match['tournament']['outcome'], 'win')
                    self.assertIsNone(match['tournament']['override'])
                    self.assertEqual(match['crashes'], {'candidate': False, 'opponent': False})
                    self.assertEqual(match['counts']['failed'], 1)

    def test_run_persists_separate_match_scores_and_cli_can_rescore_partial_results(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        from offline.experiments import run_experiment
        snapshot = PoolSnapshot.from_record(self.plan.data['pool_snapshot'])
        self.plan = ExperimentPlan.resolve(entry('candidate'), snapshot, move_cap=0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = run_experiment(self.plan, output=root / 'run')
            saved = json.loads((root / 'run' / 'match-scores.json').read_text())
            self.assertEqual(saved, run['match_scores'])
            self.assertIn('capped', saved['matches'][0]['flags'])
            self.assertFalse(saved['official_format'])
            raw = json.loads((root / 'run' / 'results.json').read_text())
            raw['results'].pop()
            (root / 'partial.json').write_text(json.dumps(raw))
            command = [sys.executable, '-m', 'offline.experiment_cli', 'score',
                '--plan', str(root / 'run' / 'manifest.json'), '--results', str(root / 'partial.json'),
                '--output', str(root / 'rescored.json')]
            scored = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(scored.returncode, 0, scored.stderr)
            partial = json.loads((root / 'rescored.json').read_text())['matches'][0]
            self.assertEqual(partial['counts']['pending'], 1)
            self.assertIsNone(partial['tournament']['coins'])
            repeat = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(repeat.returncode, 0)

    def test_supervised_late_exception_retains_crash_override_under_timeout(self):
        from offline.supervised import PlayerSpec, run_supervised_game
        ticks = iter([0, 61])
        trace = run_supervised_game(
            PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'raise'}),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), initial=scoring_start(), move_cap=2,
            clock=lambda: next(ticks))
        self.assertEqual(trace['reason'], 'timeout')
        raw = self.results(['win'] * 6 + ['loss'] * 2)
        raw['results'][0].update(status=trace['status'], trace=trace)
        match = self.score(raw)
        self.assertTrue(match['crashes']['candidate'])
        self.assertFalse(match['qualification']['qualified'])
        self.assertEqual(match['tournament']['override'], 'candidate_crash')
        self.assertEqual(match['tournament']['outcome'], 'loss')

    def test_complete_runner_scores_candidate_crashes_and_opponent_process_exits(self):
        from offline.experiments import run_experiment
        broken = Entry.local('broken', module='tests.test_supervised', factory='BrokenPlayer',
            source_paths=('omok', 'offline', 'tests'), options={'behavior': 'raise'},
            origin='synthetic', family='controlled-failure', acknowledgment='Controlled test player')
        snapshot = PoolSnapshot.from_record(self.plan.data['pool_snapshot'])
        plan = ExperimentPlan.resolve(broken, snapshot, mode='official')
        run = run_experiment(plan)
        match = run['match_scores']['matches'][0]
        self.assertEqual(match['counts']['failed'], 8)
        self.assertEqual(match['recognized'], {'candidate_wins': 0, 'opponent_wins': 8, 'draws': 0})
        self.assertFalse(match['qualification']['qualified'])
        self.assertEqual(match['tournament'], {'outcome': 'loss', 'coins': [0, 2], 'override': 'candidate_crash'})
        exited = Entry.local('exited', module='tests.test_supervised', factory='BrokenPlayer',
            source_paths=('omok', 'offline', 'tests'), options={'behavior': 'exit'},
            origin='synthetic', family='controlled-exit', acknowledgment='Controlled test player')
        snapshot = PoolSnapshot.freeze({'training': [exited], 'validation': [], 'holdout': []})
        run = run_experiment(ExperimentPlan.resolve(entry('candidate'), snapshot, mode='official'))
        match = run['match_scores']['matches'][0]
        self.assertEqual(match['counts']['failed'], 8)
        self.assertTrue(all(r['trace']['reason'] == 'player_exit' for r in run['results']))
        self.assertEqual(match['tournament'], {'outcome': 'win', 'coins': [2, 0], 'override': 'opponent_crash'})
        self.assertTrue(match['qualification']['qualified'])

    def test_cleanup_infrastructure_error_preserves_crash_but_awards_no_coins(self):
        import subprocess
        from unittest.mock import patch
        from offline.supervised import PlayerSpec, run_supervised_game
        original_wait = subprocess.Popen.wait
        calls = [0]

        def wait_then_fail(process, *args, **kwargs):
            result = original_wait(process, *args, **kwargs)
            calls[0] += 1
            if calls[0] == 1:
                raise OSError('controlled cleanup observation failure')
            return result

        with patch.object(subprocess.Popen, 'wait', wait_then_fail):
            trace = run_supervised_game(
                PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'raise'}),
                PlayerSpec('tests.test_supervised', 'StatefulPlayer'), initial=scoring_start(), move_cap=2)
        raw = self.results(['win'] * 8)
        raw['results'][0].update(status=trace['status'], trace=trace)
        match = self.score(raw)
        self.assertIn('infrastructure_invalid', match['flags'])
        self.assertTrue(match['crashes']['candidate'])
        self.assertFalse(match['qualification']['qualified'])
        self.assertIsNone(match['tournament']['coins'])

    def test_recorded_protocol_error_forfeits_only_its_game(self):
        from offline.supervised import PlayerSpec, run_supervised_game
        # A recorded broken-protocol event has the same clock/board ledger as
        # a closed player socket. Replay independently validates the specimen.
        trace = run_supervised_game(
            PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': 'exit'}),
            PlayerSpec('tests.test_supervised', 'StatefulPlayer'), initial=scoring_start(), move_cap=2)
        trace['reason'] = 'protocol_error'
        trace['failure'].update(reason='protocol_error', violations=['protocol_error'])
        trace['events'][-1].update(reason='protocol_error', violations=['protocol_error'])
        raw = self.results(['win'] * 8)
        raw['results'][0].update(status=trace['status'], trace=trace)
        match = self.score(raw)
        self.assertEqual(match['recognized'], {'candidate_wins': 7, 'opponent_wins': 1, 'draws': 0})
        self.assertEqual(match['crashes'], {'candidate': False, 'opponent': False})
        self.assertIsNone(match['tournament']['override'])
        self.assertEqual(match['tournament']['coins'], [2, 0])

    def test_trace_settings_must_match_saved_plan_and_unvalidated_prior_failures_are_rejected(self):
        for change in ('board', 'clock', 'cap', 'prior_null', 'prior_failure'):
            with self.subTest(change=change):
                raw = self.results(['win'] * 8)
                trace = raw['results'][0]['trace']
                if change == 'board':
                    trace = run_game(LegalBaseline(0), LegalBaseline(1), move_cap=2)
                    raw['results'][0].update(trace=trace, status=trace['status'])
                elif change == 'clock':
                    trace['budgets_ms'] = [50000, 50000]
                    trace['remaining_ms'] = [50000 - trace['moves'][0]['elapsed_ms'], 50000]
                    trace['moves'][0]['remaining_ms'] = trace['remaining_ms'][0]
                    for event in trace['events']:
                        event['remaining_ms'] = trace['remaining_ms'][0]
                elif change == 'cap':
                    trace['move_cap'] = 3
                else:
                    trace['prior_result'] = None if change == 'prior_null' else {
                        'status': 'failed', 'reason': 'exception', 'failure': {'color': 0,
                            'called': True, 'violations': ['exception'], 'exception': {'type': 'RuntimeError'}}}
                match = self.score(raw)
                self.assertIn('infrastructure_invalid', match['flags'])
                self.assertIsNone(match['qualification']['qualified'])
                self.assertIsNone(match['tournament']['coins'])
                self.assertFalse(match['crashes']['candidate'])
