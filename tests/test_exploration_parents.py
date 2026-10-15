"""Controlled parent-selection evidence; these tests play no games."""
from copy import deepcopy
import unittest

from offline import evolution


class ExplorationParentsTests(unittest.TestCase):
    def reports(self):
        good = dict(status='advance', fitness=.7, reasons=[], vetoes=[])
        screened = dict(candidates={'a': good, 'b': good | {'fitness': .6}}, advanced=['a', 'b'])
        broader = dict(candidates={i: deepcopy(m) for i, m in screened['candidates'].items()}, advanced=[])
        for member in broader['candidates'].values():
            member.update(status='fail', reasons=['league_regression'])
        return screened, broader

    def test_new_policy_keeps_exploration_separate_from_league_advancement(self):
        screened, broader = self.reports()
        ranked = evolution.parent_candidates(evolution.EXPLORATION_SELECTION, screened, broader)
        self.assertEqual(ranked, ['a', 'b'])
        self.assertEqual(broader['advanced'], [])
        self.assertEqual(evolution.parent_candidates(evolution.SELECTION, screened, broader), [])

    def test_known_later_failure_or_incomplete_evidence_cannot_parent(self):
        for reason in ('reliability_veto', 'incomplete_coverage', 'invalid_attempt_evidence',
                       'external_gates_not_passed', 'suspicious_censoring', 'historical_schedule_incomplete'):
            with self.subTest(reason=reason):
                screened, broader = self.reports()
                broader['candidates']['a']['reasons'].append(reason)
                self.assertEqual(evolution.parent_candidates(evolution.EXPLORATION_SELECTION,
                                                           screened, broader), ['b'])
        screened, broader = self.reports()
        broader['candidates']['a']['vetoes'] = [{'check': 'timeout'}]
        self.assertEqual(evolution.parent_candidates(evolution.EXPLORATION_SELECTION, screened, broader), ['b'])

    def test_fresh_training_failure_or_check_reliability_veto_excludes_candidate(self):
        screened, broader = self.reports()
        confirmed = dict(candidates={'a': dict(status='inconclusive', reasons=['incomplete_coverage'], vetoes=[])})
        self.assertEqual(evolution.parent_candidates(evolution.EXPLORATION_SELECTION, screened, broader,
                                                   confirmed), ['b'])
        checks = dict(candidates={'a': dict(vetoes=[{'check': 'crash'}])})
        self.assertEqual(evolution.parent_candidates(evolution.EXPLORATION_SELECTION, screened, broader,
                                                   checks=checks), ['b'])

    def test_validation_strength_values_do_not_rank_parents(self):
        screened, broader = self.reports()
        checks = dict(candidates={'a': dict(vetoes=[], validation=dict(reasons=[], fitness=0),
                                             official=dict(reasons=[]), clock=dict(reasons=[]))})
        self.assertEqual(evolution.parent_candidates(evolution.EXPLORATION_SELECTION, screened, broader,
                                                   checks=checks), ['a', 'b'])
        checks['candidates']['a']['validation']['reasons'] = ['score_regression', 'insufficient_pairs']
        self.assertEqual(evolution.parent_candidates(evolution.EXPLORATION_SELECTION, screened, broader,
                                                   checks=checks), ['a', 'b'])
        checks['candidates']['a']['official']['reasons'] = ['incomplete_coverage']
        self.assertEqual(evolution.parent_candidates(evolution.EXPLORATION_SELECTION, screened, broader,
                                                   checks=checks), ['b'])

    def test_nonadvanced_screening_is_never_used_and_ties_use_identity(self):
        screened, broader = self.reports()
        screened['advanced'] = ['b']
        self.assertEqual(evolution.parent_candidates(evolution.EXPLORATION_SELECTION, screened, broader), ['b'])
        screened['advanced'] = ['b', 'a']
        screened['candidates']['b']['fitness'] = .7
        self.assertEqual(evolution.parent_candidates(evolution.EXPLORATION_SELECTION, screened, broader), ['a', 'b'])


class RecipeTests(unittest.TestCase):
    def test_profiles_initialize_without_dispatch_and_simple_jobs_are_distinct(self):
        import json
        from pathlib import Path
        import subprocess
        import sys
        from tempfile import TemporaryDirectory
        from offline import screening
        from offline.registry import Entry, PoolSnapshot, canonical
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            for profile in ('all24', 'balanced', 'simple-focused'):
                with self.subTest(profile=profile):
                    output = Path(directory) / profile
                    result = subprocess.run([sys.executable,
                        str(root / 'docs/colab-training/initialize-all24-colab.py'),
                        '--profile', profile, '--output', str(output)], text=True,
                        capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)['games_started'], 0)
                    state = evolution.status(output)
                    self.assertEqual(state['rounds'], [])
                    basis = json.loads((output / 'evolution.json').read_text())['data']
                    p = basis['policy']
                    self.assertEqual(p['selection'], evolution.SELECTION if profile == 'all24'
                                     else evolution.EXPLORATION_SELECTION)
                    if profile == 'simple-focused':
                        entry = Entry.from_record(basis['incumbent'])
                        pool = PoolSnapshot.from_record(basis['snapshot'])
                        stages = []
                        for name in ('screening', 'league', 'confirmation'):
                            sp = p[name] if name == 'screening' else p[name]['screening']
                            stage = screening.build_stage(screening.ScreeningPolicy(canonical(sp)),
                                entry, [], pool, openings=p[name + '_openings'])
                            plan = next(r for r in stage['members'][0]['plans']
                                        if r['settings']['opponents'] == ['simple'])
                            keys = {(j['candidate_color'], canonical(j['opening'])) for j in plan['jobs']}
                            self.assertEqual(len(keys), 8)
                            stages.append({canonical(j['opening']) for j in plan['jobs']})
                        self.assertFalse(stages[0] & stages[2])

    def test_targeted_profile_preserves_champion_gates_and_engine_settings(self):
        import json
        from pathlib import Path
        directory = Path(__file__).resolve().parents[1] / 'docs/colab-training'
        original = json.loads((directory / 'all24-colab-setup.json').read_text())
        targeted = json.loads((directory / 'simple-focused-colab-setup.json').read_text())
        self.assertEqual(targeted['configuration'], original['configuration'])
        self.assertEqual(targeted['policy']['promotion'], original['policy']['promotion'])
        for key in ('max_matchup_regression', 'max_color_regression', 'max_family_regression'):
            self.assertEqual(targeted['policy']['league'][key], original['policy']['league'][key])
        self.assertEqual(targeted['policy']['confirmation']['min_families'],
                         original['policy']['confirmation']['min_families'])

    def test_balanced_profile_changes_only_exploratory_selection(self):
        import json
        from pathlib import Path
        directory = Path(__file__).resolve().parents[1] / 'docs/colab-training'
        original = json.loads((directory / 'all24-colab-setup.json').read_text())
        balanced = json.loads((directory / 'balanced-colab-setup.json').read_text())
        self.assertEqual(balanced['policy']['selection'], evolution.EXPLORATION_SELECTION)
        balanced['policy']['selection'] = original['policy']['selection']
        self.assertEqual(balanced, original)


class ExploratoryAncestryIntegrationTests(unittest.TestCase):
    def test_league_rejected_parent_reaches_next_population_across_resume(self):
        """Fabricated worker games check orchestration, not actual playing strength."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from offline import screening
        from offline.champions import ChampionStore
        from offline.registry import Entry
        from offline.runner import run_game
        from tests.test_evolution import small_snapshot
        from tests.test_promotion import SequencePlayer, legal_opening

        parent = Entry.local('current-material', module='omok.player', factory='IterativePlayer',
            source_paths=('omok', 'players', 'configs'), origin='local-engine', family='omok',
            acknowledgment='Local AI-written engine', variant='current-material',
            diagnostics=('search',), limitations='Controlled mechanics only.')
        policy = evolution.starter_policy(parent)
        policy.update(selection=evolution.EXPLORATION_SELECTION,
                      population_size=2, validation_every=100)
        policy['screening_openings'] = policy['league_openings'] = [legal_opening()]
        for name in ('screening', 'league', 'confirmation'):
            sp = policy[name] if name == 'screening' else policy[name]['screening']
            sp.update(opponents={'smoke': 2, 'synthetic-aggressive': 2},
                      min_evidence_per_color=1, move_cap=20)

        def fake_gates(entry, suite_identity, **kwargs):
            return [dict(check=check, status='pass', samples=1, suite_identity=suite_identity,
                         evidence={'scope': 'FABRICATED integration mechanics'})
                    for check in screening.GATES]

        def fake_worker(*specs, initial, budgets_ms, move_cap, config, **kwargs):
            job = config['experiment']['job']
            candidate = config['experiment']['candidate']['identity']
            # Mutations beat external opponents but lose to the retained incumbent.
            # The baseline wins its synthetic self matchup and loses externally.
            wins = (candidate != parent.identity) != (job['opponent']['identity'] == parent.identity)
            winner = job['candidate_color'] if wins else 1 - job['candidate_color']
            stones = [(r, c) for r, row in enumerate(initial.board)
                      for c, value in enumerate(row) if value == winner]
            row = stones[0][0]
            last = max(c for r, c in stones if r == row)
            moves = [[(0, 0)], [(0, 1)]]
            moves[winner] = [(row, last + 1)]
            return run_game(*(SequencePlayer(c, moves[c]) for c in (0, 1)), initial=initial,
                budgets_ms=budgets_ms, move_cap=move_cap, clock=lambda: 0, config=config)

        def stop_at(boundary):
            def interrupt(event):
                if event == boundary:
                    raise RuntimeError('controlled ' + boundary)
            return interrupt

        with TemporaryDirectory() as directory:
            output = Path(directory) / 'search'
            evolution.initialize(output, incumbent=parent, policy=policy, snapshot=small_snapshot())
            with patch('offline.evolution.gates.evaluate', side_effect=fake_gates), \
                 patch('offline.supervised.preflight_player', return_value={'ready': True}), \
                 patch('offline.supervised.run_supervised_game', side_effect=fake_worker):
                with self.assertRaisesRegex(RuntimeError, 'controlled round committed'):
                    evolution.run(output, max_games=200, max_seconds=120, max_rounds=1,
                                  interrupt=stop_at('round committed'))
                committed = evolution.status(output)
                round0 = committed['rounds'][0]
                self.assertEqual(round0['stage'], 'committed')
                self.assertFalse(round0['stages']['league']['report']['advanced'])
                exploratory = round0['decision']['exploratory_parents']
                self.assertEqual(len(exploratory), 1)
                rejected = round0['stages']['league']['report']['candidates'][exploratory[0]]
                self.assertIn('league_regression', rejected['reasons'])
                self.assertEqual(committed['incumbent']['identity'], parent.identity)
                with self.assertRaisesRegex(RuntimeError, 'controlled proposal persisted'):
                    evolution.run(output, max_games=200, max_seconds=120, max_rounds=1,
                                  interrupt=stop_at('proposal persisted'))
                resumed = evolution.status(output)
                round1 = resumed['rounds'][1]
                self.assertEqual(round1['parents'], round0['decision']['parents'])
                self.assertIn(exploratory[0], [r['entry']['identity']
                                             for r in round1['population']['parents']])
                self.assertIn(exploratory[0], {identity for ancestry in
                    round1['population']['ancestry'].values() for identity in ancestry})
                unchanged = evolution.run(output, max_games=0, max_seconds=0)
                self.assertEqual(unchanged['rounds'], resumed['rounds'])
                self.assertEqual(unchanged['incumbent']['identity'], parent.identity)
                self.assertEqual(len(ChampionStore(output / 'champions').load()['transactions']), 0)
