# AI-written by OpenAI Codex, for issue #41.
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from offline.confirmation import ConfirmationPolicy, prepare, assess, run
from offline.experiments import ExperimentPlan
from offline.screening import ScreeningPolicy, prepare as screen, assess as assess_screen
from offline.registry import PoolSnapshot
from tests.test_experiments import entry
from tests.test_matches import scoring_start
from tests.test_screening import passed_gates, results
from tests.test_matches import MovePlayer, FailurePlayer
from offline.runner import run_game
from omok.simulator import Position


def fixture_results(plan, outcomes):
    records = []
    start = plan.data['settings']['openings'][0]
    for job, outcome in zip(plan.data['jobs'], outcomes):
        color = job['candidate_color']
        winner = color if outcome == 'win' else 1 - color if outcome == 'loss' else None
        move = {0: (2, 4), 1: (7, 5), None: (8, 10)}[winner]
        trace = run_game(MovePlayer(0, move), MovePlayer(1, (0, 1)),
                         initial=Position(start['board'], start['side_to_move']),
                         move_cap=plan.data['settings']['move_cap'],
                         budgets_ms=tuple(plan.data['settings']['budgets_ms']))
        records.append({k: job[k] for k in ('game_id', 'match_id', 'slot', 'candidate_color')} |
                       dict(status=trace['status'], trace=trace, error=None))
    return dict(format='omok-experiment-results-v1', manifest_identity=plan.identity, results=records)


class ConfirmationTests(unittest.TestCase):
    def cohort(self, root, support='constructor', count=4, different_opening=False):
        incumbent, candidate = entry('incumbent', seed_support=support), entry('candidate', seed_support=support)
        snapshot = PoolSnapshot.freeze({'training': [entry('opponent', seed_support=support)],
                                        'validation': [], 'holdout': []})
        settings = dict(opponents={'opponent': count}, opponent_weights={'opponent': 1},
                        family_weights={'opponent': 1}, min_evidence_per_color=1, move_cap=2)
        ScreeningPolicy.create(**settings).save(root / 'selection-policy.json')
        initial = scoring_start()
        if different_opening:
            board = [list(row) for row in initial.board]
            board[18][18] = 0
            initial = Position(board, 0)
        selection = screen(root / 'selection-policy.json', incumbent, [candidate], snapshot,
                           output=root / 'selection', fixture=initial, gates=passed_gates([incumbent, candidate]))
        raw = self.evidence(selection, incumbent.identity, 'loss', 'win')
        self.assertEqual(assess_screen(root / 'selection', raw)['advanced'], [candidate.identity])
        ConfirmationPolicy.create(screening=ScreeningPolicy.create(**settings, seed=41).data,
                                  min_families=1).save(root / 'policy.json')
        stage = prepare(root / 'policy.json', selection=root / 'selection', selection_raw=raw,
                        output=root / 'confirmation', fixture=scoring_start())
        return stage, incumbent, candidate

    def evidence(self, stage, incumbent, incumbent_outcome, candidate_outcome):
        return {r['identity']: fixture_results(ExperimentPlan.from_record(r),
                [incumbent_outcome if m['entry']['identity'] == incumbent else candidate_outcome]
                * len(r['jobs'])) for m in stage['members'] for r in m['plans']}

    def test_screening_winner_can_lose_fresh_confirmation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            raw = self.evidence(stage, incumbent.identity, 'win', 'loss')
            report = assess(root / 'confirmation', raw)
            self.assertEqual(report['candidates'][candidate.identity]['status'], 'reject')
            self.assertEqual(report['candidates'][candidate.identity]['effect'], -1)
            self.assertEqual(report['retained_incumbent'], incumbent.identity)
            self.assertFalse(report['promotion'])

    def test_new_seed_cannot_make_identical_deterministic_games_fresh(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'fresh'):
                self.cohort(Path(directory), support='deterministic')

    def test_reordered_opening_with_same_position_is_not_fresh_deterministic_evidence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            incumbent, candidate = entry('incumbent', seed_support='deterministic'), entry('candidate', seed_support='deterministic')
            snapshot = PoolSnapshot.freeze({'training': [entry('opponent', seed_support='deterministic')],
                                            'validation': [], 'holdout': []})
            settings = dict(opponents={'opponent': 2}, opponent_weights={'opponent': 1},
                            family_weights={'opponent': 1}, min_evidence_per_color=1, move_cap=2)
            opening = [[9, c] if color == 0 else [10, c] for c in range(4) for color in (0, 1)]
            reordered = [list(move) for move in opening]
            reordered[0], reordered[2] = reordered[2], reordered[0]
            ScreeningPolicy.create(**settings).save(root / 'source-policy.json')
            source = screen(root / 'source-policy.json', incumbent, [candidate], snapshot,
                output=root / 'selection', openings=[opening], gates=passed_gates([incumbent, candidate]))
            raw = {}
            for member in source['members']:
                for saved in member['plans']:
                    records = []
                    for job in saved['jobs']:
                        winner = job['candidate_color'] if member['entry']['identity'] == candidate.identity else 1 - job['candidate_color']
                        start = job['opening']
                        trace = run_game(MovePlayer(0, (9, 4) if winner == 0 else (0, 0)), MovePlayer(1, (10, 4)),
                            initial=Position(start['board'], start['side_to_move']), budgets_ms=(5000, 5000), move_cap=2)
                        records.append({k: job[k] for k in ('game_id', 'match_id', 'slot', 'candidate_color')} |
                                       dict(status=trace['status'], trace=trace, error=None))
                    raw[saved['identity']] = dict(format='omok-experiment-results-v1', manifest_identity=saved['identity'], results=records)
            ConfirmationPolicy.create(screening=ScreeningPolicy.create(**settings, seed=41).data,
                                      min_families=1).save(root / 'policy.json')
            with self.assertRaisesRegex(ValueError, 'fresh'):
                prepare(root / 'policy.json', selection=root / 'selection', selection_raw=raw,
                        output=root / 'confirmation', openings=[reordered])

    def test_selection_results_cannot_be_imported_as_confirmation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.cohort(root)
            from offline.screening import load_stage
            source = load_stage(root / 'selection')
            with self.assertRaisesRegex(ValueError, 'Foreign'):
                assess(root / 'confirmation', self.evidence(source, source['incumbent'], 'loss', 'win'))

    def test_sparse_favorable_confirmation_retains_incumbent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root, count=2)
            report = assess(root / 'confirmation', self.evidence(stage, incumbent.identity, 'loss', 'win'))
            chosen = report['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertEqual(chosen['distinct_pairs'], 1)
            self.assertEqual(report['advanced'], [])

    def test_full_favorable_pairs_advance_with_descriptive_sensitivity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            chosen = assess(root / 'confirmation', self.evidence(stage, incumbent.identity, 'loss', 'win'))['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'advance')
            self.assertEqual(chosen['distinct_pairs'], 2)
            self.assertEqual(chosen['sensitivity_range'], [1, 1])
            self.assertFalse(chosen['independent_trials_assumed'])

    def test_gain_depending_on_one_pair_is_inconclusive(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            raw = self.evidence(stage, incumbent.identity, 'loss', 'win')
            chosen_plan = stage['members'][1]['plans'][0]
            raw[chosen_plan['identity']] = results(ExperimentPlan.from_record(chosen_plan), ['win', 'win', 'loss', 'loss'])
            chosen = assess(root / 'confirmation', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['effect'], .5)
            self.assertEqual(chosen['sensitivity_range'], [0, 1])
            self.assertEqual(chosen['status'], 'inconclusive')

    def test_changed_execution_conditions_block_comparison(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            raw = self.evidence(stage, incumbent.identity, 'loss', 'win')
            for index, evidence in enumerate(raw.values()):
                evidence['segments'] = [dict(id='s', conditions={'workers': index + 1, 'platform': 'fixture'})]
                for result in evidence['results']:
                    result['segment'] = 's'
            chosen = assess(root / 'confirmation', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIn('incomparable_execution_segments', chosen['reasons'])

    def test_broader_league_finalists_preserve_every_selection_rung(self):
        from tests.test_league import LeagueTests
        with TemporaryDirectory() as directory:
            root = Path(directory)
            helper = LeagueTests()
            league, incumbent, candidate = helper.cohort(root)
            raw = helper.evidence(league, incumbent, {n: ['win'] * 4 for n in ('line', 'capture', 'incumbent')})
            ConfirmationPolicy.create(screening=ScreeningPolicy.create(
                **{k: v for k, v in league['screening']['policy']['policy'].items() if k != 'seed'}, seed=41).data).save(root / 'confirm-policy.json')
            stage = prepare(root / 'confirm-policy.json', selection=root / 'league', selection_raw=raw,
                            output=root / 'confirmation', fixture=scoring_start())
            chosen = assess(root / 'confirmation', self.evidence(stage, incumbent.identity, 'loss', 'win'))['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'advance')
            self.assertEqual(set(chosen['by_family_effect']), {'line', 'capture', 'incumbent'})

    def test_real_dispatch_resumes_saved_jobs_and_rejects_lost_checkpoint(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            saved = (root / 'confirmation/confirmation.json').read_bytes()
            partial = run(root / 'confirmation', max_jobs_per_plan=1)
            self.assertEqual(partial['candidates'][candidate.identity]['status'], 'inconclusive')
            checkpoint = root / 'confirmation' / stage['members'][1]['plans'][0]['identity'] / 'checkpoint.json'
            old_checkpoint = checkpoint.read_bytes()
            final = run(root / 'confirmation')
            self.assertEqual(final['candidates'][candidate.identity]['reliability_samples']['committed_attempts'], 4)
            again = run(root / 'confirmation')
            self.assertEqual(again['candidates'][candidate.identity]['reliability_samples']['committed_attempts'], 4)
            self.assertEqual((root / 'confirmation/confirmation.json').read_bytes(), saved)
            current_checkpoint = checkpoint.read_bytes()
            checkpoint.write_bytes(old_checkpoint)
            with self.assertRaisesRegex(ValueError, 'authoritative'):
                run(root / 'confirmation', max_jobs_per_plan=0)
            checkpoint.write_bytes(current_checkpoint)
            checkpoint.unlink()
            with self.assertRaisesRegex(ValueError, 'authoritative'):
                run(root / 'confirmation', max_jobs_per_plan=0)

    def test_deterministic_or_unsupported_repeats_cannot_inflate_pair_counts(self):
        for support in ('deterministic', 'unsupported'):
            with self.subTest(support=support), TemporaryDirectory() as directory:
                root = Path(directory)
                stage, incumbent, candidate = self.cohort(root, support=support, count=8, different_opening=True)
                chosen = assess(root / 'confirmation', self.evidence(stage, incumbent.identity, 'loss', 'win'))['candidates'][candidate.identity]
                self.assertEqual(chosen['requested_jobs'], 8)
                self.assertEqual(chosen['distinct_pairs'], 1)
                self.assertEqual(chosen['effect'], 1)
                self.assertEqual(chosen['status'], 'inconclusive')

    def test_reliability_failure_vetoes_favorable_strength(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            raw = self.evidence(stage, incumbent.identity, 'loss', 'win')
            plan = stage['members'][1]['plans'][0]
            trace = run_game(FailurePlayer(0, 'exception'), MovePlayer(1, (0, 1)),
                             initial=scoring_start(), budgets_ms=(5000, 5000), move_cap=2)
            raw[plan['identity']]['results'][0].update(status=trace['status'], trace=trace)
            chosen = assess(root / 'confirmation', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'reject')
            self.assertEqual(chosen['reliability_samples']['candidate_failure_attempts'], 1)

    def test_related_opponents_share_weight_and_regression_cannot_hide_in_gain(self):
        from tests.test_league import LeagueTests
        from offline.registry import Entry, canonical
        with TemporaryDirectory() as directory:
            root = Path(directory)
            variants = []
            for name in ('old-a', 'old-b'):
                data = entry(name).data
                data['family'] = 'shared-history'
                variants.append(Entry(canonical(data)))
            helper = LeagueTests()
            league, incumbent, candidate = helper.cohort(root, history=variants)
            names = ('line', 'capture', 'incumbent', 'old-a', 'old-b')
            selection_raw = helper.evidence(league, incumbent, {n: ['win'] * 4 for n in names})
            ConfirmationPolicy.create(screening=ScreeningPolicy.create(
                **{k: v for k, v in league['screening']['policy']['policy'].items() if k != 'seed'}, seed=41).data).save(root / 'policy.json')
            stage = prepare(root / 'policy.json', selection=root / 'league', selection_raw=selection_raw,
                            output=root / 'confirmation', fixture=scoring_start())
            raw = self.evidence(stage, incumbent.identity, 'loss', 'win')
            for m in stage['members']:
                for plan in m['plans']:
                    if plan['settings']['opponents'][0].startswith('old-'):
                        raw[plan['identity']] = results(ExperimentPlan.from_record(plan),
                            ['win' if m['entry']['identity'] == incumbent.identity else 'loss'] * 4)
            chosen = assess(root / 'confirmation', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['effect'], .5)
            self.assertEqual(chosen['by_family_effect']['shared-history'], -1)
            self.assertEqual(chosen['status'], 'reject')

    def test_missing_confirmation_result_does_not_become_a_draw_or_gain(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            raw = self.evidence(stage, incumbent.identity, 'loss', 'win')
            raw[stage['members'][1]['plans'][0]['identity']]['results'].pop()
            chosen = assess(root / 'confirmation', raw)['candidates'][candidate.identity]
            self.assertEqual(chosen['status'], 'inconclusive')
            self.assertIsNone(chosen['fitness'])

    def test_saved_policy_and_manifest_refuse_overwrite_and_detect_tampering(self):
        import json
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stage, incumbent, candidate = self.cohort(root)
            with self.assertRaises(FileExistsError):
                ConfirmationPolicy.load(root / 'policy.json').save(root / 'policy.json')
            path = root / 'confirmation/confirmation.json'
            envelope = json.loads(path.read_text())
            envelope['confirmation']['policy']['min_pairs_per_opponent'] = 1
            path.write_text(json.dumps(envelope))
            with self.assertRaisesRegex(ValueError, 'identity'):
                assess(root / 'confirmation', self.evidence(stage, incumbent.identity, 'loss', 'win'))


if __name__ == '__main__':
    unittest.main()
