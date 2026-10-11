# AI-written by OpenAI Codex, for issue #42.
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from offline.registry import PoolSnapshot, Entry, canonical
from offline.experiments import ExperimentPlan
from offline.promotion import PromotionPolicy, prepare, assess, run
from tests.test_experiments import entry
from tests.test_matches import scoring_start
from tests.test_screening import passed_gates, results
from offline.confirmation import ConfirmationPolicy, prepare as confirm
from offline.league import LeaguePolicy, prepare as league, archive_history
from offline.screening import ScreeningPolicy, prepare as screen
from offline.runner import run_game
from offline.experiments import opening_record
from omok.simulator import Position
import copy
import json


CONDITIONS = {'power': 'controlled test', 'load': 'controlled test', 'other_experiments_stopped': True}


class SequencePlayer:
    def __init__(self, color, moves):
        self.color, self.moves = color, iter(moves)

    def take_turn(self, board, time):
        return next(self.moves)


def controlled_results(plan, outcomes, spent=0):
    """Replay-valid legal traces with controlled outcomes/time, not actual agent strength."""
    records = []
    for job, outcome in zip(plan.data['jobs'], outcomes):
        winner = job['candidate_color'] if outcome == 'win' else 1 - job['candidate_color']
        start = job['opening']
        if start['moves']:
            moves = [[(2, 4) if winner == 0 else (0, 0)], [(7, 5)]]
        else:
            moves = [[(2 + c * 5, i if winner == c else i * 2) for i in range(5)] for c in (0, 1)]
        ticks = iter([value for i in range(10) for value in (i * spent / 1000, (i + 1) * spent / 1000)])
        trace = run_game(*(SequencePlayer(c, moves[c]) for c in (0, 1)),
            initial=Position(start['board'], start['side_to_move']),
            budgets_ms=tuple(plan.data['settings']['budgets_ms']), move_cap=plan.data['settings']['move_cap'],
            clock=lambda: next(ticks))
        records.append({k: job[k] for k in ('game_id', 'match_id', 'slot', 'candidate_color')} |
            dict(status=trace['status'], trace=trace, error=None, segment='controlled'))
    return dict(format='omok-experiment-results-v1', manifest_identity=plan.identity, results=records,
        segments=[dict(id='controlled', conditions={'workers': 1, 'contention': canonical(CONDITIONS)})])


def legal_opening():
    return [[2, i] if c == 0 else [7, i + 1] for i in range(4) for c in (0, 1)]


class PromotionTests(unittest.TestCase):
    def cohort(self, root, training_regression=False, confirmation_regression=False,
               prior_training_failure=False, suite_identity=None, candidate_names=('candidate',), **policy_settings):
        incumbent = entry('incumbent')
        candidates = [entry(name) for name in candidate_names]
        candidate = candidates[0]
        old = entry('old')
        pool = PoolSnapshot.freeze({'training': [entry('line'), entry('capture')],
            'validation': [entry('valid')], 'holdout': [entry('reserved')]})
        gates = passed_gates([incumbent] + candidates)
        if suite_identity is not None:
            for records in gates.values():
                for gate in records:
                    if gate['check'] == 'mandatory_tactic':
                        gate['suite_identity'] = suite_identity
        settings = dict(opponents={'line': 4}, opponent_weights={'line': 1},
            family_weights={'line': 1}, move_cap=2, min_evidence_per_color=1)
        ScreeningPolicy.create(**settings).save(root / 'screen-policy.json')
        selected = screen(root / 'screen-policy.json', incumbent, candidates, pool,
            output=root / 'screen', openings=[legal_opening()], gates=gates)
        def evidence(stage, fresh=False):
            raw = {}
            for m in stage['members']:
                for p in m['plans']:
                    baseline = m['entry']['identity'] == incumbent.identity
                    outcome = 'loss' if baseline else 'win'
                    if (training_regression or (fresh and confirmation_regression)) and p['settings']['opponents'] == ['old']:
                        outcome = 'win' if baseline else 'loss'
                    raw[p['identity']] = controlled_results(ExperimentPlan.from_record(p), [outcome] * len(p['jobs']))
            return raw
        settings.update(opponents={n: 16 if n == 'incumbent' else 4 for n in ('line', 'capture', 'incumbent', 'old')},
            opponent_weights={n: 1 for n in ('line', 'capture', 'incumbent', 'old')},
            family_weights={n: 1 for n in ('line', 'capture', 'incumbent', 'old')})
        LeaguePolicy.create(screening=ScreeningPolicy.create(**settings, seed=40).data,
            history_slots={old.identity: 0}, max_family_regression=1, max_matchup_regression=1,
            max_color_regression=1).save(root / 'league-policy.json')
        archived = archive_history(root / 'history', [old])
        previous = []
        if prior_training_failure:
            from offline.registry import digest
            from offline.experiments import save_new_json
            from tests.test_matches import FailurePlayer, MovePlayer
            earlier = league(root / 'league-policy.json', incumbent, pool, history=archived,
                rungs=[(root / 'screen', evidence(selected))], output=root / 'earlier',
                openings=[legal_opening()], gates=gates)
            old_raw = evidence(earlier['screening'])
            member = next(m for m in earlier['screening']['members'] if m['entry']['identity'] == candidate.identity)
            plan = member['plans'][0]
            start = plan['jobs'][0]['opening']
            trace = run_game(FailurePlayer(0, 'exception'), MovePlayer(1, (0, 1)),
                initial=Position(start['board'], 0), move_cap=2, budgets_ms=(5000, 5000))
            old_raw[plan['identity']]['results'][0].update(status=trace['status'], trace=trace)
            data = {'stage': earlier, 'raw': old_raw}
            save_new_json(root / 'earlier/league-results.json', {'identity': digest(data), 'data': data})
            previous = [root / 'earlier']
        broad = league(root / 'league-policy.json', incumbent, pool,
            history=archived, rungs=[(root / 'screen', evidence(selected))],
            output=root / 'league', openings=[legal_opening()], gates=gates,
            round_index=len(previous), previous_rounds=previous)
        ConfirmationPolicy.create(screening=ScreeningPolicy.create(**settings, seed=43).data,
            max_family_regression=1, max_color_regression=1).save(root / 'confirm-policy.json')
        fresh = confirm(root / 'confirm-policy.json', selection=root / 'league', selection_raw=evidence(broad['screening']),
            output=root / 'confirmation', openings=[legal_opening()])
        PromotionPolicy.create(validation={'valid': 4}, official_opponents=['valid'], **policy_settings).save(root / 'policy.json')
        snapshot = PoolSnapshot.from_record(fresh['pool_snapshot'])
        record = prepare(root / 'policy.json', incumbent, snapshot, output=root / 'checks',
            prior_exposures=[dict(source='Phase 4', details='previous validation games; limited independence')],
            confirmation=root / 'confirmation', confirmation_raw=evidence(fresh, fresh=True), openings=[legal_opening()])
        raw = {}
        for stage_name in ('validation', 'official'):
            for member in record[stage_name]['members']:
                for saved in member['plans']:
                    plan = ExperimentPlan.from_record(saved)
                    raw[plan.identity] = controlled_results(plan, ['win'] * len(saved['jobs']))
        return record, raw, incumbent, candidate

    def test_complete_controlled_evidence_can_be_eligible_without_promoting(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            report = assess(root / 'checks', raw)
            self.assertEqual(report['candidates'][candidate.identity]['status'], 'eligible')
            self.assertEqual(report['eligible'], [candidate.identity])
            self.assertEqual(report['retained_incumbent'], incumbent.identity)
            self.assertFalse(report['promotion'])

    def test_historical_and_family_regression_veto_positive_training_gain(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root, training_regression=True)
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'reject')
            self.assertIn('historical_regression', chosen['reasons'])
            self.assertIn('family_regression', chosen['reasons'])

    def test_new_confirmation_regression_cannot_use_looser_earlier_margins(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root, confirmation_regression=True)
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'reject')
            self.assertIn('confirmation_historical_regression', chosen['reasons'])

    def test_candidate_failure_in_earlier_training_round_remains_a_veto(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root, prior_training_failure=True)
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'reject')
            self.assertTrue(chosen['vetoes'])

    def test_per_color_validation_regression_vetoes_favorable_aggregate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            member = next(m for m in record['validation']['members'] if m['entry']['identity'] == candidate.identity)
            plan = ExperimentPlan.from_record(member['plans'][0])
            raw[plan.identity] = controlled_results(plan, ['win', 'loss'] * 2)
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'reject')
            self.assertIn('per_color_regression', chosen['reasons'])

    def test_validation_regression_rejects_a_training_winner(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            member = next(m for m in record['validation']['members'] if m['entry']['identity'] == candidate.identity)
            plan = ExperimentPlan.from_record(member['plans'][0])
            raw[plan.identity] = controlled_results(plan, ['loss'] * 4)
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'reject')
            self.assertIn('validation_regression', chosen['reasons'])

    def test_missing_official_games_or_conditions_remain_inconclusive(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            member = next(m for m in record['official']['members'] if m['entry']['identity'] == candidate.identity)
            key = member['plans'][0]['identity']
            raw[key]['segments'][0]['conditions']['workers'] = 2
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIn('unverified_official_conditions', chosen['reasons'])
            raw[key]['results'].pop()
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIn('official_completion_required', chosen['reasons'])

    def test_timing_policy_regression_rejects_even_completed_wins(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            member = next(m for m in record['official']['members'] if m['entry']['identity'] == candidate.identity)
            plan = ExperimentPlan.from_record(member['plans'][0])
            raw[plan.identity] = controlled_results(plan, ['win'] * 8, spent=500)
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'reject')
            self.assertIn('timing_policy_regression', chosen['reasons'])

    def test_official_execution_conditions_must_be_comparable_to_incumbent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            member = next(m for m in record['official']['members'] if m['entry']['identity'] == candidate.identity)
            raw[member['plans'][0]['identity']]['segments'][0]['conditions']['cpu'] = 'different hardware'
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIn('incomparable_official_conditions', chosen['reasons'])

    def test_reliability_failure_is_a_veto_even_when_other_games_win(self):
        from tests.test_matches import FailurePlayer, MovePlayer
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            member = next(m for m in record['official']['members'] if m['entry']['identity'] == candidate.identity)
            plan = ExperimentPlan.from_record(member['plans'][0])
            trace = run_game(FailurePlayer(0, 'exception'), MovePlayer(1, (0, 0)), move_cap=plan.data['settings']['move_cap'])
            raw[plan.identity]['results'][0].update(status=trace['status'], trace=trace)
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'reject')
            self.assertTrue(chosen['vetoes'])

    def test_saved_policy_forbids_single_match_promotion_and_detects_changed_clocks(self):
        with self.assertRaisesRegex(ValueError, 'Single-match'):
            PromotionPolicy.create(validation={'valid': 4}, official_opponents=['valid'], min_incumbent_games=8)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root)
            with self.assertRaises(FileExistsError):
                PromotionPolicy.load(root / 'policy.json').save(root / 'policy.json')
            path = root / 'checks/eligibility.json'
            envelope = json.loads(path.read_text())
            envelope['checks']['official']['members'][0]['plans'][0]['settings']['budgets_ms'] = [1000, 1000]
            path.write_text(json.dumps(envelope))
            with self.assertRaisesRegex(ValueError, 'identity'):
                assess(root / 'checks', raw)

    def test_capped_and_sparse_validation_do_not_support_eligibility(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, incumbent, candidate = self.cohort(root, min_validation_pairs=3)
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIn('insufficient_distinct_pairs', chosen['reasons'])
            plan = ExperimentPlan.from_record(record['validation']['members'][1]['plans'][0])
            start = plan.data['jobs'][0]['opening']
            trace = run_game(SequencePlayer(0, [(0, 0)]), SequencePlayer(1, [(0, 1)]),
                initial=Position(start['board'], 0), move_cap=2, budgets_ms=(5000, 5000))
            raw[plan.identity]['results'][0].update(status=trace['status'], trace=trace)
            chosen = assess(root / 'checks', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIn('validation_incomplete_coverage', chosen['reasons'])

    def test_failed_tactical_gate_and_missing_gate_cannot_pass_incumbent_audit(self):
        for status in ('fail', 'inconclusive'):
            with self.subTest(status=status), TemporaryDirectory() as directory:
                root = Path(directory)
                incumbent = entry('incumbent')
                snapshot = PoolSnapshot.freeze({'training': [incumbent], 'validation': [entry('valid')], 'holdout': []})
                gates = passed_gates([incumbent])
                gates[incumbent.identity][-1]['status'] = status
                PromotionPolicy.create(validation={'valid': 4}, official_opponents=['valid']).save(root / 'policy.json')
                record = prepare(root / 'policy.json', incumbent, snapshot, output=root / 'checks',
                    gates=gates, prior_exposures=[], openings=[legal_opening()])
                raw = {p['identity']: controlled_results(ExperimentPlan.from_record(p), ['win'] * len(p['jobs']))
                       for stage in ('validation', 'official') for m in record[stage]['members'] for p in m['plans']}
                chosen = assess(root / 'checks', raw)['candidates'][incumbent.identity]
                self.assertEqual(chosen['status'], 'reject' if status == 'fail' else 'inconclusive')

    def test_prior_reliability_exposure_cannot_be_erased_by_successful_recheck(self):
        from offline.registry import digest
        from offline.experiments import save_new_json
        from tests.test_matches import FailurePlayer, MovePlayer
        with TemporaryDirectory() as directory:
            root = Path(directory)
            incumbent = entry('incumbent')
            snapshot = PoolSnapshot.freeze({'training': [incumbent], 'validation': [entry('valid')], 'holdout': []})
            PromotionPolicy.create(validation={'valid': 4}, official_opponents=['valid']).save(root / 'policy.json')
            record = prepare(root / 'policy.json', incumbent, snapshot, output=root / 'first',
                prior_exposures=[], gates=passed_gates([incumbent]), openings=[legal_opening()])
            raw = {p['identity']: controlled_results(ExperimentPlan.from_record(p), ['win'] * len(p['jobs']))
                   for stage in ('validation', 'official') for m in record[stage]['members'] for p in m['plans']}
            clean = copy.deepcopy(raw)
            plan = record['official']['members'][0]['plans'][0]
            trace = run_game(FailurePlayer(0, 'exception'), MovePlayer(1, (0, 0)), move_cap=plan['settings']['move_cap'])
            raw[plan['identity']]['results'][0].update(status=trace['status'], trace=trace)
            data = {'check_identity': digest(record), 'raw': raw}
            save_new_json(root / 'first/eligibility-results.json', {'identity': digest(data), 'data': data})
            prepare(root / 'policy.json', incumbent, snapshot, output=root / 'second', prior_exposures=[],
                gates=passed_gates([incumbent]), openings=[legal_opening()], previous_checks=[root / 'first'])
            chosen = assess(root / 'second', clean)['candidates'][incumbent.identity]
            self.assertEqual(chosen['status'], 'reject')
            self.assertTrue(chosen['vetoes'])

    def test_resume_keeps_validation_exposure_and_rejects_lost_checkpoint(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            incumbent = entry('incumbent')
            snapshot = PoolSnapshot.freeze({'training': [incumbent], 'validation': [entry('valid')], 'holdout': []})
            PromotionPolicy.create(validation={'valid': 2}, official_opponents=['valid'], validation_cap=2).save(root / 'policy.json')
            record = prepare(root / 'policy.json', incumbent, snapshot, output=root / 'checks',
                prior_exposures=[], gates=passed_gates([incumbent]), fixture=scoring_start())
            declaration = (root / 'checks/eligibility.json').read_bytes()
            partial = run(root / 'checks', conditions=CONDITIONS, max_jobs_per_plan=1)
            again = run(root / 'checks', conditions=CONDITIONS, max_jobs_per_plan=0)
            self.assertEqual(partial['eligible'], again['eligible'])
            self.assertEqual((root / 'checks/eligibility.json').read_bytes(), declaration)
            path = root / 'checks' / record['validation']['members'][0]['plans'][0]['identity'] / 'checkpoint.json'
            path.unlink()
            with self.assertRaisesRegex(ValueError, 'checkpoint'):
                run(root / 'checks', conditions=CONDITIONS, max_jobs_per_plan=0)
            with self.assertRaisesRegex(ValueError, 'stop other experiments'):
                run(root / 'checks', conditions=CONDITIONS | {'other_experiments_stopped': False}, max_jobs_per_plan=1)

    def test_incumbent_validation_is_explicit_and_balanced_with_prior_exposure(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            incumbent, opponent = entry('incumbent'), entry('validation')
            snapshot = PoolSnapshot.freeze({'training': [incumbent], 'validation': [opponent], 'holdout': []})
            PromotionPolicy.create(validation={'validation': 4}, official_opponents=['validation']).save(root / 'policy.json')
            record = prepare(root / 'policy.json', incumbent, snapshot, output=root / 'checks',
                gates=passed_gates([incumbent]), fixture=scoring_start(),
                prior_exposures=[{'source': 'Phase 4', 'details': 'already played validation'}])
            plan = ExperimentPlan.from_record(record['validation']['members'][0]['plans'][0])
            self.assertEqual(plan.data['settings']['purpose'], 'validation')
            self.assertEqual([j['candidate_color'] for j in plan.data['jobs']], [0, 1, 0, 1])
            raw = {plan.identity: results(plan, ['win'] * 4)}
            report = assess(root / 'checks', raw)
            self.assertFalse(report['promotion'])
            self.assertEqual(report['retained_incumbent'], incumbent.identity)
            self.assertFalse(report['untouched_final_evidence'])
            self.assertEqual(report['prior_exposures'][0]['source'], 'Phase 4')

    def test_optimizer_checks_reject_holdout_and_reserved_role_switch(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            incumbent, reserved, valid = entry('incumbent'), entry('reserved'), entry('valid')
            snapshot = PoolSnapshot.freeze({'training': [incumbent], 'validation': [valid], 'holdout': [reserved]})
            PromotionPolicy.create(validation={'valid': 4}, official_opponents=['reserved']).save(root / 'policy.json')
            with self.assertRaisesRegex(ValueError, 'holdout'):
                prepare(root / 'policy.json', incumbent, snapshot, output=root / 'checks', prior_exposures=[])
            data = reserved.data
            data['logical_id'] = 'renamed'
            with self.assertRaisesRegex(ValueError, 'protected'):
                prepare(root / 'policy.json', Entry(canonical(data)), snapshot,
                    output=root / 'role-switch', prior_exposures=[])


if __name__ == '__main__':
    unittest.main()
