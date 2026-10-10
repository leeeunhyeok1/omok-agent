# AI-written by OpenAI Codex, for issue #33.
import unittest
import json
import gzip
import subprocess
import sys
import tempfile
from pathlib import Path

from offline.experiments import ExperimentPlan, run_experiment
from offline.registry import PoolSnapshot
from offline.reports import report_experiment
from tests.test_experiments import entry
from tests import test_matches


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_matches.MatchTests()
        self.fixture.setUp()
        self.plan = self.fixture.plan

    def test_saved_results_keep_crashes_partial_matches_and_clean_denominators(self):
        raw = self.fixture.results(['win'] * 6 + ['loss', 'draw'])
        self.fixture.fail_slot(raw, 0, 'candidate')
        raw['results'].pop()
        report = report_experiment(self.plan, raw)
        self.assertEqual(report['jobs']['counts'], dict(planned=8, completed=6,
            failed=1, capped=0, infrastructure_failed=0, pending=1))
        self.assertEqual(report['jobs']['recognized']['losses'], 2)
        self.assertEqual(report['clean_games']['counts']['completed'], 6)
        self.assertEqual(report['clean_games']['recognized']['win_rate'],
                         {'numerator': 5, 'denominator': 6, 'value': 5 / 6})
        self.assertEqual(report['matches'][0]['tournament']['outcome'], 'unresolved')
        self.assertIsNone(report['matches'][0]['tournament']['coins'])
        self.assertFalse(report['matches'][0]['qualification']['qualified'])
        self.assertEqual(report['opponents'][0]['jobs']['by_color']['black']['recognized']['losses'], 2)

    def test_attempt_history_preserves_retries_and_deduplicates_identical_deliveries(self):
        raw = self.fixture.results(['win', 'loss'])
        first, second = raw['results']
        first.update(attempt_id='a2', segment='new')
        second.update(attempt_id='b1', segment='old')
        previous = {**first, 'attempt_id': 'a1', 'segment': 'old', 'status': 'setup_failed',
                    'trace': None, 'error': {'type': 'ImportError', 'message': 'unavailable'}}
        raw['attempts'] = [dict(game_id=first['game_id'], attempt_id='a1', segment='old',
            state='committed', result=previous), dict(game_id=first['game_id'], attempt_id='a2',
            segment='new', state='committed', result=first), dict(game_id=second['game_id'],
            attempt_id='b1', segment='old', state='committed', result=second),
            dict(game_id=self.plan.data['jobs'][2]['game_id'], attempt_id='c1', segment='new', state='interrupted')]
        raw['attempts'].append(raw['attempts'][0].copy())
        report = report_experiment(self.plan, raw)
        self.assertEqual(report['jobs']['counts']['completed'], 2)
        self.assertEqual(report['all_attempts']['total'], 4)
        self.assertEqual(report['all_attempts']['committed']['counts']['infrastructure_failed'], 1)
        self.assertEqual(report['all_attempts']['interrupted'], 1)
        self.assertEqual(report['all_attempts']['duplicate_deliveries'], 1)
        self.assertEqual(report['all_attempts']['committed']['recognized']['win_rate']['denominator'], 2)
        self.assertEqual(report['opponents'][0]['all_attempts']['total'], 4)
        raw['attempts'][-1] = {**raw['attempts'][-1], 'state': 'running'}
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            report_experiment(self.plan, raw)

    def test_metrics_do_not_count_returned_and_applied_events_twice_or_invent_diagnostics(self):
        raw = self.fixture.results(['win', 'loss'])
        report = report_experiment(self.plan, raw)
        metrics = report['metrics']['latest_jobs']
        self.assertEqual(metrics['game_length']['samples'], 2)
        self.assertEqual(metrics['game_length']['mean'], 1)
        self.assertEqual(metrics['candidate']['turn_ms']['samples'], 1)
        self.assertEqual(metrics['opponent']['turn_ms']['samples'], 1)
        self.assertEqual(metrics['candidate']['diagnostics']['nodes']['samples'], 0)
        self.assertIsNone(metrics['candidate']['diagnostics']['nodes']['mean'])
        raw['results'][0]['trace']['events'][0]['search'] = {
            'nodes': 17, 'completed_depth': 2, 'evaluation_calls': 9,
            'evaluation_profile': {'sampled_calls': 3}}
        measured = report_experiment(self.plan, raw)['metrics']['latest_jobs']
        self.assertEqual(measured['candidate']['diagnostics']['nodes']['mean'], 17)
        self.assertEqual(measured['candidate']['diagnostics']['evaluation_profile.sampled_calls']['mean'], 3)
        self.assertEqual(measured['opponent']['diagnostics']['nodes']['missing'], 1)
        self.assertEqual(measured['candidate']['remaining_ms']['samples'], 2)

    def test_micro_macro_family_coverage_and_deterministic_duplicate_limits(self):
        plan = ExperimentPlan.resolve(entry('candidate', seed_support='deterministic'),
            PoolSnapshot.freeze({'training': [entry('first', seed_support='deterministic'),
                entry('second', seed_support='deterministic')], 'validation': [], 'holdout': []}),
            mode='fixture', fixture=test_matches.scoring_start(), move_cap=2)
        records = []
        for job in plan.data['jobs'][:10]:
            winner = job['candidate_color'] if job['slot'] < 4 and job['opponent']['logical_id'] == 'first' else 1 - job['candidate_color']
            trace = test_matches.terminal_trace(winner)
            records.append({k: job[k] for k in ('game_id', 'match_id', 'slot', 'candidate_color')} |
                           dict(status=trace['status'], trace=trace, error=None))
        report = report_experiment(plan, dict(format='omok-experiment-results-v1',
            manifest_identity=plan.identity, results=records))
        self.assertEqual(report['averages']['micro']['value'], .4)
        self.assertEqual(report['averages']['equal_opponent_macro']['value'], .25)
        self.assertEqual(report['averages']['equal_opponent_macro']['denominator'], 2)
        self.assertEqual(report['weak_matchups'][0]['logical_id'], 'second')
        self.assertEqual(report['coverage']['families']['first']['planned_jobs'], 8)
        self.assertEqual(len(report['coverage']['duplicate_evidence_groups']), 4)
        self.assertEqual(report['rating']['status'], 'deferred')
        self.assertFalse(report['uncertainty']['independent_trials_assumed'])
        self.assertFalse(report['ordinary_strength_evidence'])

    def test_saved_batch_cli_reports_caps_and_changed_segments_separately(self):
        plan = ExperimentPlan.resolve(entry('candidate'), PoolSnapshot.freeze({
            'training': [entry('opponent')], 'validation': [], 'holdout': []}),
            mode='screening', games_per_opponent=2, move_cap=0, total_ms=100)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            run_experiment(plan, output=output, max_jobs=1, workers=2)
            raw = run_experiment(plan, output=output, resume=True, workers=1)
            report_path = Path(directory) / 'report.json'
            completed = subprocess.run([sys.executable, '-m', 'offline.experiment_cli', 'report',
                '--plan', str(output / 'manifest.json'), '--results', str(output / 'results.json'),
                '--output', str(report_path)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(report_path.read_text())
            self.assertEqual(report['jobs']['counts']['capped'], 2)
            self.assertIsNone(report['averages']['micro']['value'])
            self.assertEqual(len(report['execution_segments']), 2)
            self.assertEqual(report['execution_segments'][0]['metrics']['records'], 1)
            self.assertEqual(report['execution_segments'][1]['metrics']['records'], 1)
            self.assertEqual(report['execution_segments'][1]['evidence']['conditions'], raw['segments'][1]['conditions'])
            self.assertIsNone(report['matches'][0]['tournament']['coins'])

    def test_committed_known_results_cover_failures_caps_retries_and_runtime_changes(self):
        path = Path(__file__).resolve().parents[1] / 'docs/verification/issue-33/known-results.json.gz'
        evidence = json.loads(gzip.decompress(path.read_bytes()))
        report = report_experiment(ExperimentPlan.from_record(evidence['plan']), evidence['raw'])
        self.assertEqual(report['jobs']['counts'], dict(planned=8, completed=4,
            failed=1, capped=1, infrastructure_failed=1, pending=1))
        self.assertEqual(report['jobs']['recognized']['win_rate'], dict(numerator=2, denominator=5, value=.4))
        self.assertEqual(report['clean_games']['recognized']['win_rate']['value'], .5)
        self.assertEqual(report['all_attempts']['total'], 9)
        self.assertEqual(report['all_attempts']['duplicate_deliveries'], 1)
        self.assertEqual(report['all_attempts']['committed']['counts']['infrastructure_failed'], 2)
        self.assertEqual(report['execution_segments'][1]['evidence']['changed_conditions'], ['workers', 'hardware'])
        self.assertIsNone(report['metrics']['latest_jobs']['candidate']['diagnostics']['nodes']['mean'])
        self.assertIsNone(report['matches'][0]['tournament']['coins'])

    def test_invalid_trace_cannot_supply_strength_or_timing_and_history_must_agree(self):
        raw = self.fixture.results(['win'])
        raw['results'][0]['trace']['final']['board'][0][0] = 1
        report = report_experiment(self.plan, raw)
        self.assertEqual(report['jobs']['counts']['infrastructure_failed'], 1)
        self.assertEqual(report['metrics']['latest_jobs']['validated_traces'], 0)
        self.assertIsNone(report['averages']['micro']['value'])
        raw['attempts'] = []
        with self.assertRaisesRegex(ValueError, 'disagree'):
            report_experiment(self.plan, raw)


if __name__ == '__main__':
    unittest.main()
