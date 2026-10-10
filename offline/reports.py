# AI-written by OpenAI Codex, for issue #33.
"""Descriptive matchup reports from saved, replay-validated experiment evidence."""
from math import ceil, isfinite
from typing import Any

from offline.experiments import ExperimentPlan
from offline.matches import game_score, score_experiment

FORMAT = 'omok-matchup-report-v1'
CATEGORIES = ('completed', 'failed', 'capped', 'infrastructure_failed', 'pending')


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {'numerator': numerator, 'denominator': denominator,
            'value': numerator / denominator if denominator else None}


def summary(slots: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {key: sum(s['category'] == key for s in slots) for key in CATEGORIES}
    counts['planned'] = len(slots)
    outcomes = {key: sum(s['recognized_result'] == value for s in slots) for key, value in
                (('wins', 'candidate_win'), ('losses', 'opponent_win'), ('draws', 'draw'))}
    outcomes['win_rate'] = rate(outcomes['wins'], sum(outcomes.values()))
    failures: dict[str, dict[str, int]] = {'candidate': {}, 'opponent': {}}
    for slot in slots:
        execution = slot.get('execution')
        failure = execution.get('failure') if execution else None
        if failure and failure.get('color') in (0, 1):
            role = 'candidate' if failure['color'] == slot['candidate_color'] else 'opponent'
            for reason in failure.get('violations', []):
                failures[role][reason] = failures[role].get(reason, 0) + 1
    return {'counts': counts, 'recognized': outcomes, 'failure_violations': failures,
            'failure_rate': rate(counts['failed'] + counts['infrastructure_failed'], len(slots) - counts['pending']),
            'completion_rate': rate(counts['completed'], len(slots)),
            'candidate_crashes': sum('candidate' in s['crashes'] for s in slots),
            'opponent_crashes': sum('opponent' in s['crashes'] for s in slots)}


def color_summary(slots: list[dict[str, Any]]) -> dict[str, Any]:
    return summary(slots) | {'by_color': {name: summary([s for s in slots if s['candidate_color'] == color])
                            for color, name in enumerate(('black', 'white'))}}


def attempt_history(plan: ExperimentPlan, raw: dict[str, Any]) -> tuple[list[dict[str, Any]], int, bool]:
    if 'attempts' not in raw:
        return [dict(game_id=r['game_id'], state='committed', result=r) for r in raw['results']], 0, False
    jobs = {j['game_id']: j for j in plan.data['jobs']}
    seen: dict[str, dict[str, Any]] = {}
    latest = {}
    duplicates = 0
    for attempt in raw['attempts']:
        key = attempt['attempt_id']
        if key in seen:
            if seen[key] != attempt:
                raise ValueError('Conflicting duplicate attempt delivery.')
            duplicates += 1
            continue
        if not isinstance(key, str) or not key or attempt['game_id'] not in jobs or attempt['state'] not in (
                'committed', 'interrupted', 'running'):
            raise ValueError('Invalid attempt identity or state.')
        seen[key] = attempt
        if attempt['state'] == 'committed':
            record = attempt['result']
            job = jobs[attempt['game_id']]
            if any(record.get(k) != job[k] or type(record.get(k)) is not type(job[k])
                   for k in ('game_id', 'match_id', 'slot', 'candidate_color')) or any(
                    record.get(k) != attempt[k] for k in ('attempt_id', 'segment')):
                raise ValueError('Attempt/result assignment mismatch.')
            latest[attempt['game_id']] = record
    if latest != {r['game_id']: r for r in raw['results']}:
        raise ValueError('Latest committed attempts disagree with job results.')
    return list(seen.values()), duplicates, True


def attempt_summary(attempts: list[dict[str, Any]], scores: dict[int, dict[str, Any]]) -> dict[str, Any]:
    slots = [scores[id(a['result'])]
             for a in attempts if a['state'] == 'committed']
    return {'total': len(attempts), 'interrupted': sum(a['state'] == 'interrupted' for a in attempts),
            'running': sum(a['state'] == 'running' for a in attempts), 'committed': color_summary(slots)}


def distribution(values: list[Any]) -> dict[str, Any]:
    numbers = sorted(v for v in values if type(v) in (int, float) and isfinite(v))
    return {'samples': len(numbers), 'missing': len(values) - len(numbers),
            'mean': sum(numbers) / len(numbers) if numbers else None,
            'min': numbers[0] if numbers else None, 'max': numbers[-1] if numbers else None,
            **{name: numbers[max(0, ceil(len(numbers) * fraction) - 1)] if numbers else None
               for name, fraction in (('p50', .5), ('p95', .95), ('p99', .99))}}


def numeric_diagnostics(value: Any, prefix: str = '') -> dict[str, Any]:
    fields = {}
    if isinstance(value, dict):
        for key, child in value.items():
            name = prefix + str(key)
            if isinstance(child, dict):
                fields.update(numeric_diagnostics(child, name + '.'))
            elif type(child) in (int, float) and isfinite(child):
                fields[name] = child
    return fields


def metrics(records: list[dict[str, Any]], scores: dict[int, dict[str, Any]]) -> dict[str, Any]:
    traces = []
    for record in records:
        slot = scores[id(record)]
        if record.get('trace') is not None and 'validation_error' not in slot:
            traces.append((record['trace'], slot['candidate_color']))
    result: dict[str, Any] = {'records': len(records), 'validated_traces': len(traces),
                             'unavailable_traces': len(records) - len(traces),
        'game_length': distribution([len(t['moves']) for t, _ in traces])}
    for role in ('candidate', 'opponent'):
        events: list[dict[str, Any]] = []
        clocks = []
        for trace, color in traces:
            color = color if role == 'candidate' else 1 - color
            events.extend(e for e in trace.get('events', []) if e['type'] == 'returned' and e['color'] == color)
            clocks.append(trace.get('remaining_ms', [None, None])[color])
        diagnostics = [numeric_diagnostics(e.get('search')) for e in events]
        keys = {'nodes', 'completed_depth', 'attempted_depth', 'evaluation_calls'}
        keys.update(k for fields in diagnostics for k in fields)
        result[role] = {'turn_ms': distribution([e.get('elapsed_ms') for e in events]),
            'player_call_ms': distribution([e.get('call_elapsed_ms') for e in events]),
            'overhead_ms': distribution([e.get('overhead_ms') for e in events]),
            'remaining_ms': distribution(clocks),
            'diagnostics': {k: distribution([d.get(k) for d in diagnostics]) for k in sorted(keys)}}
    return result


def report_experiment(plan: ExperimentPlan, raw: dict[str, Any]) -> dict[str, Any]:
    plan = ExperimentPlan.from_record(plan.record())
    scored = score_experiment(plan, raw)
    attempts, duplicates, history_available = attempt_history(plan, raw)
    jobs = {j['game_id']: j for j in plan.data['jobs']}
    slots = [s for match in scored['matches'] for s in match['slots']]
    by_game = {s['game_id']: s for s in slots}
    latest = {r['game_id']: r for r in raw['results']}
    scores = {id(r): by_game[r['game_id']] for r in raw['results']}
    committed = [a['result'] for a in attempts if a['state'] == 'committed']
    for record in committed:
        # Reuse the validated latest score even after JSON has materialized the
        # same result separately in the attempt history. Replay each prior attempt once.
        scores[id(record)] = (by_game[record['game_id']] if latest.get(record['game_id']) == record
                              else game_score(jobs[record['game_id']], record, plan.record()))
    clean = [s for s in slots if s['category'] == 'completed']
    opponents = []
    for match in scored['matches']:
        job = next(j for j in plan.data['jobs'] if j['match_id'] == match['match_id'])
        opponent = job['opponent']
        opponents.append({'identity': match['opponent_identity'], 'logical_id': opponent['logical_id'],
            'family': opponent['family'], 'origin': opponent['origin'], 'pool': job['pool'],
            'jobs': color_summary(match['slots']),
            'all_attempts': attempt_summary([a for a in attempts if jobs[a['game_id']]['match_id'] == match['match_id']],
                                           scores),
            'clean_games': color_summary([s for s in match['slots'] if s['category'] == 'completed'])})
        records = [r for r in raw['results'] if r['match_id'] == match['match_id']]
        opponents[-1]['metrics'] = metrics(records, scores)
        opponents[-1]['metrics_by_color'] = {name: metrics(
            [r for r in records if r['candidate_color'] == color], scores)
            for color, name in enumerate(('black', 'white'))}
    coverage: dict[str, Any] = {'families': {}, 'origins': {}, 'pools': {},
                               'duplicate_evidence_groups': {}, 'seed_limitations': {}}
    for job in jobs.values():
        for dimension, value in (('families', job['opponent']['family']),
                                 ('origins', job['opponent']['origin']), ('pools', job['pool'])):
            group = coverage[dimension].setdefault(value, {'opponent_versions': [], 'planned_jobs': 0,
                                                          'observed_jobs': 0})
            if job['opponent']['identity'] not in group['opponent_versions']:
                group['opponent_versions'].append(job['opponent']['identity'])
            group['planned_jobs'] += 1
            group['observed_jobs'] += job['game_id'] in latest
        duplicate = job.get('duplicate_evidence_group')
        if duplicate:
            coverage['duplicate_evidence_groups'].setdefault(duplicate, []).append(job['game_id'])
        if job.get('seed_limitations'):
            coverage['seed_limitations'][job['game_id']] = job['seed_limitations']
    coverage['duplicate_evidence_groups'] = {k: v for k, v in coverage['duplicate_evidence_groups'].items() if len(v) > 1}
    rates = [o['jobs']['recognized']['win_rate']['value'] for o in opponents
             if o['jobs']['recognized']['win_rate']['value'] is not None]
    clean_rates = [o['clean_games']['recognized']['win_rate']['value'] for o in opponents
                  if o['clean_games']['recognized']['win_rate']['value'] is not None]
    averages = {'micro': summary(slots)['recognized']['win_rate'],
        'equal_opponent_macro': {'numerator': sum(rates), 'denominator': len(rates),
            'value': sum(rates) / len(rates) if rates else None, 'unavailable_opponents': len(opponents) - len(rates)},
        'clean_game_micro': summary(clean)['recognized']['win_rate'],
        'clean_game_equal_opponent_macro': {'numerator': sum(clean_rates), 'denominator': len(clean_rates),
            'value': sum(clean_rates) / len(clean_rates) if clean_rates else None,
            'unavailable_opponents': len(opponents) - len(clean_rates)}}
    segments = raw.get('segments', [])
    segment_ids = {s['id'] for s in segments}
    if len(segment_ids) != len(segments):
        raise ValueError('Duplicate execution segment.')
    execution_segments = [{'evidence': s, 'metrics': metrics(
        [r for r in committed if r.get('segment') == s['id']], scores)} for s in segments]
    unassigned = [r for r in committed if r.get('segment') not in segment_ids]
    return {'format': FORMAT, 'manifest_identity': plan.identity, 'mode': scored['mode'],
            'candidate': plan.data['candidate'], 'ordinary_strength_evidence': scored['mode'] != 'fixture',
            'jobs': color_summary(slots), 'clean_games': color_summary(clean),
            'all_attempts': attempt_summary(attempts, scores) | {
                'history_available': history_available, 'duplicate_deliveries': duplicates},
            'metrics': {'latest_jobs': metrics(raw['results'], scores),
                        'all_committed_attempts': metrics(committed, scores)},
            'averages': averages, 'coverage': coverage,
            'weak_matchups': [{'identity': o['identity'], 'logical_id': o['logical_id'],
                'win_rate': o['jobs']['recognized']['win_rate'], 'by_color': o['jobs']['by_color']}
                for o in sorted(opponents, key=lambda o: (
                    o['jobs']['recognized']['win_rate']['value'] is None,
                    o['jobs']['recognized']['win_rate']['value'] or 0, o['identity']))],
            'execution_segments': execution_segments,
            'unassigned_segment_metrics': metrics(unassigned, scores),
            'rating': {'status': 'deferred', 'reason': 'No calibrated independent opponent pool; descriptive outcomes suffice. '
                       'Caps and unresolved matches receive no rating outcomes; no class rank is inferred.'},
            'uncertainty': {'independent_trials_assumed': False, 'intervals': None,
                'reason': 'Small, paired, repeated and related-family samples may be dependent. '
                          'Rates are descriptive, not confidence intervals or promotion thresholds.'},
            'opponents': opponents, 'matches': scored['matches'], 'scoring_policy': scored['scoring_policy']}
