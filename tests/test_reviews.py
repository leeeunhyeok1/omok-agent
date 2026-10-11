# AI-written by OpenAI Codex, for issue #44.
import tempfile
import json
import unittest
from pathlib import Path

from tests import test_screening
from offline.registry import digest


class ReviewTests(unittest.TestCase):
    def test_review_retains_incumbent_and_explains_screening_without_probing(self):
        from offline.reviews import review_batch
        with tempfile.TemporaryDirectory() as directory:
            stage, raw, incumbent, candidate = test_screening.ScreeningTests().cohort(Path(directory))
            report = review_batch(stage, raw, max_failures=2)
            self.assertEqual(report['retained_incumbent'], incumbent.identity)
            self.assertEqual(report['strongest_verified'], incumbent.identity)
            self.assertEqual(report['strongest_screened'], candidate.identity)
            self.assertFalse(report['promotion']['performed'])
            self.assertEqual(report['candidates'][candidate.identity]['selection'], 'advance')
            self.assertEqual(len(report['failures']), 2)
            self.assertEqual({f['color'] for f in report['failures']}, {0, 1})
            self.assertTrue(any(f['inspection']['positions'] for f in report['failures']))
            self.assertEqual(report['deeper_analysis'], None)
            self.assertEqual(report['source']['raw_identity'], digest(raw))

    def test_confirmed_missed_win_is_additive_and_tiny_budget_stays_unknown(self):
        from offline.regressions import analyze_tactic, export_regression, verify_regression
        from offline.inspection import inspect_loss
        from offline.runner import run_game
        from omok.simulator import Position
        from tests.test_runner import ReturningPlayer
        board = [[-1] * 19 for _ in range(19)]
        board[9][4] = 1
        board[9][5:9] = [0] * 4
        trace = run_game(ReturningPlayer(0, [(0, 0)]), ReturningPlayer(1, []),
                         initial=Position(board, 0), move_cap=1)
        record = inspect_loss(trace, color=0)['positions'][0]
        partial = analyze_tactic(record, kind='immediate-win', max_transitions=1, max_seconds=10)
        self.assertEqual(partial['status'], 'unknown')
        self.assertIsNone(partial['allowed_moves'])
        analysis = analyze_tactic(record, kind='immediate-win', max_transitions=361, max_seconds=30)
        self.assertEqual(analysis['allowed_moves'], [[9, 9]])
        self.assertTrue(analysis['confirmed_failure'])
        self.assertEqual(analysis['budget']['max_transitions'], 361)
        with tempfile.TemporaryDirectory() as directory:
            path = export_regression(Path(directory), trace, ply=0, color=0, analysis=analysis)
            original = path.read_bytes()
            verify_regression(json.loads(original))
            self.assertEqual(export_regression(Path(directory), trace, ply=0, color=0, analysis=analysis), path)
            self.assertEqual(path.read_bytes(), original)
            analysis['allowed_moves'] = [[0, 0]]
            with self.assertRaises(ValueError):
                export_regression(Path(directory), trace, ply=0, color=0, analysis=analysis)

    def test_incomplete_reviews_keep_unknown_strength_and_preserve_all_saved_files(self):
        from offline.reviews import review_saved_run, render_review
        from offline.optimizer import run
        from tests import test_optimizer
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            test_optimizer.OptimizerTests().setup_run(root)
            run(root / 'run', max_games=0)
            before = {p: p.read_bytes() for p in (root / 'run').rglob('*.json')}
            report = review_saved_run(root / 'run')
            self.assertEqual(report['failures'], [])
            self.assertIsNone(report['strongest_verified'])
            self.assertTrue(all(c['fitness'] is None for c in report['candidates'].values()))
            self.assertEqual(before, {p: p.read_bytes() for p in (root / 'run').rglob('*.json')})
            self.assertIn('throughput', render_review(report))

    def test_engine_change_needs_separate_lineage_and_bounded_comparison(self):
        from offline.reviews import record_engine_change
        proposal = dict(problem='missed capture defenses', scope=['omok/tactics.py'],
            behavior='retain all verified defenses', correctness_gates=['simulator', 'public player'],
            comparison_plan='remeasure compatible incumbent on the same frozen training league',
            parent_engine_lineage='engine-a', new_engine_lineage='engine-b',
            compatible_incumbents=['incumbent-a'], new_run='run-b')
        report = record_engine_change({'source': 'controlled evidence'}, proposal)
        self.assertEqual(report['engine_change']['new_run'], 'run-b')
        proposal['new_engine_lineage'] = 'engine-a'
        with self.assertRaises(ValueError):
            record_engine_change({}, proposal)

    def test_saved_eligibility_reasons_are_visible_and_foreign_batches_rejected(self):
        from offline.reviews import review_batch, include_promotion, render_review
        from tests import test_promotion
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record, raw, _, candidate = test_promotion.PromotionTests().cohort(root, training_regression=True)
            evidence = {'check_identity': digest(record), 'raw': raw}
            (root / 'checks/eligibility-results.json').write_text(
                json.dumps({'identity': digest(evidence), 'data': evidence}), encoding='utf-8')
            confirmation = record['confirmation']
            review = review_batch(confirmation['selection'], confirmation['selection_raw'], max_failures=1)
            attached = include_promotion(review, root / 'checks')
            self.assertIn('historical_regression', render_review(attached))
            self.assertIn('reject', render_review(attached))
            self.assertFalse(attached['promotion']['performed'])
            prior = confirmation['selection_context']['prior_rungs'][0]
            earlier = review_batch(prior['stage'], prior['raw'], max_failures=1)
            self.assertIn('historical_regression', render_review(include_promotion(earlier, root / 'checks')))
            del review['candidates'][candidate.identity]
            with self.assertRaisesRegex(ValueError, 'another review cohort'):
                include_promotion(review, root / 'checks')
            review = review_batch(confirmation['selection'], confirmation['selection_raw'], max_failures=1)
            review['source']['stage_identity'] = 'different-batch'
            with self.assertRaisesRegex(ValueError, 'another reviewed stage'):
                include_promotion(review, root / 'checks')
            review['source']['stage_identity'] = digest(confirmation['selection'])
            plan_id = next(iter(review['source']['plan_evidence_identities']))
            review['source']['plan_evidence_identities'][plan_id] = 'different-evidence'
            with self.assertRaisesRegex(ValueError, 'differs from reviewed evidence'):
                include_promotion(review, root / 'checks')
