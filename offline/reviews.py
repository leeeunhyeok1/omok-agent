# AI-written by OpenAI Codex, for issue #44.
"""Compact reviews derived from saved training evidence; no player execution."""
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from offline.experiments import ExperimentPlan
from offline.inspection import inspect_loss
from offline.matches import game_score
from offline.registry import digest
from offline.reports import attempt_history
from offline.screening import assess_stage


def review_saved_run(output: Path, **settings: Any) -> dict[str, Any]:
    """Read authoritative optimizer/child checkpoints without resuming execution."""
    from offline.batches import Checkpoint
    from offline.optimizer import read_envelope, validate_manifest
    manifest = read_envelope(output / 'manifest.json', 'identity')
    validate_manifest(manifest)
    checkpoint = read_envelope(output / 'optimizer-checkpoint.json', 'sha256')
    if checkpoint['manifest_identity'] != digest(manifest):
        raise ValueError('Review checkpoint belongs to another optimizer run.')
    raw = {}
    for member in manifest['stage']['members']:
        for record in member['plans']:
            plan = ExperimentPlan.from_record(record)
            path = output / plan.identity / 'checkpoint.json'
            if not path.exists():
                if plan.identity in checkpoint['evidence']:
                    raise ValueError('Missing authoritative child evidence.')
                continue
            data = read_envelope(path, 'sha256')
            Checkpoint.validate_saved(plan, data)
            raw[plan.identity] = {'format': 'omok-experiment-results-v1', 'manifest_identity': plan.identity,
                'results': list(data['results'].values()), 'attempts': data['attempts'], 'segments': data['segments']}
    report = review_batch(manifest['stage'], raw, **settings)
    report['source']['optimizer_manifest_identity'] = digest(manifest)
    report['source']['optimizer_checkpoint_identity'] = digest(checkpoint)
    report['resources'].append({'optimizer_segments': checkpoint['segments'], 'progress': checkpoint['progress']})
    return report


def include_promotion(review: dict[str, Any], checks: Path) -> dict[str, Any]:
    """Reassess existing eligibility evidence, without validation/holdout execution."""
    from offline.optimizer import read_envelope
    from offline.promotion import load, assess_record_checks
    record = load(checks)
    evidence = read_envelope(checks / 'eligibility-results.json', 'identity')
    if evidence['check_identity'] != digest(record) or record['validation']['incumbent'] != review['retained_incumbent']:
        raise ValueError('Foreign promotion evidence.')
    validate_promotion_source(review, record)
    report = assess_record_checks(record, evidence['raw'])
    result = deepcopy(review)
    result['promotion'] = {'performed': False, 'status': 'saved eligibility assessment',
                           'evidence_identity': digest(evidence), 'assessment': report}
    return result


def evidence_identity(raw: dict[str, Any]) -> str:
    return digest({key: raw.get(key, []) for key in ('results', 'attempts', 'segments')})


def validate_promotion_source(review: dict[str, Any], record: dict[str, Any]) -> None:
    identities = {m['entry']['identity'] for m in record['validation']['members']}
    if not identities <= set(review['candidates']):
        raise ValueError('Promotion finalists belong to another review cohort.')
    confirmation = record['confirmation']
    if confirmation is None:
        if identities != {review['retained_incumbent']}:
            raise ValueError('Finalist promotion requires bound selection evidence.')
        return
    sources = [(confirmation['selection'], confirmation['selection_raw'])]
    def collect(context: dict[str, Any]) -> None:
        sources.extend((r['stage'], r['raw']) for r in context['prior_rungs'])
        for prior in context['prior_rounds']:
            sources.append((prior['stage']['screening'], prior['raw']))
            collect(prior['stage'])
    if confirmation['selection_context'] is not None:
        collect(confirmation['selection_context'])
    matching = [raw for stage, raw in sources if digest(stage) == review['source']['stage_identity']]
    if not matching:
        raise ValueError('Promotion selection belongs to another reviewed stage.')
    if not any(all(identity == evidence_identity(saved.get(plan, {}))
                   for plan, identity in review['source']['plan_evidence_identities'].items()) for saved in matching):
        raise ValueError('Promotion selection evidence differs from reviewed evidence.')


def include_champion_decision(review: dict[str, Any], store: Path, transaction: str) -> dict[str, Any]:
    from offline.champions import ChampionStore
    data = ChampionStore(store).load()
    decision = data['transactions'][transaction]
    previous = data['versions'][decision['previous']]['entry_identity']
    current = data['versions'][decision['current']]['entry_identity']
    if (decision['request']['kind'] != 'promotion' or previous != review['retained_incumbent']
            or current not in review['candidates']):
        raise ValueError('Champion decision is not for this review cohort/incumbent.')
    validate_promotion_source(review, data['evidence'][decision['request']['evidence']]['checks'])
    result = deepcopy(review)
    result['promotion'] = {'performed': current != previous, 'status': decision['reason'],
                           'transaction_identity': transaction, 'decision': decision}
    result['strongest_verified'] = current
    result['champion'] = current
    return result


def record_engine_change(review: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Record a bounded mechanism experiment separately from parameter optimization."""
    required = {'problem', 'scope', 'behavior', 'correctness_gates', 'comparison_plan',
                'parent_engine_lineage', 'new_engine_lineage', 'compatible_incumbents', 'new_run'}
    if (set(proposal) != required or any(not proposal[k] for k in required)
            or proposal['parent_engine_lineage'] == proposal['new_engine_lineage']):
        raise ValueError('Engine changes require bounded scope, gates, rebenchmark plan and separate lineage/run.')
    result = deepcopy(review)
    result['engine_change'] = deepcopy(proposal) | {'source_review_identity': digest(review),
        'status': 'proposal; rebenchmark compatible incumbents and start the declared new comparable run'}
    return result


def review_batch(stage: dict[str, Any], raw: dict[str, dict[str, Any]], *,
                 max_failures: int = 6, max_positions: int = 3) -> dict[str, Any]:
    """Review the declared cohort. Screening winners are not verified champions."""
    if type(max_failures) is not int or not 1 <= max_failures <= 100:
        raise ValueError('Failure sample bound must be 1..100.')
    if type(max_positions) is not int or not 1 <= max_positions <= 100:
        raise ValueError('Position sample bound must be 1..100.')
    assessed = assess_stage(stage, raw)
    candidates = {}
    losses = []
    resources = []
    for member in stage['members']:
        identity = member['entry']['identity']
        evidence = assessed['candidates'][identity]
        weak = sorted([{'opponent': name, 'color': color, **cell}
            for name, opponent in evidence['by_opponent'].items()
            for color, cell in opponent['by_color'].items()],
            key=lambda c: (c['value'] is None, c['value'] or 0, c['opponent'], c['color']))
        candidates[identity] = {'entry': member['entry'], 'selection': evidence['status'],
            'reasons': evidence['reasons'], 'fitness': evidence['fitness'],
            'partial_score': evidence['partial_score'], 'score_scope': evidence['score_scope'],
            'coverage': {'requested_jobs': evidence['requested_jobs'],
                'unavailable_opponents': evidence['unavailable_opponents'],
                'by_opponent': evidence['by_opponent'], 'cap_rate': evidence['cap_rate']},
            'reliability': evidence['reliability_samples'] | {
                'zero_observed_player_failures': evidence['zero_observed_player_failures'],
                'gates': evidence['gates']}, 'weak_matchups_colors': weak[:6],
            'timing': [r['metrics'] for r in evidence['reports']]}
        for record in member['plans']:
            plan = ExperimentPlan.from_record(record)
            saved = raw.get(plan.identity)
            if saved is None:
                continue
            resources.append({'candidate': identity, 'plan_identity': plan.identity,
                              'segments': saved.get('segments', []), 'conditions': saved.get('conditions'),
                              'observed_jobs': len(saved['results']),
                              'wall_seconds': sum(s.get('wall_seconds', 0) for s in saved.get('segments', [])) or None})
            jobs = {j['game_id']: j for j in plan.data['jobs']}
            attempts, _, _ = attempt_history(plan, saved)
            for attempt in attempts:
                if attempt['state'] != 'committed':
                    continue
                result = attempt['result']
                job = jobs[result['game_id']]
                scored = game_score(job, result, record)
                trace = result.get('trace')
                if not trace or 'validation_error' in scored:
                    continue
                failure = trace.get('failure') or trace.get('prior_result', {}).get('failure')
                candidate_failure = failure and failure['color'] == job['candidate_color']
                if scored['recognized_result'] != 'opponent_win' and not candidate_failure:
                    continue
                inspection = inspect_loss(trace, color=job['candidate_color'],
                                          max_positions=max_positions, history_limit=1000)
                # Spread positions over the whole game, not merely the final turns.
                turns = [i for i, m in enumerate(trace['moves']) if m['color'] == job['candidate_color']]
                if candidate_failure and trace['status'] in ('failed', 'capped'):
                    turns.append(len(trace['moves']))
                if turns:
                    count = min(max_positions, len(turns))
                    indices = sorted({round(i * (len(turns) - 1) / max(1, count - 1))
                                      for i in range(count)})
                    inspection = inspect_loss(trace, color=job['candidate_color'],
                        plies=[turns[i] for i in indices], max_positions=max_positions, history_limit=1000)
                    for position in inspection['positions']:
                        fraction = position['ply'] / max(1, len(trace['moves']))
                        position['game_phase'] = {'status': 'hypothesis', 'category':
                            'relative early' if fraction < 1 / 3 else 'relative middle' if fraction < 2 / 3 else 'relative late'}
                pressure = any(p['clocks_before_ms'][job['candidate_color']] <=
                    trace['budgets_ms'][job['candidate_color']] * .1 for p in inspection['positions'])
                losses.append({'candidate': identity, 'game_id': job['game_id'],
                    'attempt_id': attempt.get('attempt_id'), 'plan_identity': plan.identity,
                    'opponent': job['opponent'], 'color': job['candidate_color'],
                    'time_pressure': {'status': 'hypothesis', 'low_remaining_clock': pressure},
                    'inspection': inspection, 'source': {'trace_identity': digest(trace),
                        'trace': trace, 'job': job}})
    # Greedy diversity coverage with stable tie breaks. Samples remain descriptive.
    selected: list[dict[str, Any]] = []
    covered: set[tuple[str, Any]] = set()
    while losses and len(selected) < max_failures:
        def dimensions(loss: dict[str, Any]) -> set[tuple[str, Any]]:
            return {('candidate', loss['candidate']), ('opponent', loss['opponent']['identity']),
                    ('color', loss['color']), ('pressure', loss['time_pressure']['low_remaining_clock'])}
        losses.sort(key=lambda loss: (-len(dimensions(loss) - covered),
            loss['candidate'], loss['game_id'], loss['attempt_id'] or ''))
        loss = losses.pop(0)
        selected.append(loss)
        covered.update(dimensions(loss))
    ranked = sorted((i for i, e in assessed['candidates'].items()
                     if e['fitness'] is not None and e['status'] in ('advance', 'retain')),
                    key=lambda i: (-assessed['candidates'][i]['fitness'], i))
    return deepcopy({'format': 'omok-batch-review-v1',
        'source': {'stage_identity': digest(stage), 'raw_identity': digest(raw),
                   'plan_evidence_identities': {r['identity']: evidence_identity(raw.get(r['identity'], {}))
                       for m in stage['members'] for r in m['plans']},
                   'attribution': 'AI-written OpenAI Codex review; original entry/source provenance retained'},
        'strongest_verified': stage['incumbent'] if assessed['candidates'][stage['incumbent']]['status'] == 'retain' else None,
        'retained_incumbent': stage['incumbent'],
        'strongest_screened': ranked[0] if ranked else None,
        'promotion': {'performed': False, 'status': 'retain incumbent',
            'reasons': ['Screening alone does not verify or promote a champion.']},
        'candidates': candidates, 'resources': resources, 'failures': selected,
        'sampling': {'available': len(losses) + len(selected), 'exported': len(selected),
                     'policy': 'stable diversity across candidates/opponents/colors/clock pressure; spread game plies'},
        'deeper_analysis': None, 'next_bounded_experiment': {
            'action': 'fresh training confirmation' if assessed['advanced'] else 'investigate sampled training failures',
            'candidates': assessed['advanced'], 'max_positions': max_positions,
            'max_failures': max_failures, 'new_games_scheduled': 0,
            'proposed_max_new_games': sum(assessed['candidates'][i]['requested_jobs']
                for i in [stage['incumbent']] + assessed['advanced']) if assessed['advanced'] else 0,
            'proposed_analysis_budget': {'max_transitions': 361, 'max_seconds': 30},
            'condition': 'freeze fresh training jobs/policy before dispatch; no promotion from this review'},
        'limitations': 'Automatic categories, clock pressure and game-phase explanations are hypotheses; best strategic moves remain unknown.'})


def render_review(review: dict[str, Any]) -> str:
    """Human-sized summary; JSON companion retains complete sampled evidence."""
    lines = ['# Optimization batch review', '',
        f"Retained incumbent: `{review['retained_incumbent']}`.",
        f"Strongest verified candidate or retained incumbent: `{review['strongest_verified']}`.",
        f"Promotion: {review['promotion']['status']}.", '',
        '| Candidate | Selection | Fitness | Requested games | Candidate failure attempts | Reasons |',
        '| --- | --- | --- | --- | --- | --- |']
    for identity, candidate in sorted(review['candidates'].items()):
        lines.append(f"| {identity[:12]} | {candidate['selection']} | {candidate['fitness']} | "
            f"{candidate['coverage']['requested_jobs']} | {candidate['reliability']['candidate_failure_attempts']} | "
            f"{', '.join(candidate['reasons']) or 'saved gates passed'} |")
    lines.append('')
    promotion = review['promotion']
    assessment = promotion.get('assessment', promotion.get('decision', {}).get('report', {}))
    for identity, decision in sorted(assessment.get('candidates', {}).items()):
        lines.append(f"Promotion eligibility for {identity[:12]}: {decision['status']}; "
                     f"{', '.join(decision['reasons']) or 'saved promotion policy passed'}.")
    lines.append('')
    for identity, candidate in sorted(review['candidates'].items()):
        for cell in candidate['weak_matchups_colors'][:2]:
            lines.append(f"\nWeak cell for {identity[:12]}: {cell['opponent']} as {cell['color']}, "
                         f"score {cell['numerator']}/{cell['denominator']}; distinct evidence {cell['distinct_evidence']}.")
        for timing in candidate['timing']:
            clock = timing['latest_jobs']['candidate']['turn_ms']
            lines.append(f"\nCandidate turn time: p95 {clock['p95']} ms, max {clock['max']} ms "
                         f"({clock['samples']} observations; {clock['missing']} missing).")
    lines.extend(['', 'Representative failures (categories and clock pressure are hypotheses):', ''])
    for failure in review['failures']:
        plies = [p['ply'] for p in failure['inspection']['positions']]
        lines.append(f"- {failure['candidate'][:12]} vs {failure['opponent']['logical_id']}, "
            f"color {failure['color']}, plies {plies}, low clock {failure['time_pressure']['low_remaining_clock']}; "
            f"trace `{failure['source']['trace_identity']}`.")
    for resource in review['resources']:
        if 'optimizer_segments' in resource:
            seconds = sum(s.get('wall_seconds', 0) for s in resource['optimizer_segments'])
            attempts = resource['progress']['attempts']
            lines.extend(['', f"Resources: {attempts} attempts / {seconds:.3f} recorded wall seconds; "
                f"throughput {attempts / seconds if seconds else None} attempts/second. "
                'Worker/runtime/contention settings are retained in the JSON companion.'])
    if not any('optimizer_segments' in r for r in review['resources']):
        lines.extend(['', 'Batch throughput: unavailable without optimizer wall-time evidence. '
                      'Available execution segments and runtime settings are retained in the JSON companion.'])
    lines.extend(['', 'Separate deeper-analysis budget: none used by this review.', '',
        f"Next bounded experiment: {review['next_bounded_experiment']['action']}; "
        f"at most {review['next_bounded_experiment']['max_failures']} failures and "
        f"{review['next_bounded_experiment']['max_positions']} positions per game; "
        f"proposed new-game cap {review['next_bounded_experiment']['proposed_max_new_games']}, "
        'analysis cap 361 transitions / 30 seconds per position. Freeze the experiment policy before dispatch. '
        'No new games scheduled.', '',
        review['limitations'], '', f"Source {review['source'].get('kind', 'stage')}: `{review['source']['stage_identity']}`; "
        f"evidence: `{review['source']['raw_identity']}`. {review['source']['attribution']}", ''])
    return '\n'.join(lines)


def main() -> None:
    import argparse
    from offline.experiments import save_new_json
    from offline.inspection import load_trace, checked_fixture
    from offline.regressions import analyze_tactic, export_regression, append_fixture, verify_regression
    from offline.screening import load_stage
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    review = sub.add_parser('batch')
    source = review.add_mutually_exclusive_group(required=True)
    source.add_argument('--run', type=Path)
    source.add_argument('--stage', type=Path)
    review.add_argument('--raw', type=Path)
    review.add_argument('--checks', type=Path)
    review.add_argument('--champion-store', type=Path)
    review.add_argument('--transaction')
    review.add_argument('--engine-change', type=Path)
    review.add_argument('--max-failures', type=int, default=6)
    review.add_argument('--max-positions', type=int, default=3)
    review.add_argument('--output', type=Path, required=True)
    analyze = sub.add_parser('analyze')
    analyze.add_argument('--trace', type=Path, required=True)
    analyze.add_argument('--color', type=int, choices=(0, 1), required=True)
    analyze.add_argument('--ply', type=int, required=True)
    analyze.add_argument('--kind', choices=('immediate-win', 'immediate-defense'), required=True)
    analyze.add_argument('--max-transitions', type=int, required=True)
    analyze.add_argument('--max-seconds', type=float, required=True)
    analyze.add_argument('--output', type=Path, required=True)
    analyze.add_argument('--fixtures', type=Path)
    rule = sub.add_parser('rule')
    rule.add_argument('--trace', type=Path, required=True)
    rule.add_argument('--color', type=int, choices=(0, 1), required=True)
    rule.add_argument('--ply', type=int, required=True)
    rule.add_argument('--outcome', choices=('ongoing', 'black_win', 'white_win', 'draw'), required=True)
    rule.add_argument('--reason')
    rule.add_argument('--fixtures', type=Path, required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('fixture', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'batch':
            if bool(args.stage) != bool(args.raw):
                raise ValueError('--stage requires --raw; --run reads authoritative checkpoints.')
            settings = {'max_failures': args.max_failures, 'max_positions': args.max_positions}
            result = (review_saved_run(args.run, **settings) if args.run else
                      review_batch(load_stage(args.stage), load_trace(args.raw), **settings))
            if args.checks:
                result = include_promotion(result, args.checks)
            if bool(args.champion_store) != bool(args.transaction):
                raise ValueError('Champion status requires both --champion-store and --transaction.')
            if args.champion_store:
                result = include_champion_decision(result, args.champion_store, args.transaction)
            if args.engine_change:
                result = record_engine_change(result, load_trace(args.engine_change))
        elif args.command == 'analyze':
            trace = load_trace(args.trace)
            record = inspect_loss(trace, color=args.color, plies=[args.ply])['positions'][0]
            result = analyze_tactic(record, kind=args.kind, max_transitions=args.max_transitions,
                                    max_seconds=args.max_seconds)
            if args.fixtures:
                result['fixture'] = str(export_regression(args.fixtures, trace, ply=args.ply,
                                                         color=args.color, analysis=result))
        elif args.command == 'rule':
            fixture = checked_fixture(load_trace(args.trace), ply=args.ply, color=args.color,
                                      expected_outcome=args.outcome, expected_reason=args.reason)
            print(append_fixture(args.fixtures, fixture))
            return
        else:
            verify_regression(load_trace(args.fixture))
            print('verified')
            return
        args.output.parent.mkdir(parents=True, exist_ok=True)
        save_new_json(args.output, result)
        if args.command == 'batch':
            with args.output.with_suffix('.md').open('x', encoding='utf-8') as stream:
                stream.write(render_review(result))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        parser.exit(2, f'error: {error}\n')


if __name__ == '__main__':
    main()
