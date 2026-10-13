# AI-written by OpenAI Codex for issue #45.
"""Public autonomous optimizer behavior with actual restored players."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from offline.evolution import initialize, run, starter_policy, status
from offline.registry import Entry, PoolSnapshot, default_catalog

OPENING = [[9, 5], [10, 5], [9, 6], [10, 6], [9, 7], [10, 7], [9, 8], [10, 8]]


def small_policy():
    catalog, _ = default_catalog()
    p = starter_policy(catalog['phase3-material'])
    p.update(population_size=1, validation_every=100)
    for name in ('screening', 'league', 'confirmation'):
        screen = p[name] if name == 'screening' else p[name]['screening']
        screen.update(opponents={'smoke': 2, 'synthetic-aggressive': 2},
                      min_evidence_per_color=1, move_cap=20)
    p['screening_openings'] = p['league_openings'] = [OPENING]
    return p


def small_snapshot():
    _, snapshot = default_catalog()
    wanted = {'smoke', 'synthetic-aggressive', 'synthetic-defensive', 'synthetic-space'}
    return PoolSnapshot.freeze({pool: [Entry.from_record(r) for r in records if r['logical_id'] in wanted]
                               for pool, records in snapshot.record()['pools'].items()})


class EvolutionTests(unittest.TestCase):
    def test_successive_rounds_use_saved_parents_and_global_attempt_limit(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'search'
            prepared = initialize(output, policy=small_policy(), snapshot=small_snapshot())
            self.assertEqual(prepared['rounds'], [])
            def crash(event):
                raise RuntimeError(event)
            for event in ('round created', 'proposal persisted', 'screening prepared'):
                def at_boundary(actual, expected=event):
                    if actual == expected:
                        crash(actual)
                with self.assertRaisesRegex(RuntimeError, event):
                    run(output, max_games=100, max_seconds=600, interrupt=at_boundary)
            def child_commit(counts):
                if 'event' not in counts:
                    raise RuntimeError('child committed')
            with self.assertRaisesRegex(RuntimeError, 'child committed'):
                run(output, max_games=1, max_seconds=600, progress=child_commit)
            partial = status(output)
            self.assertEqual(partial['segments'][-1]['attempts'], 1)
            self.assertEqual(partial['rounds'][0]['stage'], 'screening')
            first = partial['rounds'][0]['population']
            final = run(output, max_games=100, max_seconds=600, max_rounds=2)
            self.assertEqual(len(final['rounds']), 2)
            self.assertEqual([r['stage'] for r in final['rounds']], ['committed', 'committed'])
            self.assertEqual(final['rounds'][0]['population'], first)
            self.assertEqual(final['rounds'][1]['parents'], final['rounds'][0]['decision']['parents'])
            self.assertNotEqual(final['rounds'][1]['seed'], final['rounds'][0]['seed'])
            self.assertEqual(final['segments'][-1]['attempts'], 55)
            again = run(output, max_games=0, max_seconds=0)
            self.assertEqual(again['rounds'], final['rounds'])
            self.assertEqual(again['incumbent'], prepared['incumbent'])
            self.assertEqual(status(output)['parents'], final['rounds'][1]['decision']['parents'])

    def test_exhaustion_records_a_review_without_dispatch(self):
        import subprocess
        import sys
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'search'
            p = small_policy()
            p['seed'] = 0
            p['proposal'].update(max_attempts=1, diversity_probability=0)
            initialize(output, policy=p, snapshot=small_snapshot())
            final = run(output, max_games=10, max_seconds=120)
            self.assertEqual(final['stopped'], 'proposal exhaustion')
            self.assertEqual(final['segments'][-1]['attempts'], 0)
            result = subprocess.run([sys.executable, '-m', 'offline.optimizer', 'review',
                                     '--output', str(output), '--round', '0'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('proposal exhaustion', result.stdout)

    def test_equal_gate_evidence_preserves_decisions_across_all_commit_boundaries(self):
        """Fabricated gate vetoes compare mechanics; no strength evidence or game draws."""
        import subprocess
        from unittest.mock import patch
        from offline.champions import ChampionStore
        execute = subprocess.run
        def fail_gate(argv, **kwargs):
            if 'input' in kwargs:
                return subprocess.CompletedProcess(argv, 1, '', 'FABRICATED gate rejection mechanics')
            return execute(argv, **kwargs)
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference'
            recovered = Path(directory) / 'recovered'
            p, snapshot = small_policy(), small_snapshot()
            initialize(reference, policy=p, snapshot=snapshot)
            initialize(recovered, policy=p, snapshot=snapshot)
            events = ('round created', 'proposal persisted', 'screening prepared', 'league prepared',
                      'round committed', 'round created', 'proposal persisted')
            with patch('offline.gates.subprocess.run', side_effect=fail_gate):
                expected = run(reference, max_games=20, max_seconds=600, max_rounds=2)
                for boundary in events:
                    def crash(event, target=boundary):
                        if event == target:
                            raise RuntimeError(event)
                    with self.assertRaisesRegex(RuntimeError, boundary):
                        run(recovered, max_games=20, max_seconds=600, max_rounds=2, interrupt=crash)
                    if boundary == 'round committed':
                        run(recovered, max_games=0, max_seconds=0)
                        version = ChampionStore(recovered / 'champions').load()['current']
                        self.assertTrue((recovered / 'exports' / (version + '.json')).is_file())
                actual = run(recovered, max_games=20, max_seconds=600, max_rounds=1)
            self.assertEqual([r['population'] for r in actual['rounds']], [r['population'] for r in expected['rounds']])
            self.assertEqual([r['decision'] for r in actual['rounds']], [r['decision'] for r in expected['rounds']])
            self.assertEqual(actual['rng_state'], expected['rng_state'])
            self.assertEqual(actual['parents'], expected['parents'])
            self.assertTrue(all(s['attempts'] == 0 for s in actual['segments']))

    def test_initialize_rejects_later_training_role_changes_before_proposals(self):
        with TemporaryDirectory() as directory:
            p = small_policy()
            for name in ('league', 'confirmation'):
                with self.subTest(stage=name):
                    bad = __import__('copy').deepcopy(p)
                    screen = bad[name]['screening']
                    screen.update(opponents={'synthetic-space': 2},
                                  opponent_weights={'synthetic-space': 1},
                                  family_weights={'space-filling': 1})
                    output = Path(directory) / name
                    with self.assertRaisesRegex(ValueError, 'training opponents only'):
                        initialize(output, policy=bad)
                    self.assertFalse(output.exists())

    def test_archived_holdout_cannot_enter_as_historical_champion(self):
        from offline.league import champion_bundle
        catalog, _ = default_catalog()
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'search'
            with self.assertRaisesRegex(ValueError, 'protected holdout'):
                initialize(output, policy=small_policy(), snapshot=small_snapshot(),
                           history={'champions': [champion_bundle(catalog['synthetic-space'])]})
            self.assertFalse(output.exists())

    def test_corrupt_population_is_rejected_without_new_attempts(self):
        import json
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'search'
            initialize(output, policy=small_policy(), snapshot=small_snapshot())
            def crash(event):
                if event == 'proposal persisted':
                    raise RuntimeError('proposal persisted')
            with self.assertRaisesRegex(RuntimeError, 'proposal persisted'):
                run(output, max_games=1, max_seconds=120, interrupt=crash)
            before = status(output)
            path = output / 'rounds/0/population/proposals.json'
            population = json.loads(path.read_text())
            population['seed'] = -1
            path.write_text(json.dumps(population))
            with self.assertRaisesRegex(ValueError, 'Immutable population changed'):
                run(output, max_games=1, max_seconds=120)
            self.assertEqual(status(output)['segments'], before['segments'])

    def test_failed_candidate_gates_prevent_game_dispatch(self):
        import json
        import subprocess
        from unittest.mock import patch
        execute = subprocess.run
        def gate_process(argv, **kwargs):
            entry = json.loads(kwargs['input']) if 'input' in kwargs else None
            if entry and entry['logical_id'].startswith('candidate-'):
                return subprocess.CompletedProcess(argv, 1, '', 'Controlled restored-player failure')
            return execute(argv, **kwargs)
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'search'
            initialize(output, policy=small_policy(), snapshot=small_snapshot())
            with patch('offline.gates.subprocess.run', side_effect=gate_process):
                final = run(output, max_games=100, max_seconds=600, max_rounds=1)
            round_record = final['rounds'][0]
            candidate = round_record['population']['candidates'][0]['entry']['identity']
            from offline.screening import load_stage
            declaration = load_stage(output / 'rounds/0/screening')
            plan_ids = {p['identity'] for m in declaration['members'] if m['entry']['identity'] == candidate
                        for p in m['plans']}
            candidate_attempts = [a for key, raw in round_record['stages']['screening']['raw'].items()
                                  if key in plan_ids for a in raw['attempts']]
            self.assertEqual(len(candidate_attempts), 0)
            self.assertEqual(round_record['decision']['screening'][candidate]['status'], 'fail')

    def test_user_facing_initialize_status_and_zero_budget_run(self):
        import json
        import subprocess
        import sys
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'search'
            policy = Path(directory) / 'policy.json'
            policy.write_text(json.dumps(small_policy()))
            for arguments in ([ 'initialize', '--policy', str(policy)], ['status'],
                              ['run', '--max-games', '0', '--max-seconds', '0', '--max-rounds', '2']):
                result = subprocess.run([sys.executable, '-m', 'offline.optimizer', *arguments,
                                         '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(status(output)['rounds'], [])

    def test_controlled_complete_path_promotes_retains_history_and_resumes_transaction(self, evidence_output=None):
        """Fabricated worker outcomes prove mechanics, never actual engine strength."""
        from unittest.mock import patch
        from offline.runner import run_game
        from tests.test_promotion import SequencePlayer, legal_opening
        from offline.champions import ChampionStore
        import json
        p = small_policy()
        p['screening_openings'] = p['league_openings'] = [legal_opening()]
        p['confirmation_openings'] = [
            [[3, i] if c == 0 else [8, i + 1] for i in range(4) for c in (0, 1)],
            [[4, i] if c == 0 else [9, i + 1] for i in range(4) for c in (0, 1)]]
        p['validation_openings'] = p['confirmation_openings']
        for name in ('screening', 'league', 'confirmation'):
            screen = p[name] if name == 'screening' else p[name]['screening']
            screen.update(opponents={'smoke': 4, 'synthetic-aggressive': 4}, move_cap=20)
        baseline = [None]
        reject_confirmation = [False]
        def worker(*specs, initial, budgets_ms, move_cap, config, **kwargs):
            job = config['experiment']['job']
            candidate = config['experiment']['candidate']['identity']
            winner = 1 - job['candidate_color'] if candidate == baseline[0] else job['candidate_color']
            if reject_confirmation[0] and any(initial.board[r][c] != -1 for r in (3, 4) for c in range(19)):
                winner = 1 - job['candidate_color']
            if any(cell != -1 for row in initial.board for cell in row):
                stones = [(r, c) for r, row in enumerate(initial.board) for c, v in enumerate(row) if v == winner]
                row = stones[0][0]
                last = max(c for r, c in stones if r == row)
                moves = [[(0, 0)], [(0, 1)]]
                moves[winner] = [(row, last + 1)]
            else:
                moves = [[(2 + color * 5, i if winner == color else i * 2) for i in range(5)] for color in (0, 1)]
            return run_game(*(SequencePlayer(c, moves[c]) for c in (0, 1)), initial=initial,
                            budgets_ms=budgets_ms, move_cap=move_cap, clock=lambda: 0, config=config)
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'search'
            first = initialize(output, policy=p, snapshot=small_snapshot())
            baseline[0] = first['incumbent']['identity']
            def crash(event):
                if event == 'promotion committed':
                    raise RuntimeError('controlled interruption after champion transaction')
            conditions = {'power': 'FABRICATED mechanics', 'load': 'FABRICATED mechanics', 'other_experiments_stopped': True}
            with patch('offline.supervised.preflight_player', return_value={'ready': True, 'detail': 'FABRICATED mechanics'}), patch('offline.supervised.run_supervised_game', side_effect=worker):
                with self.assertRaisesRegex(RuntimeError, 'controlled interruption', msg='Serious finalist must reach promotion within the declared allocation'):
                    run(output, max_games=1000, max_seconds=900, max_rounds=1,
                        conditions=conditions, interrupt=crash)
                promoted = status(output)
                self.assertNotEqual(promoted['incumbent']['identity'], baseline[0])
                # Replay the already committed transaction against its original baseline.
                first_round = run(output, max_games=1000, max_seconds=900, max_rounds=1, conditions=conditions)
                self.assertEqual(first_round['segments'][-1]['attempts'], 0)
                self.assertEqual(len(ChampionStore(output / 'champions').load()['transactions']), 1)
                baseline[0] = first_round['incumbent']['identity']
                reject_confirmation[0] = True
                next_round = run(output, max_games=1000, max_seconds=900, max_rounds=1, conditions=conditions)
            if evidence_output is not None:
                __import__('shutil').copytree(output, evidence_output)
            self.assertEqual(len(next_round['rounds']), 2)
            self.assertEqual(next_round['rounds'][1]['parents'], first_round['rounds'][0]['decision']['parents'])
            self.assertEqual(len(ChampionStore(output / 'champions').load()['transactions']), 1)
            self.assertEqual(next_round['incumbent'], first_round['incumbent'])
            self.assertFalse(next_round['rounds'][1]['decision']['historical_gaps'])
            self.assertFalse(next_round['rounds'][1]['stages']['confirmation']['report']['advanced'])
            for round_record in next_round['rounds']:
                for stage in round_record['stages'].values():
                    for raw in stage['raw'].values():
                        self.assertFalse(any(r['exposure']['pool'] == 'holdout' for r in raw['results']))
