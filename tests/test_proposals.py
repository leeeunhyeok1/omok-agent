# AI-written by OpenAI Codex, for issue #37.
"""Candidate proposal artifacts and registered execution are the test seams."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from offline.registry import Entry, PHASE3
from offline.proposals import ProposalPolicy, generate, resolve_entry
from offline.registry import canonical
from offline.registry import default_catalog, run_registered_game, PoolSnapshot
from offline.replay import replay
from omok.evaluation import EvaluationConfig
from omok.simulator import Position


class ProposalTests(unittest.TestCase):
    def parent(self, name='incumbent'):
        return Entry.checkpoint(name, commit=PHASE3, factory='IterativePlayer')

    def test_saved_policy_reproduces_actual_candidates_without_changing_parent(self):
        parent = self.parent()
        before = parent.definition
        with TemporaryDirectory() as directory:
            root = Path(directory)
            policy = ProposalPolicy.for_parent(parent, batch='evaluation', groups=['material'])
            policy.save(root / 'policy.json')
            first = generate(root / 'policy.json', [parent], seed=37, count=3, output=root / 'first')
            second = generate(root / 'policy.json', [parent], seed=37, count=3, output=root / 'second')
            self.assertEqual(first, second)
            self.assertEqual(len(first['candidates']), 3)
            original = resolve_entry(parent)
            for record in first['candidates']:
                entry = Entry.from_record(record['entry'])
                actual = resolve_entry(entry)
                self.assertEqual(actual['settings'], original['settings'])
                self.assertNotEqual(actual['evaluation']['coefficients']['material'], 1)
                self.assertEqual(record['parents'], [parent.identity])
            self.assertEqual(parent.definition, before)
            self.assertEqual(json.loads((root / 'first' / 'proposals.json').read_text()), first)
            with self.assertRaises(FileExistsError):
                generate(root / 'policy.json', [parent], seed=37, count=3, output=root / 'first')

    def test_invalid_actual_configurations_cannot_become_registry_entries(self):
        parent = self.parent()
        original = resolve_entry(parent)
        cases = [
            ('settings.max_depth', 1.5), ('settings.max_nodes', True),
            ('settings.max_nodes', 10 ** 400),
            ('settings.table_capacity', 1000000), ('settings.candidate_radius', 0),
            ('settings.candidate_cap', 0), ('settings.extensions', 'unverified-extension'),
            ('settings.full_width', True), ('settings.ordering', 'made-up'),
            ('settings.time_policy.return_margin_ms', 0),
            ('settings.time_policy.turn_fraction', float('inf')),
            ('evaluation.coefficients.material', 4001),
            ('evaluation.coefficients.material', False),
        ]
        for path, invalid in cases:
            with self.subTest(path=path, value=invalid):
                value = json.loads(json.dumps(original))
                parts = path.split('.')
                target = value
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = invalid
                data = parent.data
                data['options'] = {'candidate_configuration': value}
                with self.assertRaises(ValueError):
                    Entry(canonical(data))

    def test_accepted_configuration_executes_in_both_colors_through_registry(self):
        parent = self.parent()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            ProposalPolicy.for_parent(parent, batch='search-time', groups=['candidates']).save(root / 'policy.json')
            batch = generate(root / 'policy.json', [parent], seed=37, count=1, output=root / 'batch')
            candidate = Entry.from_record(batch['candidates'][0]['entry'])
            _, pools = default_catalog()
            for color in (0, 1):
                trace = run_registered_game(candidate, pools, 'smoke', candidate_color=color,
                    purpose='training', seed=37, move_cap=2, budgets_ms=(5000, 5000), diagnostics=True)
                self.assertEqual(trace['status'], 'capped')
                self.assertEqual(len(trace['moves']), 2)
                position = Position.empty()
                for event in trace['moves']:
                    position = position.play(event['move']).position
                self.assertEqual(trace['config']['registry']['candidate']['identity'], candidate.identity)

    def test_bounded_rejections_repairs_duplicates_and_shared_ancestry_are_reproducible(self):
        parent = self.parent()
        data = parent.data
        value = resolve_entry(parent)
        value['evaluation']['coefficients']['material'] = 4000
        data['options'] = {'candidate_configuration': value}
        parent = Entry(canonical(data))
        renamed = parent.data
        renamed['logical_id'] = 'same-genotype-other-name'
        renamed = Entry(canonical(renamed))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for repair in ('reject', 'clip-domain'):
                policy = ProposalPolicy.for_parent(parent, batch='evaluation', groups=['material'],
                    diversity_probability=0, max_attempts=1, repair=repair)
                path = root / (repair + '.json')
                policy.save(path)
                first = generate(path, [parent, renamed], seed=37, count=30, output=root / repair)
                second = generate(path, [renamed, parent], seed=37, count=30, output=root / (repair + '-again'))
                self.assertEqual(first, second)
                self.assertEqual(len(first['attempts']), 30)
                self.assertTrue(first['exhausted_slots'])
                if repair == 'reject':
                    self.assertTrue(any(a['status'] == 'rejected' for a in first['attempts']))
                else:
                    self.assertTrue(any(a['repairs'] for a in first['attempts']))
                    self.assertTrue(any(a['status'] == 'duplicate' for a in first['attempts']))
                self.assertEqual(len({c['genotype'] for c in first['candidates']}), len(first['candidates']))
                self.assertIn(sorted([parent.identity, renamed.identity]), first['ancestry'].values())

    def test_policy_cannot_change_features_pool_semantics_or_unsupported_mechanisms(self):
        parent = self.parent()
        for batch, groups in [('evaluation', ['extensions']), ('evaluation', ['captures']),
                              ('search-time', ['material']), ('evaluation', ['feature_version'])]:
            with self.subTest(batch=batch, groups=groups), self.assertRaises(ValueError):
                ProposalPolicy.for_parent(parent, batch=batch, groups=groups)
        policy = ProposalPolicy.for_parent(parent, batch='evaluation', groups=['material'])
        value = policy.data
        value['schema']['genes']['evaluation.coefficients.material']['domain'] = [-10000, 10000]
        with self.assertRaises(ValueError):
            ProposalPolicy(canonical(value))
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'policy.json'
            policy.save(path)
            record = json.loads(path.read_text())
            record['policy']['repair'] = 'clip-domain'
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                ProposalPolicy.load(path)

    def test_policy_pins_source_basis_before_proposing(self):
        parent = self.parent()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            policy = ProposalPolicy.for_parent(parent, batch='evaluation', groups=['material'])
            self.assertEqual(policy.data['engine_sources'], parent.data['sources'])
            self.assertEqual(policy.data['adapter_sources'], parent.data['adapter_sources'])
            policy.save(root / 'policy.json')
            other = parent.data
            other['sources']['unrelated-engine-asset.json'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'source basis'):
                generate(root / 'policy.json', [Entry(canonical(other))], seed=37, count=1, output=root / 'batch')

    def test_registered_players_keep_interleaved_diagnostics_and_caches_independent(self):
        # Registry factories own one player per worker. Observe configuration
        # independence at that public execution boundary during interleaved turns.
        with TemporaryDirectory() as directory:
            root = Path(directory)
            parent = self.parent()
            ProposalPolicy.for_parent(parent, batch='evaluation', groups=['material']).save(root / 'policy.json')
            batch = generate(root / 'policy.json', [parent], seed=37, count=2, output=root / 'batch')
            first, second = [Entry.from_record(record['entry']) for record in batch['candidates']]
            expected = [EvaluationConfig.from_json(canonical(resolve_entry(entry)['evaluation'])).identity
                        for entry in (first, second)]
            self.assertNotEqual(expected[0], expected[1])
            pools = PoolSnapshot.freeze({'training': [second], 'validation': [], 'holdout': []})
            for _ in range(2):
                trace = run_registered_game(first, pools, second.data['logical_id'], purpose='training',
                    seed=37, move_cap=4, budgets_ms=(5000, 5000), diagnostics=True)
                self.assertEqual(trace['status'], 'capped')
                replay(trace)
                returned = [event for event in trace['events'] if event['type'] == 'returned']
                self.assertEqual([event['color'] for event in returned], [0, 1, 0, 1])
                for event in returned:
                    self.assertEqual(event['search']['evaluation']['configuration_id'], expected[event['color']])
                workers = trace['workers']
                self.assertNotEqual(workers[0]['pid'], workers[1]['pid'])
                self.assertTrue(all(worker['reaped'] for worker in workers))


if __name__ == '__main__':
    unittest.main()
