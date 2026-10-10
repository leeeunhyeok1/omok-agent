# AI-written by OpenAI Codex, for issue #39.
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from offline.optimizer import create, run
from offline.proposals import ProposalPolicy, generate
from offline.registry import Entry, PHASE3, PoolSnapshot
from offline.screening import ScreeningPolicy, prepare
from tests.test_experiments import entry
from tests.test_matches import scoring_start
from offline.registry import digest
from offline.batches import Checkpoint


class OptimizerTests(unittest.TestCase):
    def setup_run(self, root):
        parent = Entry.checkpoint('incumbent', commit=PHASE3, factory='IterativePlayer')
        ProposalPolicy.for_parent(parent, batch='evaluation', groups=['material']).save(root / 'proposal-policy.json')
        proposals = generate(root / 'proposal-policy.json', [parent], seed=39, count=1, output=root / 'population')
        candidates = [Entry.from_record(c['entry']) for c in proposals['candidates']]
        snapshot = PoolSnapshot.freeze({'training': [entry('opponent')], 'validation': [], 'holdout': []})
        ScreeningPolicy.create(opponents={'opponent': 2}, opponent_weights={'opponent': 1},
            family_weights={'opponent': 1}, min_evidence_per_color=1, move_cap=1).save(root / 'screen-policy.json')
        prepare(root / 'screen-policy.json', parent, candidates, snapshot, output=root / 'stage', fixture=scoring_start())
        create(root / 'run', proposals=root / 'population/proposals.json', stage=root / 'stage')
        return proposals

    def test_global_game_bound_and_resume_preserve_population_and_committed_work(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            proposals = self.setup_run(root)
            partial = run(root / 'run', max_games=1)
            self.assertEqual(partial['progress']['committed_jobs'], 1)
            self.assertEqual(partial['progress']['pending_jobs'], 3)
            self.assertFalse(partial['decision_committed'])
            final = run(root / 'run', max_games=10, workers=2)
            self.assertEqual(final['progress']['committed_jobs'], 4)
            self.assertTrue(final['decision_committed'])
            self.assertEqual(final['population'], proposals)
            again = run(root / 'run', max_games=10)
            self.assertEqual(final['decisions'], again['decisions'])
            self.assertEqual(final['evidence'], again['evidence'])
            self.assertEqual(again['progress']['attempts'], 4)
            self.assertEqual(again['history'], [again['incumbent']])
            self.assertTrue(any(s['changed_conditions'] for s in again['segments']))

    def test_zero_time_and_requested_stop_dispatch_nothing_then_resume(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_run(root)
            stopped = run(root / 'run', max_seconds=0)
            self.assertEqual(stopped['progress']['attempts'], 0)
            stopped = run(root / 'run', stop_requested=lambda: True)
            self.assertEqual(stopped['progress']['attempts'], 0)
            self.assertEqual(stopped['segments'][-1]['stop_reason'], 'graceful stop')
            final = run(root / 'run')
            self.assertEqual(final['progress']['attempts'], 4)

    def test_commit_export_interruption_recovers_commits_and_never_repeats_selection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_run(root)
            def crash(counts):
                raise RuntimeError('owner died after durable game commit')
            with self.assertRaisesRegex(RuntimeError, 'owner died'):
                run(root / 'run', progress=crash)
            # Reports are derived: deletion must not cause a replay.
            for path in (root / 'run').rglob('results.json'):
                path.unlink()
            final = run(root / 'run')
            self.assertEqual(final['progress']['attempts'], 4)
            decision = final['decisions']
            (root / 'run/screening-report.json').write_text('{')
            again = run(root / 'run')
            self.assertEqual(again['decisions'], decision)
            self.assertEqual(again['progress']['attempts'], 4)

    def test_corrupt_child_and_changed_source_are_rejected_before_other_dispatch(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_run(root)
            stopped = run(root / 'run', max_games=0)
            plan_id = list(stopped['stage_assignments'].values())[-1][0]
            path = root / 'run' / plan_id / 'checkpoint.json'
            original = path.read_bytes()
            path.write_text('{')
            with self.assertRaises(ValueError):
                run(root / 'run')
            path.write_bytes(original)
            with patch('offline.batches.source_snapshot', return_value={}):
                with self.assertRaisesRegex(ValueError, 'version changed'):
                    run(root / 'run')
            final = run(root / 'run', max_games=0)
            self.assertEqual(final['progress']['attempts'], 0)

    def test_duplicate_delivery_and_out_of_order_completion_preserve_logical_decision(self):
        from offline.experiments import execute_job
        from time import sleep
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_run(root)
            manifest = root / 'run/manifest.json'
            other = root / 'other'
            other.mkdir()
            (other / 'manifest.json').write_bytes(manifest.read_bytes())
            (other / 'optimizer-checkpoint.json').write_bytes((root / 'run/optimizer-checkpoint.json').read_bytes())
            reference = run(root / 'run')
            def reordered(plan, job, check_stop):
                record = execute_job(plan, job, check_stop)
                if job['slot'] == 0:
                    sleep(.2)
                return record
            commit = Checkpoint.commit
            def duplicate(cp, attempt, record):
                commit(cp, attempt, record)
                commit(cp, attempt, record)
            with patch('offline.batches.execute_job', side_effect=reordered), patch.object(Checkpoint, 'commit', duplicate):
                final = run(other, workers=2)
            self.assertEqual(final['population'], reference['population'])
            self.assertEqual(final['decisions'], reference['decisions'])
            self.assertEqual(final['progress']['attempts'], 4)

    def test_authoritative_run_corruption_and_policy_tampering_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_run(root)
            run(root / 'run', max_games=0)
            path = root / 'run/optimizer-checkpoint.json'
            saved = path.read_bytes()
            path.write_text('{')
            with self.assertRaisesRegex(ValueError, 'authoritative'):
                run(root / 'run')
            path.write_bytes(saved)
            path = root / 'run/manifest.json'
            envelope = json.loads(path.read_text())
            envelope['data']['stage']['policy']['policy']['seed'] += 1
            envelope['identity'] = digest(envelope['data'])
            path.write_text(json.dumps(envelope))
            with self.assertRaises(ValueError):
                run(root / 'run')

    def test_stop_after_verified_completion_commits_result_in_shutdown(self):
        from offline.experiments import execute_job
        from threading import Event
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_run(root)
            completed = Event()
            def finishing(plan, job, check_stop):
                result = execute_job(plan, job, check_stop)
                completed.set()
                return result
            with patch('offline.batches.execute_job', side_effect=finishing):
                stopped = run(root / 'run', stop_requested=completed.is_set)
            self.assertEqual(stopped['progress']['committed_jobs'], 1)
            self.assertEqual(stopped['progress']['attempts'], 1)
            final = run(root / 'run')
            self.assertEqual(final['progress']['attempts'], 4)

    def test_missing_authoritative_run_checkpoint_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_run(root)
            run(root / 'run', max_games=0)
            (root / 'run/optimizer-checkpoint.json').unlink()
            with self.assertRaisesRegex(ValueError, 'authoritative'):
                run(root / 'run', max_games=0)

    def test_missing_child_checkpoint_cannot_erase_previously_committed_work(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_run(root)
            partial = run(root / 'run', max_games=1)
            plan_id = next(k for k, evidence in partial['evidence'].items() if evidence)
            child = root / 'run' / plan_id
            for path in child.glob('*.json'):
                if path.name != 'manifest.json':
                    path.unlink()
            with self.assertRaisesRegex(ValueError, 'authoritative child'):
                run(root / 'run', max_games=0)
            saved = json.loads((root / 'run/optimizer-checkpoint.json').read_text())['data']
            self.assertEqual(saved['progress']['committed_jobs'], 1)


if __name__ == '__main__':
    unittest.main()
