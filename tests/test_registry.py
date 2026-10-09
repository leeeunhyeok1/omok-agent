# AI-written by OpenAI Codex, for issue #26.
import tempfile
from pathlib import Path
import unittest

from offline.registry import Entry, PoolSnapshot, run_registered_game
from offline.replay import replay


class RegistryTests(unittest.TestCase):
    def test_registered_game_freezes_provenance_and_records_development_exposure(self):
        candidate = Entry.local('candidate', module='offline.worker_players', factory='create',
            options={'name': 'baseline'}, source_paths=('omok', 'offline'),
            origin='retained-engine', family='omok', acknowledgment='Local AI-written engine')
        opponent = Entry.local('smoke', module='offline.worker_players', factory='create',
            options={'name': 'smoke'}, source_paths=('omok', 'offline'),
            origin='synthetic', family='random-smoke', acknowledgment='Local smoke bot',
            seed_support='constructor')
        snapshot = PoolSnapshot.freeze({'training': [opponent], 'validation': [], 'holdout': []})
        trace = run_registered_game(candidate, snapshot, 'smoke', move_cap=3)
        self.assertEqual(trace['status'], 'capped')
        provenance = trace['config']['registry']
        self.assertEqual(provenance['candidate']['identity'], candidate.identity)
        self.assertEqual(provenance['opponent']['identity'], opponent.identity)
        self.assertEqual(provenance['exposure']['purpose'], 'development')
        self.assertEqual(provenance['exposure']['pool'], 'training')
        self.assertEqual(provenance['pool_snapshot']['identity'], snapshot.identity)
        self.assertNotEqual(provenance['seeds'][0], provenance['seeds'][1])
        replay(trace)

    def local(self, name='candidate', **changes):
        options = dict(module='offline.worker_players', factory='create',
            options={'name': 'baseline'}, source_paths=('omok', 'offline'),
            origin='synthetic', family=name, acknowledgment='Controlled test fixture')
        options.update(changes)
        return Entry.local(name, **options)

    def test_reserved_pools_require_explicit_final_evaluation(self):
        candidate = self.local()
        training, validation, holdout = [self.local(n) for n in ('train', 'valid', 'reserved')]
        snapshot = PoolSnapshot.freeze({'training': [training], 'validation': [validation], 'holdout': [holdout]})
        self.assertEqual({e.data['logical_id'] for _, e in snapshot.select()}, {'train', 'valid'})
        with self.assertRaisesRegex(ValueError, 'protected holdout'):
            run_registered_game(candidate, snapshot, 'reserved', move_cap=1)
        trace = run_registered_game(candidate, snapshot, 'reserved', purpose='final-evaluation', move_cap=1)
        self.assertEqual(trace['config']['registry']['exposure']['purpose'], 'final-evaluation')
        self.assertEqual(trace['config']['registry']['exposure']['pool'], 'holdout')
        replay(trace)
        with self.assertRaisesRegex(ValueError, 'protected validation'):
            run_registered_game(candidate, snapshot, 'valid', purpose='training', move_cap=1)
        with self.assertRaisesRegex(ValueError, 'protected holdout'):
            run_registered_game(holdout, snapshot, 'train', move_cap=1)

    def test_frozen_definitions_detect_tampering_and_related_family_splits(self):
        first = self.local('first')
        record = first.record()
        record['options']['name'] = 'smoke'
        with self.assertRaisesRegex(ValueError, 'identity'):
            Entry.from_record(record)
        second = self.local('second', family='first')
        with self.assertRaisesRegex(ValueError, 'Related design'):
            PoolSnapshot.freeze({'training': [first], 'validation': [], 'holdout': [second]})
        snapshot = PoolSnapshot.freeze({'training': [first], 'validation': [], 'holdout': []})
        altered = snapshot.record()
        altered['pools']['training'] = []
        with self.assertRaisesRegex(ValueError, 'identity'):
            PoolSnapshot.from_record(altered)
        data = first.data
        data['options']['name'] = 'smoke'
        self.assertEqual(first.data['options']['name'], 'baseline')

    def test_changed_helper_or_configuration_cannot_play_under_old_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bot.py').write_text('from helper import MOVE\nclass Bot:\n def __init__(self, color): self.color=color\n def take_turn(self, board, time): return MOVE\n')
            (root / 'helper.py').write_text('MOVE=(2, 3)\n')
            (root / 'config.json').write_text('{"setting":1}')
            old = self.local('external', source_root=root, module='bot', factory='Bot', options={},
                             source_paths=('.',), origin='classmate')
            snapshot = PoolSnapshot.freeze({'training': [old], 'validation': [], 'holdout': []})
            (root / 'helper.py').write_text('MOVE=(3, 4)\n')
            with self.assertRaisesRegex(ValueError, 'changed or missing'):
                run_registered_game(self.local(), snapshot, 'external', move_cap=1)
            new = self.local('external', source_root=root, module='bot', factory='Bot', options={},
                             source_paths=('.',), origin='classmate')
            self.assertNotEqual(old.identity, new.identity)
            (root / 'config.json').write_text('{"setting":2}')
            with self.assertRaisesRegex(ValueError, 'changed or missing'):
                run_registered_game(self.local(), PoolSnapshot.freeze({'training': [new], 'validation': [], 'holdout': []}), 'external', move_cap=1)

    def test_same_named_external_modules_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            entries = []
            for number, move in enumerate(((2, 3), (4, 5))):
                root = Path(directory) / str(number)
                root.mkdir()
                (root / 'helper.py').write_text(f'MOVE={move!r}\n')
                (root / 'player.py').write_text('from helper import MOVE\nclass Player:\n def __init__(self, color): self.color=color\n def take_turn(self, board, time): return MOVE\n')
                entries.append(self.local(str(number), source_root=root, module='player', factory='Player',
                                          options={}, source_paths=('.',), origin='classmate'))
            trace = run_registered_game(entries[0], PoolSnapshot.freeze({'training': [entries[1]], 'validation': [], 'holdout': []}), '1', move_cap=2)
            self.assertEqual([m['move'] for m in trace['moves']], [[2, 3], [4, 5]])
            replay(trace)

    def test_preflight_reports_missing_dependency_invalid_config_and_color(self):
        cases = [self.local('missing', dependencies=('issue26_missing_dependency',)),
                 self.local('invalid', options={'name': 'search', 'settings': {}})]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bot.py').write_text('class Bot:\n def __init__(self, color): self.color=1-color\n')
            cases.append(self.local('wrong-color', source_root=root, source_paths=('.',), module='bot', factory='Bot', options={}))
            for entry in cases:
                with self.subTest(name=entry.data['logical_id']), self.assertRaisesRegex(ValueError, 'Preflight failed'):
                    run_registered_game(self.local(), PoolSnapshot.freeze({'training': [entry], 'validation': [], 'holdout': []}), entry.data['logical_id'], move_cap=1)
        unavailable = self.local('pending', availability='pending')
        snapshot = PoolSnapshot.freeze({'training': [unavailable], 'validation': [], 'holdout': []})
        with self.assertRaisesRegex(ValueError, 'pending'):
            snapshot.select()

    def test_seeded_players_repeat_per_role_without_sharing_randomness(self):
        a = self.local('a', options={'name': 'smoke'}, seed_support='constructor')
        b = self.local('b', options={'name': 'smoke'}, seed_support='constructor')
        snapshot = PoolSnapshot.freeze({'training': [b], 'validation': [], 'holdout': []})
        traces = [run_registered_game(a, snapshot, 'b', seed=71, move_cap=4) for _ in range(2)]
        self.assertEqual([m['move'] for m in traces[0]['moves']], [m['move'] for m in traces[1]['moves']])
        self.assertNotEqual(traces[0]['moves'][0]['move'], traces[0]['moves'][1]['move'])

    def test_retained_phase_versions_play_their_actual_checkpoint_sources(self):
        from offline.registry import default_catalog
        catalog, snapshot = default_catalog()
        for name in ('phase1', 'phase2', 'phase3-material', 'phase3-effects'):
            with self.subTest(name=name):
                trace = run_registered_game(catalog[name], snapshot, 'smoke', move_cap=1,
                                            budgets_ms=(100, 100))
                self.assertEqual(len(trace['moves']), 1)
                self.assertIsNone(trace['failure'])
                self.assertIn('commit', trace['config']['registry']['candidate']['loader'])
                replay(trace)
        self.assertEqual(catalog['random'].data['origin'], 'professor-provided')
        self.assertEqual(catalog['random'].data['seed_support'], 'process-global')
        self.assertEqual(snapshot.select(purpose='validation'), [])
        self.assertEqual(snapshot.select(purpose='final-evaluation'), snapshot.select())

    def test_adding_source_cannot_silently_change_a_frozen_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bot.py').write_text('class Bot:\n def __init__(self,color): self.color=color\n def take_turn(self,board,time): return (2,3)\n')
            entry = self.local('bundle', source_root=root, source_paths=('.',), module='bot', factory='Bot', options={})
            (root / 'new_helper.py').write_text('NEW=True\n')
            with self.assertRaisesRegex(ValueError, 'Source bundle changed'):
                run_registered_game(self.local(), PoolSnapshot.freeze({'training': [entry], 'validation': [], 'holdout': []}), 'bundle', move_cap=1)

    def test_import_and_constructor_loops_are_bounded_without_competitive_calls(self):
        from offline.supervised import Supervision
        import time
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for code in ('while True: pass\n', 'class Bot:\n def __init__(self,color):\n  while True: pass\n'):
                (root / 'bot.py').write_text(code)
                entry = self.local('loop', source_root=root, source_paths=('.',), module='bot', factory='Bot', options={})
                started = time.monotonic()
                with self.assertRaisesRegex(ValueError, 'Preflight failed'):
                    run_registered_game(self.local(), PoolSnapshot.freeze({'training': [entry], 'validation': [], 'holdout': []}), 'loop', move_cap=1,
                                        supervision=Supervision(startup_ms=300, cleanup_ms=100))
                self.assertLess(time.monotonic() - started, 3)

    def test_lazy_imports_use_frozen_worker_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'helper.py').write_text('MOVE=(2,3)\n')
            (root / 'bot.py').write_text('from pathlib import Path\nclass Bot:\n def __init__(self,color,original): self.color=color; self.original=original\n def take_turn(self,board,time):\n  Path(self.original).write_text("MOVE=(5,6)\\n")\n  from helper import MOVE\n  return MOVE\n')
            candidate = self.local('frozen', source_root=root, source_paths=('.',), module='bot', factory='Bot',
                                   options={'original': str(root / 'helper.py')})
            opponent = self.local('other')
            trace = run_registered_game(candidate, PoolSnapshot.freeze({'training': [opponent], 'validation': [], 'holdout': []}), 'other', move_cap=1)
            self.assertEqual(trace['moves'][0]['move'], [2, 3])
            self.assertEqual((root / 'helper.py').read_text(), 'MOVE=(5,6)\n')
            replay(trace)

    def test_saved_cli_registry_plays_and_replays_without_overwriting_evidence(self):
        import subprocess
        import sys
        from offline.replay import load_trace
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / 'registry.json'
            trace = Path(directory) / 'game.json'
            base = [sys.executable, '-m', 'offline.registry_cli']
            freeze = subprocess.run(base + ['freeze', '--output', str(registry)], capture_output=True, text=True, timeout=10)
            self.assertEqual(freeze.returncode, 0, freeze.stderr)
            play = base + ['play', '--registry', str(registry), '--candidate', 'phase2', '--opponent', 'random',
                           '--candidate-color', 'white', '--move-cap', '3', '--output', str(trace)]
            result = subprocess.run(play, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = load_trace(trace)
            self.assertEqual(saved['config']['registry']['candidate_color'], 1)
            self.assertEqual(len(saved['moves']), 3)
            replay(saved)
            before = trace.read_bytes()
            result = subprocess.run(play, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(trace.read_bytes(), before)

    def test_evaluator_path_cannot_escape_the_immutable_source_snapshot(self):
        from offline.registry import PHASE3
        from omok.evaluation import EvaluationConfig
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'mutable.json'
            EvaluationConfig(material=1).save(config)
            for path in (str(config), '../mutable.json', 'configs/missing.json'):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Evaluator path'):
                    Entry.checkpoint('mutable-config', commit=PHASE3, factory='IterativePlayer',
                                     options={'evaluation_path': path})
            EvaluationConfig(material=2).save(config)
            with self.assertRaisesRegex(ValueError, 'Evaluator path'):
                Entry.checkpoint('mutable-config', commit=PHASE3, factory='IterativePlayer',
                                 options={'evaluation_path': str(config)})


if __name__ == '__main__':
    unittest.main()
