# AI-written by OpenAI Codex, for issue #32.
"""Controlled games at the agreed complete runner/tournament boundary."""
import tempfile
import unittest
import os
from unittest.mock import patch
from pathlib import Path
from time import monotonic, sleep

from offline.experiments import ExperimentPlan, run_experiment
from offline.batches import Checkpoint
from offline.registry import Entry, PoolSnapshot, ROOT
from tests.test_experiments import entry


class ConcurrentPlayer:
    def __init__(self, color, seed=0, marker=None, loop=False, exit_on_turn=False):
        self.color, self.seed, self.marker, self.loop = color, seed, marker, loop
        self.exit_on_turn = exit_on_turn
        self.turns = 0

    def take_turn(self, board, time):
        if self.exit_on_turn:
            os._exit(7)
        if self.marker:
            Path(self.marker + str(self.color)).write_text('started')
        if self.loop:
            while True:
                pass
        sleep(0.75 if self.color == 0 else 0.01)
        self.turns += 1
        row = self.turns - 1
        return next((row, c) for c in range(19) if board[row][c] == -1)


def controlled_plan(**options):
    candidate = Entry.local('controlled', module='tests.test_concurrency', factory='ConcurrentPlayer',
        options=options, source_paths=('tests', 'omok', 'offline'), origin='synthetic',
        family='controlled', acknowledgment='Controlled concurrency fixture', seed_support='constructor')
    return ExperimentPlan.resolve(candidate,
        PoolSnapshot.freeze({'training': [entry('opponent')], 'validation': [], 'holdout': []}),
        games_per_opponent=2, move_cap=4, total_ms=3000)


class ConcurrencyTests(unittest.TestCase):
    def test_out_of_order_games_preserve_serial_schedule_and_player_state(self):
        plan = controlled_plan()
        serial = run_experiment(plan)
        parallel = run_experiment(plan, workers=2, contention='controlled fixture; no other experiments')
        self.assertEqual([a['game_id'] for a in parallel['attempts'] if a['state'] == 'committed'],
                         [j['game_id'] for j in plan.data['jobs']])
        self.assertEqual(parallel['segments'][0]['completion_order'],
                         [j['game_id'] for j in reversed(plan.data['jobs'])])
        for a, b, job in zip(serial['results'], parallel['results'], plan.data['jobs']):
            self.assertEqual(a['game_id'], b['game_id'])
            self.assertEqual(a['status'], b['status'])
            self.assertEqual([{k: m[k] for k in ('color', 'move', 'captured')} for m in a['trace']['moves']],
                             [{k: m[k] for k in ('color', 'move', 'captured')} for m in b['trace']['moves']])
            self.assertEqual(b['trace']['config']['experiment']['job'], job)
            self.assertEqual([m['move'][0] for m in b['trace']['moves']
                              if m['color'] == job['candidate_color']], [0, 1])
            self.assertTrue(all(w['reaped'] for w in b['trace']['workers']))
            self.assertGreaterEqual(b['scheduling']['queue_ms'], 0)
            self.assertGreaterEqual(b['scheduling']['execution_ms'], 0)
            for color in (0, 1):
                charged = sum(m['elapsed_ms'] for m in b['trace']['moves'] if m['color'] == color)
                self.assertAlmostEqual(b['trace']['remaining_ms'][color], 3000 - charged)
        self.assertEqual(parallel['conditions']['workers'], 2)
        self.assertEqual(parallel['counts']['capped'], 2)

    def test_stop_cleans_every_active_game_and_resume_preserves_identities(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.scratch') as directory:
            root = Path(directory)
            marker = str(root / 'turn-')
            plan = controlled_plan(marker=marker, loop=True)
            stopped = run_experiment(plan, output=root / 'run', workers=2,
                stop_requested=lambda: all(Path(marker + str(c)).exists() for c in (0, 1)))
            self.assertEqual(stopped['counts']['pending'], 2)
            self.assertEqual(len(stopped['attempts']), 2)
            for attempt in stopped['attempts']:
                self.assertEqual(attempt['state'], 'interrupted')
                self.assertTrue(all(w['reaped'] for w in attempt['interrupted_trace']['workers']))
            resumed = run_experiment(plan, output=root / 'run', resume=True, workers=2)
            self.assertEqual(resumed['counts']['failed'], 2)
            self.assertEqual(len(resumed['attempts']), 4)
            self.assertEqual([r['game_id'] for r in resumed['results']],
                             [j['game_id'] for j in plan.data['jobs']])

    def test_supervisor_start_failure_is_retained_without_player_forfeit(self):
        plan = controlled_plan()
        # Process creation is an OS boundary; simulate an unexpected supervisor fault.
        with patch('subprocess.Popen', side_effect=RuntimeError('controlled supervisor failure')):
            result = run_experiment(plan, workers=2)
        self.assertEqual(result['counts']['infrastructure_failed'], 2)
        self.assertTrue(all(r['status'] == 'supervisor_error' for r in result['results']))
        self.assertEqual(result['match_scores']['matches'][0]['recognized']['opponent_wins'], 0)

    def test_player_exit_is_not_retried_under_concurrency(self):
        result = run_experiment(controlled_plan(exit_on_turn=True), workers=2, infrastructure_retries=2)
        self.assertEqual(result['counts']['failed'], 2)
        self.assertEqual(len(result['attempts']), 2)
        for record in result['results']:
            self.assertEqual(record['trace']['reason'], 'player_exit')
            self.assertTrue(all(w['reaped'] for w in record['trace']['workers']))

    def test_owner_failure_interrupts_other_games_and_resume_keeps_committed_game(self):
        plan = controlled_plan()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            def failed_owner(counts):
                raise RuntimeError('controlled owner failure')
            with self.assertRaisesRegex(RuntimeError, 'owner failure'):
                run_experiment(plan, output=output, workers=2, progress=failed_owner)
            restored = Checkpoint(plan, output, True, None)
            self.assertEqual(len(restored.data['results']), 1)
            interrupted = next(a for a in restored.data['attempts'] if a['state'] == 'interrupted')
            evidence = interrupted.get('interrupted_trace', interrupted.get('discarded_result', {}).get('trace'))
            self.assertTrue(all(w['reaped'] for w in evidence['workers']))
            result = run_experiment(plan, output=output, resume=True)
            self.assertEqual(result['counts']['capped'], 2)
            self.assertEqual(len(result['attempts']), 3)

    def test_checkpoint_rejects_cancelled_and_foreign_owner_arrivals(self):
        plan = controlled_plan()
        record = run_experiment(plan, max_jobs=1)['results'][0]
        first = Checkpoint(plan, None, False, None)
        attempt = first.begin(record['game_id'], 'first')
        attempt['state'] = 'interrupted'
        with self.assertRaisesRegex(ValueError, 'Late'):
            first.commit(attempt, record)
        second = Checkpoint(plan, None, False, None)
        with self.assertRaisesRegex(ValueError, 'owner'):
            second.commit(attempt, record)

    def test_worker_bounds_and_hardware_changes_are_segment_metadata(self):
        plan = ExperimentPlan.resolve(entry('candidate'),
            PoolSnapshot.freeze({'training': [entry('opponent')], 'validation': [], 'holdout': []}),
            games_per_opponent=4, move_cap=0)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            first = run_experiment(plan, output=output, workers=2, max_jobs=3)
            self.assertEqual(first['counts']['pending'], 1)
            self.assertEqual(first['segments'][0]['peak_active_games'], 2)
            self.assertGreater(first['results'][2]['scheduling']['queue_ms'],
                               first['results'][0]['scheduling']['queue_ms'])
            from offline.experiments import execution_conditions
            changed = execution_conditions()
            changed['cpu'] = 'controlled changed CPU'
            with patch('offline.batches.execution_conditions', return_value=changed):
                resumed = run_experiment(plan, output=output, resume=True)
            self.assertEqual(resumed['results'][:3], first['results'])
            self.assertIn('cpu', resumed['segments'][-1]['changed_conditions'])
            self.assertIn('workers', resumed['segments'][-1]['changed_conditions'])
            self.assertEqual(len(resumed['attempts']), 4)
        for workers in (0, -1, True, 65):
            with self.assertRaises(ValueError):
                run_experiment(plan, workers=workers)

    def test_time_bound_interrupts_parallel_workers_with_bounded_cleanup(self):
        started = monotonic()
        result = run_experiment(controlled_plan(loop=True), workers=2, max_seconds=2)
        self.assertLess(monotonic() - started, 6)
        self.assertEqual(result['counts']['pending'], 2)
        self.assertEqual(len(result['attempts']), 2)
        for attempt in result['attempts']:
            self.assertEqual(attempt['state'], 'interrupted')
            if 'interrupted_trace' in attempt:
                self.assertTrue(all(w['reaped'] for w in attempt['interrupted_trace']['workers']))
            else:
                self.assertTrue(attempt['interrupted_preflight']['worker']['reaped'])


if __name__ == '__main__':
    unittest.main()
