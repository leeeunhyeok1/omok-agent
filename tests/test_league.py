# AI-written by OpenAI Codex, for issue #40.
import tempfile
import unittest
import json
from pathlib import Path

from offline.experiments import ExperimentPlan
from offline.league import LeaguePolicy, prepare, assess, archive_history, run
from offline.batches import atomic_json
from offline.registry import digest
from offline.registry import PoolSnapshot, Entry, canonical
from offline.screening import ScreeningPolicy, prepare as screen
from tests.test_experiments import entry
from tests.test_matches import scoring_start
from tests.test_screening import passed_gates, results


class LeagueTests(unittest.TestCase):
    def cohort(self, root, *, history=(), round_index=0, previous_rounds=(), missing=False):
        incumbent, candidate = entry('incumbent'), entry('candidate')
        opponents = [entry('line'), entry('capture')]
        if missing:
            data = entry('external').data
            data.update(availability='pending', origin='supplied',
                        acknowledgment='Requested external opponent; file not supplied')
            opponents.append(Entry(canonical(data)))
        pool = PoolSnapshot.freeze({'training': opponents, 'validation': [], 'holdout': []})
        ScreeningPolicy.create(opponents={'line': 4}, opponent_weights={'line': 1},
            family_weights={'line': 1}, move_cap=2).save(root / 'screen-policy.json')
        rung = screen(root / 'screen-policy.json', incumbent, [candidate], pool,
            output=root / 'screen', fixture=scoring_start(), gates=passed_gates([incumbent, candidate]))
        raw = {p['identity']: results(ExperimentPlan.from_record(p),
                   ['loss'] * 4 if m['entry']['identity'] == incumbent.identity else ['win'] * 4)
               for m in rung['members'] for p in m['plans']}
        archived = archive_history(root / 'archive', list(history))
        names = ['line', 'capture', 'incumbent'] + [e.data['logical_id'] for e in history]
        if missing:
            names.append('external')
        families = {e.data['family'] for e in opponents + [incumbent] + list(history)}
        policy = LeaguePolicy.create(screening=ScreeningPolicy.create(
            opponents={n: 4 for n in names}, opponent_weights={n: 1 for n in names},
            family_weights={f: 1 for f in families}, move_cap=2).data,
            history_slots={e.identity: 0 for e in history}, history_period=2)
        policy.save(root / 'league-policy.json')
        stage = prepare(root / 'league-policy.json', incumbent, pool, history=archived,
            rungs=[(root / 'screen', raw)], output=root / 'league', round_index=round_index,
            previous_rounds=list(previous_rounds), fixture=scoring_start(),
            gates=passed_gates([incumbent, candidate]))
        return stage, incumbent, candidate

    def evidence(self, stage, incumbent, outcomes):
        raw = {}
        for m in stage['screening']['members']:
            for record in m['plans']:
                plan = ExperimentPlan.from_record(record)
                name = plan.data['settings']['opponents'][0]
                raw[plan.identity] = results(plan, ['draw'] * 4
                    if m['entry']['identity'] == incumbent.identity else outcomes[name])
        return raw

    def test_beating_incumbent_cannot_hide_diverse_league_losses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            raw = self.evidence(stage, incumbent,
                {'line': ['loss'] * 4, 'capture': ['loss'] * 4, 'incumbent': ['win'] * 4})
            report = assess(root / 'league', raw)
            chosen = report['candidates'][candidate.identity]
            self.assertEqual(chosen['fitness'], 1 / 3)
            self.assertEqual(chosen['status'], 'fail')
            self.assertEqual(chosen['by_opponent']['incumbent']['value'], 1)
            self.assertEqual(len(report['prior_rungs']), 1)
            self.assertFalse(report['promotion'])

    def test_high_aggregate_cannot_hide_historical_or_color_regression(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root, history=[entry('old')])
            raw = self.evidence(stage, incumbent, {'line': ['win'] * 4,
                'capture': ['win'] * 4, 'incumbent': ['win'] * 4, 'old': ['loss'] * 4})
            chosen = assess(root / 'league', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['fitness'], .75)
            self.assertEqual(chosen['status'], 'fail')
            self.assertIn('league_regression', chosen['reasons'])
            self.assertTrue(any(r['name'] == 'old' for r in chosen['regressions']))
            raw = self.evidence(stage, incumbent, {n: ['win', 'loss'] * 2
                for n in ('line', 'capture', 'incumbent', 'old')})
            chosen = assess(root / 'league', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['by_color'], {'black': 1, 'white': 0})
            self.assertTrue(any(r['name'] == 'white' for r in chosen['regressions']))

    def test_related_variants_do_not_gain_influence_from_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = []
            for name in ('old-a', 'old-b'):
                data = entry(name).data
                data['family'] = 'shared-history'
                old.append(Entry(canonical(data)))
            stage, incumbent, candidate = self.cohort(root, history=old)
            raw = self.evidence(stage, incumbent, {'line': ['win'] * 4,
                'capture': ['win'] * 4, 'incumbent': ['win'] * 4,
                'old-a': ['loss'] * 4, 'old-b': ['loss'] * 4})
            chosen = assess(root / 'league', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['fitness'], .75)
            self.assertEqual(chosen['by_family']['shared-history'], 0)

    def save_results(self, root, stage, raw):
        data = {'stage': stage, 'raw': raw}
        atomic_json(root / 'league/league-results.json', {'identity': digest(data), 'data': data})

    def test_history_rotation_and_later_promotion_preserve_artifacts_and_incumbent_remeasurement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = entry('old')
            first = root / 'first'
            first.mkdir()
            stage0, incumbent, _ = self.cohort(first, history=[old])
            raw = self.evidence(stage0, incumbent, {n: ['win'] * 4 for n in ('line', 'capture', 'incumbent', 'old')})
            self.save_results(first, stage0, raw)
            second = root / 'second'
            second.mkdir()
            stage1, _, candidate = self.cohort(second, history=[old], round_index=1,
                previous_rounds=[first / 'league'])
            self.assertEqual(stage1['selected_history'], [])
            self.assertNotEqual(stage0['screening']['members'][0]['plans'][0]['identity'],
                                stage1['screening']['members'][0]['plans'][0]['identity'])
            raw = self.evidence(stage1, incumbent, {n: ['win'] * 4 for n in ('line', 'capture', 'incumbent')})
            self.save_results(second, stage1, raw)
            third = root / 'third'
            third.mkdir()
            stage2, _, _ = self.cohort(third, history=[old, entry('newly-promoted')], round_index=2,
                previous_rounds=[first / 'league', second / 'league'])
            self.assertEqual(len(stage2['selected_history']), 2)
            self.assertNotEqual(stage0['screening']['pool_snapshot']['identity'], stage2['screening']['pool_snapshot']['identity'])
            raw = self.evidence(stage2, incumbent, {n: ['win'] * 4
                for n in ('line', 'capture', 'incumbent', 'old', 'newly-promoted')})
            report = assess(third / 'league', raw)
            self.assertEqual(report['historical_gaps'], [])
            self.assertEqual(report['candidates'][candidate.identity]['status'], 'advance')
            original = (first / 'archive' / (old.identity + '.json')).read_bytes()
            archive_history(first / 'archive', [entry('newly-promoted')])
            self.assertEqual((first / 'archive' / (old.identity + '.json')).read_bytes(), original)
            self.assertEqual(len(archive_history(first / 'archive', [])['champions']), 2)

    def test_unavailable_opponents_and_prior_historical_gaps_remain_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root, history=[entry('old')], missing=True)
            raw = self.evidence(stage, incumbent, {n: ['win'] * 4 for n in ('line', 'capture', 'incumbent', 'old')})
            for m in stage['screening']['members']:
                for p in m['plans']:
                    if p['settings']['opponents'] == ['old']:
                        raw[p['identity']]['results'].pop()
            report = assess(root / 'league', raw)
            self.assertEqual(report['candidates'][candidate.identity]['unavailable_opponents'], ['external'])
            self.assertIsNone(report['candidates'][candidate.identity]['fitness'])
            self.assertFalse(next(iter(report['history_coverage'].values()))['complete'])
            self.save_results(root, stage, raw)
            following = root / 'next'
            following.mkdir()
            next_stage, incumbent, candidate = self.cohort(following, history=[entry('old')],
                round_index=1, previous_rounds=[root / 'league'])
            raw = self.evidence(next_stage, incumbent, {n: ['win'] * 4 for n in ('line', 'capture', 'incumbent')})
            report = assess(following / 'league', raw)
            self.assertEqual(report['candidates'][candidate.identity]['status'], 'inconclusive')
            self.assertEqual(len(report['historical_gaps']), 1)

    def test_real_dispatch_resumes_without_repeating_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.cohort(root)
            partial = run(root / 'league', max_jobs_per_plan=1)
            self.assertTrue(all(c['fitness'] is None for c in partial['candidates'].values()))
            final = run(root / 'league')
            again = run(root / 'league')
            self.assertEqual(final['advanced'], again['advanced'])
            self.assertEqual({i: (m['status'], m['fitness'], m['reliability_samples'])
                              for i, m in final['candidates'].items()},
                             {i: (m['status'], m['fitness'], m['reliability_samples'])
                              for i, m in again['candidates'].items()})
            self.assertEqual(sum(c['reliability_samples']['committed_attempts'] for c in final['candidates'].values()), 24)

    def test_failed_gates_and_pending_results_cannot_advance_broad_league(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            raw = self.evidence(stage, incumbent, {n: ['win'] * 4 for n in ('line', 'capture', 'incumbent')})
            member = next(m for m in stage['screening']['members'] if m['entry']['identity'] == candidate.identity)
            raw[member['plans'][0]['identity']]['results'].pop()
            chosen = assess(root / 'league', raw)['candidates'][candidate.identity]
            self.assertIsNone(chosen['fitness'])
            self.assertEqual(chosen['status'], 'inconclusive')
            member['gates'][0]['status'] = 'fail'
            atomic_json(root / 'league/league.json', {'identity': digest(stage), 'stage': stage})
            self.assertEqual(assess(root / 'league', raw)['candidates'][candidate.identity]['status'], 'fail')

    def test_archive_corruption_and_removed_rotation_slot_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = entry('old')
            archive_history(root / 'archive', [old])
            path = root / 'archive' / (old.identity + '.json')
            record = json.loads(path.read_text())
            source = next(iter(record['bundle']['sources']))
            record['bundle']['sources'][source] = 'AA=='
            record['identity'] = digest(record['bundle'])
            atomic_json(path, record)
            with self.assertRaisesRegex(ValueError, 'source mismatch'):
                archive_history(root / 'archive', [])
            first = root / 'first'
            first.mkdir()
            stage, incumbent, _ = self.cohort(first, history=[old])
            raw = self.evidence(stage, incumbent, {n: ['win'] * 4 for n in ('line', 'capture', 'incumbent', 'old')})
            self.save_results(first, stage, raw)
            second = root / 'second'
            second.mkdir()
            with self.assertRaisesRegex(ValueError, 'delete versions'):
                self.cohort(second, round_index=1, previous_rounds=[first / 'league'])


if __name__ == '__main__':
    unittest.main()
