# AI-written by OpenAI Codex, for issue #43.
from pathlib import Path
from tempfile import TemporaryDirectory
import copy
import json
import shutil
import unittest
from unittest.mock import patch

from offline.champions import ChampionStore, commit_evidence, exported_spec
from offline.supervised import Supervision, preflight_player
from offline.batches import atomic_json
from tests import test_promotion, test_league
from offline.registry import Entry, PoolSnapshot, ROOT, canonical, digest
from offline.supervised import run_supervised_game
from offline.league import archive_history, prepare as prepare_league
from offline.experiments import ExperimentPlan, execute_job
from offline.proposals import resolve_entry
from tests.test_experiments import entry
from tests.test_screening import passed_gates
from tests.test_matches import scoring_start

FIXTURE_PLAYER = '''class FixturePlayer:
    def __init__(self, color, marker=17):
        self.color, self.marker, self.calls = color, marker, 0
    def take_turn(self, board, time):
        self.calls += 1
        return next((r, c) for r in range(19) for c in range(19) if board[r][c] == -1)
    def diagnostics(self):
        return {'marker': self.marker, 'calls': self.calls}
'''


class ChampionTests(unittest.TestCase):
    fixture = None

    @classmethod
    def cohort(cls, root):
        if cls.fixture is None:
            directory = TemporaryDirectory()
            cls.addClassCleanup(directory.cleanup)
            context = cls.context()
            base = Path(directory.name)
            cls.fixture = (base, test_promotion.PromotionTests().cohort(base,
                suite_identity=context['tactical_suite']['identity']))
        base, values = cls.fixture
        shutil.copytree(base, root, dirs_exist_ok=True)
        return copy.deepcopy(values)

    @staticmethod
    def context():
        sources = {'fixed-fixture.py': 'a' * 64}
        return {'run': 'controlled fixture', 'tactical_suite': {'identity': digest(sources), 'sources': sources}}

    def source_entry(self, root, name='old'):
        root.mkdir()
        shutil.copytree(ROOT / 'omok', root / 'omok', ignore=shutil.ignore_patterns('__pycache__'))
        (root / 'fixture_player.py').write_text(FIXTURE_PLAYER, encoding='utf-8')
        return Entry.local(name, module='fixture_player', factory='FixturePlayer', options={'marker': 17},
            source_root=root, source_paths=('omok', 'fixture_player.py'), origin='controlled',
            family='controlled', acknowledgment='Synthetic reload fixture')

    def test_baseline_requires_an_identified_fixed_tactical_suite(self):
        with TemporaryDirectory() as directory:
            store = ChampionStore(Path(directory) / 'store')
            with self.assertRaisesRegex(ValueError, 'tactical suite'):
                store.initialize(entry('incumbent'), context={'run': 'controlled fixture'}, reason='verified baseline')

    def test_changed_construction_adapter_cannot_be_archived_as_compatible(self):
        with TemporaryDirectory() as directory:
            store = ChampionStore(Path(directory) / 'store')
            data = entry('incumbent').data
            data['adapter_sources']['offline/registry_worker.py'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'adapter'):
                store.initialize(Entry(canonical(data)), context=self.context(), reason='baseline')

    def test_feasible_improved_candidate_promotes_and_rolls_back_exactly(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            context = self.context()
            record, raw, incumbent, candidate = self.cohort(root)
            store = ChampionStore(root / 'store')
            baseline = store.initialize(incumbent, context=context, reason='verified baseline',
                history=record['confirmation']['selection_context']['history'])
            with self.assertRaises(FileNotFoundError):
                store.promote(root / 'checks')
            self.assertEqual(store.load(), baseline)
            commit_evidence(root / 'checks', raw)
            decision = store.promote(root / 'checks')
            self.assertEqual(decision['winner'], candidate.identity)
            promoted = store.load()
            self.assertEqual(promoted['versions'][baseline['current']], baseline['versions'][baseline['current']])
            self.assertIn(incumbent.identity, store.history()['history_slots'])
            artifact = store.export(root / 'export/champion.json')
            self.assertEqual(artifact['version']['bundle']['entry'], candidate.record())
            self.assertTrue(preflight_player(exported_spec(root / 'export/champion.json'), 0, Supervision())['ready'])
            self.assertEqual(store.promote(root / 'checks'), decision)
            self.assertEqual(len(store.load()['transactions']), 1)
            restored = store.rollback(baseline['current'], reason='restore known baseline')
            self.assertEqual(restored['current'], baseline['current'])
            self.assertEqual(restored['versions'], promoted['versions'])
            self.assertEqual(store.promote(root / 'checks'), decision)
            self.assertEqual(store.load()['current'], baseline['current'])

    def test_unidentified_tactical_evidence_is_recorded_as_inconclusive(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            def remove_suite(value):
                if isinstance(value, dict):
                    value.pop('suite_identity', None)
                    for item in value.values():
                        remove_suite(item)
                elif isinstance(value, list):
                    for item in value:
                        remove_suite(item)
            remove_suite(record)
            atomic_json(root / 'checks/eligibility.json', {'identity': digest(record), 'checks': record})
            store = ChampionStore(root / 'store')
            initial = store.initialize(incumbent, context=self.context(), reason='baseline')
            commit_evidence(root / 'checks', raw)
            decision = store.promote(root / 'checks')
            self.assertIsNone(decision['winner'])
            self.assertEqual(decision['report']['candidates'][candidate.identity]['status'], 'inconclusive')
            self.assertIn('tactical_suite_identity_missing_or_changed',
                          decision['report']['candidates'][candidate.identity]['reasons'])
            self.assertEqual(store.load()['current'], initial['current'])

    def test_export_loads_retained_code_and_configuration_with_fresh_runtime_state(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            original = self.source_entry(source)
            store = ChampionStore(root / 'store')
            store.initialize(original, context=self.context(), reason='verified fixture')
            artifact = store.export(root / 'exports/player.json')
            (source / 'fixture_player.py').write_text('raise RuntimeError("mutable path changed")', encoding='utf-8')
            self.assertEqual(artifact['version']['bundle']['entry'], original.record())
            specs = [exported_spec(root / 'exports/player.json') for _ in (0, 1)]
            for _ in range(2):
                trace = run_supervised_game(*specs, move_cap=2, budgets_ms=(1000, 1000), diagnostics=True)
                self.assertEqual(trace['status'], 'capped')
                self.assertEqual([e['search'] for e in trace['events'] if e['type'] == 'returned'],
                                 [{'marker': 17, 'calls': 1}, {'marker': 17, 'calls': 1}])
                self.assertTrue(all(w['reaped'] for w in trace['workers']))

    def test_scheduled_history_executes_the_archive_after_original_sources_change(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            old = self.source_entry(source)
            store = ChampionStore(root / 'store')
            store.initialize(entry('incumbent'), context=self.context(), reason='baseline',
                history=archive_history(root / 'history', [old]), history_period=2)
            self.assertEqual([b['entry']['identity'] for b in store.history(0)['champions']], [old.identity])
            self.assertEqual(store.history(1)['champions'], [])
            stage, incumbent, candidate = test_league.LeagueTests().cohort(root, history=[old])
            pools = stage['screening']['pool_snapshot']['pools']
            pools['training'] = [old.record() if r['logical_id'] == 'old' else r for r in pools['training']]
            matched = prepare_league(root / 'league-policy.json', incumbent, PoolSnapshot(canonical(pools)),
                history=store.history(), rungs=[(root / 'screen', stage['prior_rungs'][0]['raw'])],
                output=root / 'existing-pool-league', fixture=scoring_start(), gates=passed_gates([incumbent, candidate]))
            self.assertIn('old', matched['screening']['requested_opponents'])
            saved = next(p for m in stage['screening']['members'] for p in m['plans']
                         if p['settings']['opponents'] == ['old'])
            (source / 'fixture_player.py').write_text('raise RuntimeError("old source gone")', encoding='utf-8')
            plan = ExperimentPlan.from_record(saved)
            detached = plan.data
            detached['jobs'][0]['opponent']['loader'] = {'kind': 'invalid'}
            job = next(j for j in plan.data['jobs'] if j['candidate_color'] == 1)
            result = execute_job(plan, job)
            self.assertEqual(result['status'], 'capped', result)
            self.assertEqual(next(e['search'] for e in result['trace']['events'] if e['type'] == 'returned'),
                             {'marker': 17, 'calls': 1})

    def test_interrupted_evidence_and_promotion_resume_without_duplicate_decisions(self):
        for event in ('before_evidence_commit', 'after_evidence_commit',
                      'before_champion_commit', 'after_champion_commit', 'during_champion_replace'):
            with self.subTest(event=event), TemporaryDirectory() as directory:
                root = Path(directory)
                record, raw, incumbent, candidate = self.cohort(root)
                store = ChampionStore(root / 'store')
                baseline = store.initialize(incumbent, context=self.context(), reason='baseline',
                    history=record['confirmation']['selection_context']['history'])
                def interrupt(point):
                    if point == event:
                        raise InterruptedError(point)
                if event.endswith('evidence_commit'):
                    with self.assertRaises(InterruptedError):
                        commit_evidence(root / 'checks', raw, interrupt=interrupt)
                    self.assertEqual(store.load(), baseline)
                    commit_evidence(root / 'checks', raw)
                else:
                    commit_evidence(root / 'checks', raw)
                    if event == 'during_champion_replace':
                        with patch('os.replace', side_effect=InterruptedError('filesystem interruption')):
                            with self.assertRaises(InterruptedError):
                                store.promote(root / 'checks')
                    else:
                        with self.assertRaises(InterruptedError):
                            store.promote(root / 'checks', interrupt=interrupt)
                    if event != 'after_champion_commit':
                        self.assertEqual(store.load(), baseline)
                resumed = ChampionStore(root / 'store')
                decision = resumed.promote(root / 'checks')
                self.assertEqual(decision['winner'], candidate.identity)
                self.assertEqual(len(resumed.load()['transactions']), 1)
                self.assertEqual(resumed.load()['versions'][baseline['current']], baseline['versions'][baseline['current']])

    def test_rejected_and_incomplete_candidates_record_reasons_and_retain_incumbent(self):
        for mode in ('reject', 'incomplete'):
            with self.subTest(mode=mode), TemporaryDirectory() as directory:
                root = Path(directory)
                record, raw, incumbent, candidate = self.cohort(root)
                stage = 'validation' if mode == 'reject' else 'official'
                member = next(m for m in record[stage]['members'] if m['entry']['identity'] == candidate.identity)
                saved = member['plans'][0]
                if mode == 'reject':
                    raw[saved['identity']] = test_promotion.controlled_results(ExperimentPlan.from_record(saved), ['loss'] * 4)
                else:
                    raw[saved['identity']]['results'] = []
                store = ChampionStore(root / 'store')
                initial = store.initialize(incumbent, context=self.context(), reason='baseline')
                commit_evidence(root / 'checks', raw)
                decision = store.promote(root / 'checks')
                self.assertIsNone(decision['winner'])
                self.assertEqual(store.load()['versions'], initial['versions'])
                self.assertEqual(store.load()['current'], initial['current'])
                assessment = decision['report']['candidates'][candidate.identity]
                self.assertEqual(assessment['status'], 'reject' if mode == 'reject' else 'inconclusive')
                self.assertTrue(assessment['reasons'])

    def test_corrupt_export_and_unknown_rollback_fail_without_changing_the_champion(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original = self.source_entry(root / 'source')
            store = ChampionStore(root / 'store')
            initial = store.initialize(original, context=self.context(), reason='baseline')
            path = root / 'exports/player.json'
            artifact = store.export(path)
            spec = exported_spec(path)
            name = 'fixture_player.py'
            artifact['version']['bundle']['sources'][name] = 'YmFk'  # "bad", inconsistent with promoted hash
            artifact['version_identity'] = digest(artifact['version'])
            atomic_json(path, {'identity': digest(artifact), 'data': artifact})
            self.assertFalse(preflight_player(spec, 0, Supervision())['ready'])
            with self.assertRaisesRegex(ValueError, 'known archived version'):
                store.rollback('unknown', reason='mistyped target')
            self.assertEqual(store.load(), initial)

    def test_two_eligible_candidates_choose_the_same_champion_in_reverse_completion_order(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            context = self.context()
            record, raw, incumbent, candidate = test_promotion.PromotionTests().cohort(source,
                suite_identity=context['tactical_suite']['identity'], candidate_names=('candidate-a', 'candidate-b'))
            candidates = [m['entry']['identity'] for m in record['validation']['members']
                          if m['entry']['identity'] != incumbent.identity]
            partial = root / 'partial'
            shutil.copytree(source, partial)
            pending = min(candidates)
            incomplete = copy.deepcopy(raw)
            member = next(m for m in record['official']['members'] if m['entry']['identity'] == pending)
            incomplete[member['plans'][0]['identity']]['results'] = []
            partial_store = ChampionStore(partial / 'store')
            initial = partial_store.initialize(incumbent, context=context, reason='baseline')
            commit_evidence(partial / 'checks', incomplete)
            pending_decision = partial_store.promote(partial / 'checks')
            self.assertIsNone(pending_decision['winner'])
            self.assertEqual(partial_store.load()['current'], initial['current'])
            self.assertIn('promotion_cohort_incomplete',
                          pending_decision['report']['candidates'][max(candidates)]['reasons'])
            decisions = []
            for name, reverse in (('forward', False), ('reverse', True)):
                path = root / name
                shutil.copytree(source, path)
                evidence = copy.deepcopy(raw)
                if reverse:
                    evidence = dict(reversed(list(evidence.items())))
                    for item in evidence.values():
                        item['results'].reverse()
                store = ChampionStore(path / 'store')
                store.initialize(incumbent, context=context, reason='baseline')
                commit_evidence(path / 'checks', evidence)
                decisions.append(store.promote(path / 'checks'))
                retained = {b['entry']['identity'] for b in store.history()['champions']}
                required = {b['entry']['identity'] for b in record['confirmation']['selection_context']['history']['champions']}
                self.assertTrue(required | {incumbent.identity} <= retained)
            self.assertTrue(all(set(d['report']['eligible']) == set(candidates) for d in decisions))
            self.assertEqual([d['winner'] for d in decisions], [min(candidates)] * 2)

    def test_store_known_history_cannot_be_omitted_from_promotion_evidence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            extra = self.source_entry(root / 'extra-source', name='extra-old')
            store = ChampionStore(root / 'store')
            initial = store.initialize(incumbent, context=self.context(), reason='baseline',
                history=archive_history(root / 'extra-history', [extra]))
            commit_evidence(root / 'checks', raw)
            decision = store.promote(root / 'checks')
            self.assertIsNone(decision['winner'])
            self.assertIn('retained_historical_coverage_missing',
                          decision['report']['candidates'][candidate.identity]['reasons'])
            self.assertEqual(store.load()['versions'], initial['versions'])

    def test_nondefault_engine_configuration_reloads_with_empty_score_caches(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original = Entry.local('basis', module='omok.player', factory='IterativePlayer', source_paths=('omok',),
                origin='local', family='omok', acknowledgment='Frozen local engine probe')
            config = resolve_entry(original)
            config['evaluation']['coefficients']['material'] = 19
            config['settings']['max_depth'] = 1
            config['settings']['max_nodes'] = 100
            config['settings']['table_capacity'] = 32
            data = original.data
            data['options'] = {'candidate_configuration': config}
            candidate = Entry(canonical(data))
            store = ChampionStore(root / 'store')
            store.initialize(candidate, context=self.context(), reason='exact configuration probe')
            store.export(root / 'export/engine.json')
            for _ in range(2):
                specs = [exported_spec(root / 'export/engine.json') for _ in (0, 1)]
                trace = run_supervised_game(*specs, move_cap=2, budgets_ms=(1, 1), clock=lambda: 0, diagnostics=True)
                returned = [e['search'] for e in trace['events'] if e['type'] == 'returned']
                self.assertEqual(trace['status'], 'capped')
                self.assertEqual(len(returned), 2)
                for report in returned:
                    self.assertEqual(json.loads(report['evaluation']['configuration']), config['evaluation'])
                    self.assertEqual(report['config']['max_depth'], 1)
                    self.assertEqual(report['config']['max_nodes'], 100)
                    self.assertEqual(report['config']['table_capacity'], 32)
                    self.assertEqual(report['config']['time_policy'], config['settings']['time_policy'])
                    self.assertEqual((report['table_size'], report['table_hits'], report['evaluation_cache_hits']), (0, 0, 0))

    def test_saved_historical_schedule_cannot_silently_change_at_promotion(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            history = record['confirmation']['selection_context']['history']
            store = ChampionStore(root / 'store')
            initial = store.initialize(incumbent, context=self.context(), reason='baseline', history=history,
                history_period=2, history_slots={b['entry']['identity']: 1 for b in history['champions']})
            commit_evidence(root / 'checks', raw)
            decision = store.promote(root / 'checks')
            self.assertIsNone(decision['winner'])
            self.assertIn('retained_historical_schedule_changed',
                          decision['report']['candidates'][candidate.identity]['reasons'])
            self.assertEqual(store.load()['history_slots'], initial['history_slots'])


if __name__ == '__main__':
    unittest.main()
