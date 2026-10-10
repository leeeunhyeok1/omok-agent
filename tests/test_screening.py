# AI-written by OpenAI Codex, for issue #38.
import copy
import tempfile
import unittest
from pathlib import Path

from offline.experiments import ExperimentPlan
from offline.registry import PoolSnapshot
from offline.screening import ScreeningPolicy, prepare, assess, run
from offline.runner import run_game
from offline.registry import Entry, canonical, digest
from tests.test_experiments import entry
from tests.test_matches import scoring_start, MovePlayer, FailurePlayer


def passed_gates(entries):
    return {e.identity: [dict(check=check, status='pass', samples=1,
                             evidence='controlled gate fixture')
                         for check in ('restoration', 'invalid_score', 'mandatory_tactic')]
            for e in entries}


def results(plan, outcomes):
    records = []
    for job, outcome in zip(plan.data['jobs'], outcomes):
        color = job['candidate_color']
        winner = color if outcome == 'win' else 1 - color if outcome == 'loss' else None
        move = {0: (2, 4), 1: (7, 5), None: (8, 10)}[winner]
        trace = run_game(MovePlayer(0, move), MovePlayer(1, (0, 1)), initial=scoring_start(),
                         move_cap=plan.data['settings']['move_cap'],
                         budgets_ms=tuple(plan.data['settings']['budgets_ms']))
        records.append({k: job[k] for k in ('game_id', 'match_id', 'slot', 'candidate_color')} |
                       dict(status=trace['status'], trace=trace, error=None))
    return dict(format='omok-experiment-results-v1', manifest_identity=plan.identity, results=records)


class ScreeningTests(unittest.TestCase):
    def cohort(self, root, *, deterministic=False, gates=True):
        support = 'deterministic' if deterministic else 'constructor'
        incumbent, candidate = entry('incumbent', seed_support=support), entry('candidate', seed_support=support)
        snapshot = PoolSnapshot.freeze({'training': [entry('opponent', seed_support=support)],
                                        'validation': [], 'holdout': []})
        policy = ScreeningPolicy.create(opponents={'opponent': 4}, opponent_weights={'opponent': 1},
                                        family_weights={'opponent': 1}, move_cap=2)
        policy.save(root / 'policy.json')
        stage = prepare(root / 'policy.json', incumbent, [candidate], snapshot, output=root / 'stage',
                        fixture=scoring_start(), gates=passed_gates([incumbent, candidate]) if gates else None)
        raw = {r['identity']: results(ExperimentPlan.from_record(r),
                ['loss'] * 4 if m['entry']['identity'] == incumbent.identity else ['win'] * 4)
               for m in stage['members'] for r in m['plans']}
        return stage, raw, incumbent, candidate

    def test_saved_policy_weights_families_opponents_and_colors_without_micro_averaging(self):
        incumbent, candidate = entry('incumbent'), entry('candidate')
        snapshot = PoolSnapshot.freeze({'training': [entry('first'), entry('second')],
                                        'validation': [], 'holdout': []})
        policy = ScreeningPolicy.create(opponents={'first': 8, 'second': 2},
            opponent_weights={'first': 1, 'second': 1}, family_weights={'first': 3, 'second': 1},
            min_evidence_per_color=1, move_cap=2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy.save(root / 'policy.json')
            stage = prepare(root / 'policy.json', incumbent, [candidate], snapshot,
                            output=root / 'stage', fixture=scoring_start(), gates=passed_gates([incumbent, candidate]))
            raw = {}
            for member in stage['members']:
                for record in member['plans']:
                    plan = ExperimentPlan.from_record(record)
                    outcomes = (['win', 'draw'] * 4 if plan.data['settings']['opponents'] == ['first']
                                else ['loss', 'loss']) if member['entry']['identity'] == candidate.identity else ['loss'] * 8
                    raw[plan.identity] = results(plan, outcomes)
            report = assess(root / 'stage', raw)
            selected = report['candidates'][candidate.identity]
            self.assertEqual(selected['fitness'], .5625)
            self.assertEqual(selected['status'], 'advance')
            self.assertEqual(selected['by_opponent']['first']['by_color']['black']['denominator'], 4)
            self.assertEqual(selected['by_opponent']['second']['by_color']['white']['denominator'], 1)
            self.assertEqual(report['retained_incumbent'], incumbent.identity)
            self.assertFalse(report['promotion'])

    def test_related_opponent_weights_and_declared_color_weights_are_applied(self):
        incumbent, candidate = entry('incumbent'), entry('candidate')
        variants = []
        for name in ('first', 'second'):
            data = entry(name).data
            data['family'] = 'shared'
            variants.append(Entry(canonical(data)))
        snapshot = PoolSnapshot.freeze({'training': variants, 'validation': [], 'holdout': []})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ScreeningPolicy.create(opponents={'first': 8, 'second': 2},
                opponent_weights={'first': 3, 'second': 1}, family_weights={'shared': 1},
                color_weights={'black': 1, 'white': 3}, min_evidence_per_color=1,
                move_cap=2).save(root / 'policy.json')
            stage = prepare(root / 'policy.json', incumbent, [candidate], snapshot, output=root / 'stage',
                            fixture=scoring_start(), gates=passed_gates([incumbent, candidate]))
            raw = {}
            for member in stage['members']:
                for record in member['plans']:
                    plan = ExperimentPlan.from_record(record)
                    outcomes = ['win', 'draw'] * 4 if plan.data['settings']['opponents'] == ['first'] else ['loss', 'win']
                    if member['entry']['identity'] == incumbent.identity:
                        outcomes = ['loss'] * 8
                    raw[plan.identity] = results(plan, outcomes)
            chosen = assess(root / 'stage', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['by_opponent']['first']['value'], .625)
            self.assertEqual(chosen['by_opponent']['second']['value'], .75)
            self.assertEqual(chosen['fitness'], .65625)
            self.assertEqual(chosen['status'], 'advance')

    def test_partial_caps_and_missing_hard_opponents_never_supply_completed_fitness(self):
        for kind in ('pending', 'capped', 'infrastructure'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                stage, raw, incumbent, candidate = self.cohort(root)
                plan = ExperimentPlan.from_record(stage['members'][1]['plans'][0])
                record = raw[plan.identity]['results'][-1]
                if kind == 'pending':
                    raw[plan.identity]['results'].pop()
                elif kind == 'infrastructure':
                    record.update(status='setup_failed', trace=None, error={'message': 'unavailable'})
                else:
                    trace = run_game(MovePlayer(0, (0, 0)), MovePlayer(1, (0, 1)),
                                     initial=scoring_start(), budgets_ms=(5000, 5000), move_cap=2)
                    record.update(status=trace['status'], trace=trace)
                report = assess(root / 'stage', raw)
                chosen = report['candidates'][candidate.identity]
                self.assertIsNone(chosen['fitness'])
                self.assertEqual(chosen['partial_score'], 1)
                self.assertEqual(chosen['status'], 'inconclusive')
                self.assertEqual(report['advanced'], [])
                self.assertEqual(report['retained_incumbent'], incumbent.identity)
                if kind == 'capped':
                    self.assertIn('suspicious_censoring', chosen['reasons'])
                self.assertIsNone(chosen['reports'][0]['matches'][0]['tournament']['coins'])

    def test_duplicate_deterministic_games_do_not_meet_distinct_evidence_minimum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, raw, _, candidate = self.cohort(root, deterministic=True)
            chosen = assess(root / 'stage', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['fitness'], 1)
            self.assertEqual(chosen['by_opponent']['opponent']['by_color']['black']['distinct_evidence'], 1)
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIn('insufficient_distinct_evidence', chosen['reasons'])

    def test_candidate_failures_in_prior_attempts_veto_later_wins(self):
        for reason in ('exception', 'mutation', 'invalid_move', 'timeout'):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                stage, raw, _, candidate = self.cohort(root)
                plan = ExperimentPlan.from_record(stage['members'][1]['plans'][0])
                evidence = raw[plan.identity]
                previous = copy.deepcopy(evidence['results'][0])
                ticks = iter([0, 6])
                trace = run_game(FailurePlayer(0, reason), MovePlayer(1, (0, 1)), initial=scoring_start(),
                    budgets_ms=(5000, 5000), move_cap=2,
                    **({'clock': lambda: next(ticks)} if reason == 'timeout' else {}))
                previous.update(status=trace['status'], trace=trace, attempt_id='old', segment='s')
                attempts = [dict(game_id=previous['game_id'], attempt_id='old', segment='s', state='committed', result=previous)]
                for index, record in enumerate(evidence['results']):
                    record.update(attempt_id=str(index), segment='s')
                    attempts.append(dict(game_id=record['game_id'], attempt_id=str(index), segment='s', state='committed', result=record))
                evidence['attempts'] = attempts + [copy.deepcopy(attempts[-1])]
                chosen = assess(root / 'stage', raw)['candidates'][candidate.identity]
                self.assertEqual(chosen['fitness'], 1)
                self.assertEqual(chosen['status'], 'fail')
                self.assertEqual(len(chosen['vetoes']), 1)
                self.assertEqual(chosen['vetoes'][0]['attempt_id'], 'old')
                self.assertEqual(chosen['reports'][0]['all_attempts']['duplicate_deliveries'], 1)

    def test_missing_or_failed_external_gates_block_advancement(self):
        for kind in ('missing', 'restoration', 'invalid_score', 'mandatory_tactic'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                stage, raw, _, candidate = self.cohort(root, gates=kind != 'missing')
                if kind != 'missing':
                    gate = next(g for g in stage['members'][1]['gates'] if g['check'] == kind)
                    gate.update(status='fail', evidence={'position': 'fixed failing fixture', 'expected': 'unchanged'})
                    (root / 'stage/stage.json').write_text(canonical({'identity': digest(stage), 'stage': stage}))
                chosen = assess(root / 'stage', raw)['candidates'][candidate.identity]
                self.assertEqual(chosen['status'], 'inconclusive' if kind == 'missing' else 'fail')
                self.assertEqual(chosen['fitness'], 1)

    def test_validation_holdout_and_candidate_role_switches_are_rejected_before_dispatch(self):
        incumbent = entry('incumbent')
        reserved = entry('reserved')
        for pool in ('validation', 'holdout'):
            for role in ('candidate', 'opponent'):
                with self.subTest(pool=pool, role=role), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    snapshot = PoolSnapshot.freeze({'training': [entry('opponent')],
                        'validation': [reserved] if pool == 'validation' else [],
                        'holdout': [reserved] if pool == 'holdout' else []})
                    name = 'reserved' if role == 'opponent' else 'opponent'
                    ScreeningPolicy.create(opponents={name: 2}, opponent_weights={name: 1},
                        family_weights={name: 1}).save(root / 'policy.json')
                    record = reserved.data
                    record['logical_id'] = 'renamed-reserved'
                    alias = Entry(canonical(record))
                    with self.assertRaises(ValueError):
                        prepare(root / 'policy.json', incumbent, [alias] if role == 'candidate' else [entry('candidate')],
                                snapshot, output=root / 'stage')
                    self.assertFalse((root / 'stage').exists())

    def test_no_favorable_gain_retains_incumbent_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, raw, incumbent, candidate = self.cohort(root)
            for m in stage['members']:
                for r in m['plans']:
                    plan = ExperimentPlan.from_record(r)
                    raw[plan.identity] = results(plan, ['draw'] * 4)
            report = assess(root / 'stage', raw)
            self.assertEqual(report['candidates'][candidate.identity]['status'], 'fail')
            self.assertEqual(report['retained_incumbent'], incumbent.identity)
            self.assertEqual(report['advanced'], [])
            stage['policy']['policy']['min_gain'] = 0
            (root / 'stage/stage.json').write_text(canonical({'identity': digest(stage), 'stage': stage}))
            with self.assertRaisesRegex(ValueError, 'identity'):
                assess(root / 'stage', raw)

    def test_missing_opponents_remain_requested_and_block_full_stage_fitness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incumbent, candidate = entry('incumbent'), entry('candidate')
            unavailable = entry('missing').data
            unavailable['availability'] = 'pending'
            snapshot = PoolSnapshot.freeze({'training': [entry('opponent'), Entry(canonical(unavailable))],
                                            'validation': [], 'holdout': []})
            ScreeningPolicy.create(opponents={'opponent': 4, 'missing': 4},
                opponent_weights={'opponent': 1, 'missing': 1}, family_weights={'opponent': 1, 'missing': 1},
                move_cap=2).save(root / 'policy.json')
            stage = prepare(root / 'policy.json', incumbent, [candidate], snapshot,
                output=root / 'stage', fixture=scoring_start(), gates=passed_gates([incumbent, candidate]))
            raw = {r['identity']: results(ExperimentPlan.from_record(r), ['win'] * 4)
                   for m in stage['members'] for r in m['plans']}
            chosen = assess(root / 'stage', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['requested_jobs'], 8)
            self.assertEqual(chosen['unavailable_opponents'], ['missing'])
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIsNone(chosen['fitness'])

    def test_reliability_sample_sizes_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, raw, _, candidate = self.cohort(root)
            chosen = assess(root / 'stage', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['reliability_samples']['committed_attempts'], 4)
            self.assertEqual(chosen['reliability_samples']['candidate_failure_attempts'], 0)

    def test_infrastructure_retry_is_separate_and_preserves_sample_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, raw, _, candidate = self.cohort(root)
            plan = ExperimentPlan.from_record(stage['members'][1]['plans'][0])
            evidence = raw[plan.identity]
            previous = {**evidence['results'][0], 'attempt_id': 'infra', 'segment': 's',
                        'status': 'setup_failed', 'trace': None, 'error': {'message': 'temporary missing dependency'}}
            attempts = [dict(game_id=previous['game_id'], attempt_id='infra', segment='s', state='committed', result=previous)]
            for index, record in enumerate(evidence['results']):
                record.update(attempt_id=str(index), segment='s')
                attempts.append(dict(game_id=record['game_id'], attempt_id=str(index), segment='s', state='committed', result=record))
            evidence['attempts'] = attempts
            chosen = assess(root / 'stage', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'advance')
            self.assertEqual(chosen['reliability_samples']['committed_attempts'], 5)
            self.assertEqual(chosen['reports'][0]['all_attempts']['committed']['counts']['infrastructure_failed'], 1)
            # Imported results must obey the same saved bound as real dispatch.
            extra = copy.deepcopy(attempts[0])
            extra['attempt_id'] = 'excess'
            extra['result']['attempt_id'] = 'excess'
            evidence['attempts'].insert(1, extra)
            chosen = assess(root / 'stage', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIn('invalid_retry_history', chosen['reasons'])

    def test_real_dispatch_resumes_fixed_jobs_and_preserves_saved_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.cohort(root)
            saved = (root / 'stage/stage.json').read_bytes()
            partial = run(root / 'stage', max_jobs_per_plan=1)
            self.assertTrue(all(c['status'] == 'inconclusive' for c in partial['candidates'].values()))
            final = run(root / 'stage')
            self.assertEqual((root / 'stage/stage.json').read_bytes(), saved)
            for member in final['candidates'].values():
                self.assertEqual(member['reports'][0]['all_attempts']['total'], 4)
                self.assertEqual(member['reports'][0]['jobs']['counts']['pending'], 0)
            self.assertFalse(final['promotion'])
            again = run(root / 'stage')
            self.assertEqual([c['reports'][0]['all_attempts']['total'] for c in again['candidates'].values()], [4, 4])


if __name__ == '__main__':
    unittest.main()
