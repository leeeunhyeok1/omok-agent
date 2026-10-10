# AI-written by OpenAI Codex, for issue #29.
import json
import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from offline.experiments import ExperimentPlan, run_experiment
from offline.registry import PoolSnapshot
from offline.registry import Entry, ROOT
from offline.registry import digest
from offline.batches import Checkpoint, atomic_json, owner
from tests.test_experiments import entry


class ControlledPlayer:
    def __init__(self, color, marker, behavior):
        self.color, self.marker, self.behavior = color, marker, behavior
        if behavior == 'setup_once' and not Path(marker).exists():
            Path(marker).write_text('setup failed once')
            raise RuntimeError('controlled infrastructure/setup failure')

    def take_turn(self, board, time):
        Path(self.marker).write_text(str(os.getpid()))
        if self.behavior == 'loop':
            while True:
                pass
        raise RuntimeError('controlled crash')


class BatchTests(unittest.TestCase):
    def plan(self, candidate=None, **options):
        return ExperimentPlan.resolve(candidate or entry('candidate'),
            PoolSnapshot.freeze({'training': [entry('opponent')], 'validation': [], 'holdout': []}),
            games_per_opponent=2, move_cap=0, **options)

    def test_resume_preserves_committed_job_and_progress(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            first = run_experiment(plan, output=output, max_jobs=1)
            self.assertEqual(first['counts']['pending'], 1)
            saved = (output / (plan.data['jobs'][0]['game_id'] + '.json')).read_bytes()
            resumed = run_experiment(plan, output=output, resume=True)
            self.assertEqual(resumed['counts']['capped'], 2)
            self.assertEqual(resumed['counts']['pending'], 0)
            self.assertEqual(len(resumed['attempts']), 2)
            self.assertEqual(saved, (output / (plan.data['jobs'][0]['game_id'] + '.json')).read_bytes())
            again = run_experiment(plan, output=output, resume=True)
            self.assertEqual(again['results'], resumed['results'])
            self.assertEqual(again['attempts'], resumed['attempts'])

    def test_resume_rejects_truncated_authoritative_checkpoint(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            run_experiment(plan, output=output, max_jobs=1)
            (output / 'checkpoint.json').write_text('{')
            with self.assertRaises(ValueError):
                run_experiment(plan, output=output, resume=True)

    def test_stop_active_worker_then_resume_retains_interruption_and_player_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.scratch') as directory:
            marker = Path(directory) / 'called'
            candidate = Entry.local('controlled', module='tests.test_batches', factory='ControlledPlayer',
                options={'marker': str(marker), 'behavior': 'loop'}, source_paths=('tests', 'omok', 'offline'),
                origin='synthetic', family='controlled', acknowledgment='Controlled test player')
            plan = ExperimentPlan.resolve(candidate,
                PoolSnapshot.freeze({'training': [entry('opponent')], 'validation': [], 'holdout': []}),
                games_per_opponent=2, move_cap=2, total_ms=300)
            output = Path(directory) / 'run'
            stopped = run_experiment(plan, output=output, stop_requested=marker.exists)
            self.assertEqual(stopped['counts']['pending'], 2)
            interrupted = stopped['attempts'][0]
            self.assertEqual(interrupted['state'], 'interrupted')
            self.assertTrue(all(w['reaped'] for w in interrupted['interrupted_trace']['workers']))
            resumed = run_experiment(plan, output=output, resume=True, infrastructure_retries=0)
            self.assertEqual(resumed['counts']['failed'], 2)
            self.assertEqual(len(resumed['attempts']), 3)
            self.assertNotEqual(interrupted['attempt_id'], resumed['results'][0]['attempt_id'])
            again = run_experiment(plan, output=output, resume=True)
            self.assertEqual(again['attempts'], resumed['attempts'])

    def test_batch_time_bound_cancels_active_work(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            stopped = run_experiment(plan, output=Path(directory) / 'run', max_seconds=0)
            self.assertEqual(stopped['counts']['pending'], 2)
            self.assertEqual(stopped['attempts'], [])
            self.assertEqual(stopped['segments'][-1]['stop_reason'], 'batch time bound')

    def test_infrastructure_retry_preserves_attempts_and_saved_policy(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.scratch') as directory:
            candidate = Entry.local('controlled', module='tests.test_batches', factory='ControlledPlayer',
                options={'marker': str(Path(directory) / 'setup'), 'behavior': 'setup_once'},
                source_paths=('tests', 'omok', 'offline'), origin='synthetic', family='controlled',
                acknowledgment='Controlled test player')
            plan = self.plan(candidate)
            output = Path(directory) / 'run'
            first = run_experiment(plan, output=output, max_jobs=1, infrastructure_retries=1)
            self.assertEqual(first['counts']['infrastructure_failed'], 1)
            with self.assertRaisesRegex(ValueError, 'retry policy'):
                run_experiment(plan, output=output, resume=True, infrastructure_retries=2)
            resumed = run_experiment(plan, output=output, resume=True)
            self.assertEqual(resumed['counts']['capped'], 2)
            self.assertEqual([a['result']['status'] for a in resumed['attempts']],
                             ['setup_failed', 'capped', 'capped'])

    def test_moved_outputs_resume_and_uncommitted_attempt_is_interrupted(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'original'
            first = run_experiment(plan, output=output, max_jobs=1)
            envelope = json.loads((output / 'checkpoint.json').read_text())
            data = envelope['data']
            # Fault injection: the process died after durable dispatch, before commit.
            data['attempts'].append({'game_id': plan.data['jobs'][1]['game_id'],
                'attempt_id': 'abrupt-exit', 'segment': data['segments'][0]['id'], 'state': 'running'})
            atomic_json(output / 'checkpoint.json', {'data': data, 'sha256': digest(data)})
            # A partial temporary write is not a durable result.
            (output / '.pending-fault').write_text('{')
            moved = Path(directory) / 'moved'
            shutil.move(str(output), moved)
            resumed = run_experiment(plan, output=moved, resume=True)
            self.assertEqual(resumed['results'][0], first['results'][0])
            self.assertEqual(resumed['attempts'][1]['state'], 'interrupted')
            self.assertEqual(resumed['counts']['pending'], 0)

    def test_duplicate_commit_is_idempotent_and_owner_is_exclusive(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            result = run_experiment(plan, output=output, max_jobs=1)
            with owner(output):
                with self.assertRaisesRegex(ValueError, 'owner'):
                    run_experiment(plan, output=output, resume=True)
                checkpoint = Checkpoint(plan, output, True, None)
                attempt = checkpoint.data['attempts'][0]
                before = (output / 'checkpoint.json').read_bytes()
                checkpoint.commit(attempt, result['results'][0])
                self.assertEqual((output / 'checkpoint.json').read_bytes(), before)
                changed = {**result['results'][0], 'error': {'message': 'conflict'}}
                with self.assertRaisesRegex(ValueError, 'Conflicting duplicate'):
                    checkpoint.commit(attempt, changed)

    def test_resume_rejects_changed_plan_source_and_truncated_result(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            run_experiment(plan, output=output, max_jobs=1)
            changed = self.plan(seed=77)
            with self.assertRaisesRegex(ValueError, 'manifest'):
                run_experiment(changed, output=output, resume=True)
            path = output / (plan.data['jobs'][0]['game_id'] + '.json')
            path.write_text('{')
            with self.assertRaises(ValueError):
                run_experiment(plan, output=output, resume=True)

    def test_resume_rejects_changed_portable_source_bundle(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.scratch') as directory:
            root = Path(directory)
            source = root / 'bot.py'
            source.write_text('class Bot:\n def __init__(self, color): self.color=color\n')
            candidate = Entry.local('portable', module='bot', factory='Bot', source_root=root,
                source_paths=('bot.py',), origin='synthetic', family='portable', acknowledgment='Test fixture')
            plan = self.plan(candidate)
            output = root / 'run'
            run_experiment(plan, output=output, max_jobs=1)
            source.write_text('CHANGED=True\n')
            with self.assertRaisesRegex(ValueError, 'source/configuration'):
                run_experiment(plan, output=output, resume=True)

    def test_real_time_bound_interrupts_loop_and_crashes_are_not_retried(self):
        from time import monotonic
        with tempfile.TemporaryDirectory(dir=ROOT / '.scratch') as directory:
            root = Path(directory)
            def controlled(behavior):
                return Entry.local('controlled', module='tests.test_batches', factory='ControlledPlayer',
                    options={'marker': str(root / 'called'), 'behavior': behavior},
                    source_paths=('tests', 'omok', 'offline'), origin='synthetic', family='controlled',
                    acknowledgment='Controlled test player')
            snapshot = PoolSnapshot.freeze({'training': [entry('opponent')], 'validation': [], 'holdout': []})
            plan = ExperimentPlan.resolve(controlled('loop'), snapshot,
                games_per_opponent=2, move_cap=2, total_ms=30000)
            start = monotonic()
            stopped = run_experiment(plan, output=root / 'bounded', max_seconds=2)
            self.assertLess(monotonic() - start, 5)
            self.assertEqual(stopped['counts']['pending'], 2)
            self.assertEqual(stopped['attempts'][0]['state'], 'interrupted')
            crash_plan = ExperimentPlan.resolve(controlled('crash'), snapshot,
                games_per_opponent=2, move_cap=2)
            crashed = run_experiment(crash_plan, output=root / 'crashed', infrastructure_retries=2)
            self.assertEqual(crashed['counts']['failed'], 2)
            self.assertEqual(len(crashed['attempts']), 2)

    def test_keyboard_interrupt_during_commit_preserves_committed_evidence(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            injected = False
            def interrupted_write(path, value):
                nonlocal injected
                atomic_json(path, value)
                data = value.get('data', {})
                if path.name == 'checkpoint.json' and data.get('results') and not injected:
                    injected = True
                    raise KeyboardInterrupt()
            with patch('offline.batches.atomic_json', side_effect=interrupted_write):
                first = run_experiment(plan, output=output)
            self.assertTrue(injected)
            self.assertEqual(first['attempts'][0]['state'], 'committed')
            resumed = run_experiment(plan, output=output, resume=True)
            self.assertEqual(resumed['results'][0], first['results'][0])
            self.assertEqual(resumed['counts']['capped'], 2)
            self.assertEqual(len(resumed['attempts']), 2)

    def test_keyboard_interrupt_between_commit_mutations_remains_resumable(self):
        plan = self.plan()
        original_init = Checkpoint.__init__
        injected = False
        class InterruptedResults(dict):
            def __setitem__(self, key, value):
                nonlocal injected
                if not injected:
                    injected = True
                    raise KeyboardInterrupt()
                super().__setitem__(key, value)
        def initialize(checkpoint, *args, **kwargs):
            original_init(checkpoint, *args, **kwargs)
            checkpoint.data['results'] = InterruptedResults(checkpoint.data['results'])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            with patch.object(Checkpoint, '__init__', initialize):
                first = run_experiment(plan, output=output)
            self.assertTrue(injected)
            self.assertEqual(first['attempts'][0]['state'], 'committed')
            resumed = run_experiment(plan, output=output, resume=True)
            self.assertEqual(len(resumed['attempts']), 2)
            self.assertEqual(resumed['results'][0], first['attempts'][0]['result'])


if __name__ == '__main__':
    unittest.main()
