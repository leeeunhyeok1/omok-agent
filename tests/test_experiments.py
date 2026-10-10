# AI-written by OpenAI Codex, for issue #27.
import tempfile
import unittest
from pathlib import Path

from offline.registry import Entry, PoolSnapshot
from offline.experiments import ExperimentPlan, run_experiment


def entry(name, *, seed_support='constructor', options=None):
    return Entry.local(name, module='offline.worker_players', factory='create',
        options=options or {'name': 'smoke'}, source_paths=('omok', 'offline'),
        origin='synthetic', family=name, acknowledgment='Controlled local test player',
        seed_support=seed_support)


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.candidate = entry('candidate')
        self.opponent = entry('opponent')
        self.snapshot = PoolSnapshot.freeze({'training': [self.opponent], 'validation': [], 'holdout': []})

    def test_official_plan_saves_and_recreates_all_eight_slots(self):
        plan = ExperimentPlan.resolve(self.candidate, self.snapshot, mode='official')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            plan.save(path)
            restored = ExperimentPlan.load(path)
            self.assertEqual(restored.record(), plan.record())
            with self.assertRaises(FileExistsError):
                plan.save(path)
        jobs = restored.data['jobs']
        self.assertEqual(len(jobs), 8)
        self.assertEqual([j['candidate_color'] for j in jobs], [0, 1, 0, 1, 0, 1, 0, 1])
        self.assertEqual(len({j['game_id'] for j in jobs}), 8)
        self.assertEqual(len({j['match_id'] for j in jobs}), 1)
        self.assertEqual(restored.data['settings']['budgets_ms'], [60000, 60000])
        for a, b in zip(jobs[::2], jobs[1::2]):
            self.assertEqual(a['seeds'], b['seeds'])
            self.assertNotEqual(a['seeds']['candidate'], a['seeds']['opponent'])
            self.assertEqual(a['opening'], b['opening'])
            self.assertEqual(a['opening']['side_to_move'], 0)
            self.assertTrue(all(cell == -1 for row in a['opening']['board'] for cell in row))

    def test_paired_legal_openings_and_version_changes_have_reproducible_ids(self):
        options = dict(mode='development', seed=17, games_per_opponent=4,
                       openings=[[[9, 9]], [[2, 2], [3, 3]]])
        a = ExperimentPlan.resolve(self.candidate, self.snapshot, **options)
        b = ExperimentPlan.resolve(self.candidate, self.snapshot, **options)
        self.assertEqual(a.data['jobs'], b.data['jobs'])
        jobs = a.data['jobs']
        self.assertEqual([j['opening']['side_to_move'] for j in jobs], [1, 1, 0, 0])
        self.assertEqual(jobs[0]['opening']['board'][9][9], 0)
        for changes in ({'seed': 18}, {'total_ms': 100}, {'openings': [[[4, 4]]]}):
            changed = ExperimentPlan.resolve(self.candidate, self.snapshot, **(options | changes))
            self.assertNotEqual(jobs[0]['game_id'], changed.data['jobs'][0]['game_id'])
        changed = ExperimentPlan.resolve(entry('new-candidate'), self.snapshot, **options)
        self.assertNotEqual(jobs[0]['match_id'], changed.data['jobs'][0]['match_id'])
        with self.assertRaises(ValueError):
            ExperimentPlan.resolve(self.candidate, self.snapshot, openings=[[[9, 9], [9, 9]]])

    def test_serial_execution_keeps_capped_slots_and_records_actual_exposure(self):
        plan = ExperimentPlan.resolve(self.candidate, self.snapshot, games_per_opponent=2,
                                      move_cap=2, total_ms=None)
        result = run_experiment(plan)
        self.assertEqual(result['counts'], {'planned': 2, 'completed': 0, 'failed': 0,
                                           'capped': 2, 'pending': 0, 'infrastructure_failed': 0})
        self.assertEqual([r['game_id'] for r in result['results']],
                         [j['game_id'] for j in plan.data['jobs']])
        for record in result['results']:
            self.assertEqual(record['trace']['reason'], 'move_cap')
            self.assertIsNone(record['trace']['winner'])
            self.assertEqual(record['exposure']['turns_called'], [1, 1])
            self.assertEqual(record['exposure']['pool'], 'training')
            registry = record['trace']['config']['registry']
            self.assertEqual(registry['pool_snapshot'], plan.data['pool_snapshot'])
            self.assertEqual(len(registry['preflight']), 4)
            self.assertEqual(registry['candidate']['identity'], self.candidate.identity)
            from offline.replay import replay
            replay(record['trace'])

    def test_modes_reject_incompatible_policies_and_disclose_duplicate_evidence(self):
        from offline.fixtures import fixture
        deterministic = entry('deterministic', seed_support='deterministic', options={'name': 'baseline'})
        other = entry('other', seed_support='deterministic', options={'name': 'baseline'})
        snapshot = PoolSnapshot.freeze({'training': [other], 'validation': [], 'holdout': []})
        plan = ExperimentPlan.resolve(deterministic, snapshot)
        jobs = plan.data['jobs']
        self.assertEqual(jobs[0]['duplicate_evidence_group'], jobs[2]['duplicate_evidence_group'])
        self.assertNotEqual(jobs[0]['duplicate_evidence_group'], jobs[1]['duplicate_evidence_group'])
        self.assertEqual(len(jobs[0]['seed_limitations']), 2)
        unsupported = ExperimentPlan.resolve(entry('unseeded', seed_support='unsupported'), snapshot)
        self.assertIn('candidate: unsupported', unsupported.data['jobs'][0]['seed_limitations'])
        for changes in ({'total_ms': 100}, {'games_per_opponent': 2}, {'openings': [[[1, 1]]]}):
            with self.assertRaisesRegex(ValueError, 'Official'):
                ExperimentPlan.resolve(self.candidate, self.snapshot, mode='official', **changes)
        with self.assertRaisesRegex(ValueError, 'Screening'):
            ExperimentPlan.resolve(self.candidate, self.snapshot, mode='screening')
        screening = ExperimentPlan.resolve(self.candidate, self.snapshot, mode='screening', total_ms=100)
        self.assertEqual(screening.data['settings']['budget_mechanism'], 'reduced-total-wall-clock')
        tactical = ExperimentPlan.resolve(self.candidate, self.snapshot, mode='fixture',
                                          fixture=fixture('mover-win'), games_per_opponent=2, move_cap=0)
        self.assertEqual(tactical.data['jobs'][0]['opening']['kind'], 'artificial-fixture')
        self.assertEqual(run_experiment(tactical)['results'][0]['exposure']['kind'], 'no-player-turns')

    def test_rehashed_corrupt_schedule_and_protected_holdout_are_rejected(self):
        from offline.registry import digest
        plan = ExperimentPlan.resolve(self.candidate, self.snapshot)
        for field, value in (('games_per_opponent', 3), ('mode', 'unknown')):
            record = plan.record()
            record['settings'][field] = value
            record['identity'] = digest({k: v for k, v in record.items() if k != 'identity'})
            with self.assertRaises(ValueError):
                ExperimentPlan.from_record(record)
        holdout = entry('reserved')
        snapshot = PoolSnapshot.freeze({'training': [self.opponent], 'validation': [], 'holdout': [holdout]})
        plan = ExperimentPlan.resolve(self.candidate, snapshot)
        self.assertEqual(len(plan.data['jobs']), 8)
        with self.assertRaisesRegex(ValueError, 'protected'):
            ExperimentPlan.resolve(self.candidate, snapshot, opponents=['reserved'])
        final = ExperimentPlan.resolve(self.candidate, snapshot, purpose='final-evaluation', opponents=['reserved'])
        self.assertEqual(final.data['jobs'][0]['pool'], 'holdout')

    def test_failure_and_setup_error_preserve_every_slot_and_continue(self):
        from offline.registry import ROOT
        from offline.supervised import Supervision
        with tempfile.TemporaryDirectory(dir=ROOT / '.scratch') as directory:
            root = Path(directory)
            (root / 'bot.py').write_text('class Bot:\n def __init__(self,color): self.color=color\n def take_turn(self,board,time): raise RuntimeError("controlled crash")\n')
            crashing = Entry.local('crash', module='bot', factory='Bot', source_root=root,
                source_paths=('.',), origin='synthetic', family='crasher', acknowledgment='Test fixture')
            plan = ExperimentPlan.resolve(crashing, self.snapshot, games_per_opponent=2, move_cap=4)
            self.assertFalse(Path(plan.data['candidate']['loader']['root']).is_absolute())
            result = run_experiment(plan)
            self.assertEqual(result['counts']['failed'], 2)
            self.assertEqual([r['trace']['failure']['color'] for r in result['results']], [0, 1])
            self.assertTrue(all(r['trace']['reason'] == 'exception' for r in result['results']))
            (root / 'bot.py').write_text('CHANGED=True\n')
            result = run_experiment(plan)
            self.assertEqual(result['counts']['infrastructure_failed'], 2)
            self.assertTrue(all(r['exposure']['turns_called'] == [0, 0] for r in result['results']))
            (root / 'bot.py').write_text('class Bot:\n def __init__(self,color): self.color=color\n def take_turn(self,board,time):\n  while True: pass\n')
            looping = Entry.local('loop', module='bot', factory='Bot', source_root=root,
                source_paths=('.',), origin='synthetic', family='loop', acknowledgment='Test fixture')
            plan = ExperimentPlan.resolve(looping, self.snapshot, games_per_opponent=2, total_ms=None,
                move_cap=4, supervision=Supervision(unlimited_call_ms=40))
            result = run_experiment(plan)
            self.assertEqual(result['counts']['capped'], 2)
            self.assertTrue(all(r['trace']['reason'] == 'unlimited_call_cap' for r in result['results']))
            self.assertTrue(all(r['trace']['winner'] is None for r in result['results']))

    def test_saved_plan_cli_runs_and_preserves_evidence(self):
        import json
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / 'registry.json'
            registry.write_text(json.dumps({'format': 'omok-registry-v1',
                'entries': [self.candidate.record(), self.opponent.record()],
                'pool_snapshot': self.snapshot.record()}))
            base = [sys.executable, '-m', 'offline.experiment_cli']
            planned = subprocess.run(base + ['plan', '--registry', str(registry),
                '--candidate', 'candidate', '--mode', 'screening', '--total-ms', '100',
                '--games', '2', '--move-cap', '1', '--output', str(root / 'plan.json')],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(planned.returncode, 0, planned.stderr)
            executed = subprocess.run(base + ['run', '--plan', str(root / 'plan.json'),
                '--output', str(root / 'run')], capture_output=True, text=True, timeout=15)
            self.assertEqual(executed.returncode, 0, executed.stderr)
            saved = json.loads((root / 'run' / 'results.json').read_text())
            self.assertEqual(saved['counts']['planned'], 2)
            self.assertEqual(saved['counts']['capped'], 2)
            again = subprocess.run(base + ['run', '--plan', str(root / 'plan.json'),
                '--output', str(root / 'run')], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(again.returncode, 0)

    def test_unavailable_candidate_is_rejected_before_dispatch(self):
        pending = Entry.local('pending', module='offline.worker_players', factory='create',
            options={'name': 'smoke'}, source_paths=('omok', 'offline'),
            origin='synthetic', family='pending', acknowledgment='Test fixture', availability='pending')
        with self.assertRaisesRegex(ValueError, 'pending'):
            ExperimentPlan.resolve(pending, self.snapshot)
