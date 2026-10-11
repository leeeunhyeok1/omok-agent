# AI-written by OpenAI Codex, for issue #42.
"""Predeclared validation and official-clock eligibility; no champion transaction."""
from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from typing import Any

from offline.batches import Checkpoint, atomic_json, owner, verify_versions
from offline.confirmation import assess_record, load as load_confirmation, paired_effects, execution_signature
from offline.experiments import ExperimentPlan, run_experiment, save_new_json
from offline.league import assess_round
from offline.registry import Entry, PoolSnapshot, canonical, digest
from offline.screening import GATES, ScreeningPolicy, member_evidence, assess_stage
from omok.simulator import Position

FORMAT = 'omok-promotion-eligibility-v1'
CADENCE = 'every selected finalist before eligibility; incumbent on each check; fixed declared coverage'
OFFICIAL_SAFETY_CAP = 10000


@dataclass(frozen=True)
class PromotionPolicy:
    definition: str

    @staticmethod
    def defaults() -> dict[str, Any]:
        return {'version': FORMAT, 'cadence': CADENCE, 'validation': {}, 'official_opponents': [],
            'validation_ms': 5000, 'validation_cap': 1000, 'seed': 42,
            'min_validation_pairs': 2, 'min_training_families': 2, 'min_incumbent_games': 16,
            'min_incumbent_score': .55, 'min_league_gain': .05,
            'max_validation_regression': .05, 'max_family_regression': .05,
            'max_matchup_regression': .05, 'max_historical_regression': .05,
            'max_color_regression': .05, 'min_official_headroom_ms': 2,
            'max_headroom_regression_ms': 1000, 'infrastructure_retries': 1}

    def __post_init__(self) -> None:
        p = json.loads(self.definition)
        if set(p) != set(self.defaults()) or p['version'] != FORMAT or p['cadence'] != CADENCE:
            raise ValueError('Unsupported promotion policy/cadence.')
        if not p['validation'] or any(type(n) is not int or n < 2 or n % 2 for n in p['validation'].values()):
            raise ValueError('Declare balanced validation coverage.')
        if not p['official_opponents'] or len(set(p['official_opponents'])) != len(p['official_opponents']):
            raise ValueError('Declare distinct official opponents.')
        for key in ('min_validation_pairs', 'min_training_families', 'min_incumbent_games'):
            if type(p[key]) is not int or p[key] < 1:
                raise ValueError('Invalid coverage minimum: ' + key)
        if p['min_incumbent_games'] < 16 or p['min_training_families'] < 2:
            raise ValueError('Single-match or single-family promotion is forbidden.')
        for key in ('min_incumbent_score', 'min_league_gain', 'max_validation_regression',
                    'max_family_regression', 'max_matchup_regression', 'max_historical_regression', 'max_color_regression'):
            if type(p[key]) not in (int, float) or not isfinite(p[key]) or not 0 <= p[key] <= 1:
                raise ValueError('Invalid promotion margin: ' + key)
        for key in ('min_official_headroom_ms', 'max_headroom_regression_ms'):
            if type(p[key]) not in (int, float) or not isfinite(p[key]) or p[key] < 0:
                raise ValueError('Invalid timing margin.')
        if (type(p['seed']) is not int or type(p['validation_cap']) is not int or p['validation_cap'] < 0
                or type(p['infrastructure_retries']) is not int or not 0 <= p['infrastructure_retries'] <= 3
                or type(p['validation_ms']) not in (int, float) or not isfinite(p['validation_ms'])
                or not 0 < p['validation_ms'] < 60000):
            raise ValueError('Invalid validation execution policy.')
        object.__setattr__(self, 'definition', canonical(p))

    @classmethod
    def create(cls, **settings: Any) -> 'PromotionPolicy':
        return cls(canonical(cls.defaults() | settings))

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self.definition)

    def save(self, path: Path) -> None:
        save_new_json(path, {'identity': digest(self.data), 'policy': self.data})

    @classmethod
    def load(cls, path: Path) -> 'PromotionPolicy':
        record = json.loads(path.read_text(encoding='utf-8'))
        result = cls(canonical(record['policy']))
        if record['identity'] != digest(result.data):
            raise ValueError('Promotion policy identity mismatch.')
        return result


def check_stage(p: dict[str, Any], entries: list[Entry], incumbent: str, snapshot: PoolSnapshot,
                gates: dict[str, list[dict[str, Any]]], *, official: bool,
                fixture: Position | None = None, openings: list[list[list[int]]] | None = None) -> dict[str, Any]:
    requested = {}
    for name in p['official_opponents'] if official else p['validation']:
        found = [(pool, r) for pool, records in snapshot.record()['pools'].items()
                 for r in records if r['logical_id'] == name]
        if not found or found[0][0] == 'holdout' or (not official and found[0][0] != 'validation'):
            raise ValueError('Checks require validation opponents; official checks also allow training, never holdout.')
        requested[name] = found[0][1]
    counts = {n: 8 if official else p['validation'][n] for n in requested}
    # Reuse descriptive game-point/attempt accounting, never direct training selection.
    metrics = ScreeningPolicy.create(opponents=counts, opponent_weights={n: 1 for n in counts},
        family_weights={r['family']: 1 for r in requested.values()}, min_evidence_per_color=1,
        infrastructure_retries=p['infrastructure_retries'], total_ms=p['validation_ms'],
        move_cap=OFFICIAL_SAFETY_CAP if official else p['validation_cap'], seed=p['seed']).data
    members = []
    for entry in entries:
        snapshot.validate_optimizer_candidate(entry)
        plans = []
        for name, opponent in requested.items():
            if opponent['availability'] != 'ready':
                continue
            pool = next(pool for pool, records in snapshot.record()['pools'].items() if opponent in records)
            plan = ExperimentPlan.resolve(entry, snapshot, purpose=pool,
                mode='official' if official else 'fixture' if fixture is not None else 'screening',
                opponents=[name], games_per_opponent=counts[name], total_ms=60000 if official else p['validation_ms'],
                move_cap=OFFICIAL_SAFETY_CAP if official else p['validation_cap'], seed=p['seed'], diagnostics=True,
                fixture=None if official else fixture, openings=None if official else openings)
            plans.append(plan.record())
        members.append({'entry': entry.record(), 'gates': gates.get(entry.identity, []), 'plans': plans})
    return {'policy': {'policy': metrics}, 'pool_snapshot': snapshot.record(), 'requested_opponents': requested,
            'incumbent': incumbent, 'members': members}


def prepare(policy_path: Path, incumbent: Entry, snapshot: PoolSnapshot, *, output: Path,
            prior_exposures: list[dict[str, Any]], confirmation: Path | None = None,
            confirmation_raw: dict[str, dict[str, Any]] | None = None,
            gates: dict[str, list[dict[str, Any]]] | None = None,
            fixture: Position | None = None, openings: list[list[list[int]]] | None = None,
            previous_checks: list[Path] | None = None) -> dict[str, Any]:
    policy = PromotionPolicy.load(policy_path)
    snapshot.validate_optimizer_candidate(incumbent)
    source = load_confirmation(confirmation) if confirmation is not None else None
    raw = confirmation_raw or {}
    candidates = []
    retained_gates = dict(gates or {})
    if source is not None:
        decision = assess_record(source, raw)
        if source['stage']['incumbent'] != incumbent.identity or source['stage']['pool_snapshot'] != snapshot.record():
            raise ValueError('Retain the confirmed incumbent and full pool snapshot.')
        for m in source['stage']['members']:
            identity = m['entry']['identity']
            retained_gates[identity] = m['gates']
            if identity in decision['advanced']:
                candidates.append(Entry.from_record(m['entry']))
    elif raw:
        raise ValueError('Confirmation evidence requires its declaration.')
    entries = [incumbent] + sorted(candidates, key=lambda e: e.identity)
    prior = []
    for path in previous_checks or []:
        earlier = load(path)
        evidence = json.loads((path / 'eligibility-results.json').read_text(encoding='utf-8'))
        if evidence['identity'] != digest(evidence['data']) or evidence['data']['check_identity'] != digest(earlier):
            raise ValueError('Prior check evidence identity mismatch.')
        assess_record_checks(earlier, evidence['data']['raw'])
        prior.append({'record': earlier, 'raw': evidence['data']['raw']})
    record = {'format': FORMAT, 'policy': policy.data, 'confirmation': source, 'confirmation_raw': raw,
        'prior_exposures': prior_exposures, 'previous_checks': prior,
        'validation': check_stage(policy.data, entries, incumbent.identity, snapshot, retained_gates,
                                  official=False, fixture=fixture, openings=openings),
        'official': check_stage(policy.data, entries, incumbent.identity, snapshot, retained_gates, official=True)}
    validate(record)
    output.mkdir(parents=True, exist_ok=False)
    save_new_json(output / 'eligibility.json', {'identity': digest(record), 'checks': record})
    return record


def validate(record: dict[str, Any]) -> None:
    p = PromotionPolicy(canonical(record['policy'])).data
    if record['format'] != FORMAT or not isinstance(record['prior_exposures'], list):
        raise ValueError('Invalid checks/exposure history.')
    if any(not e.get('source') or not e.get('details') for e in record['prior_exposures']):
        raise ValueError('Prior exposure needs a source and honest details (unknown counts allowed).')
    validation = record['validation']
    snapshot = PoolSnapshot.from_record(validation['pool_snapshot'])
    entries = [Entry.from_record(m['entry']) for m in validation['members']]
    identities = {e.identity for e in entries}
    if len(identities) != len(entries) or validation['incumbent'] not in identities:
        raise ValueError('Invalid check cohort.')
    source = record['confirmation']
    if source is None:
        if identities != {validation['incumbent']} or record['confirmation_raw']:
            raise ValueError('Finalists require fresh training confirmation.')
    else:
        confirmed = assess_record(source, record['confirmation_raw'])
        if (identities != set(confirmed['advanced']) | {validation['incumbent']}
                or source['stage']['incumbent'] != validation['incumbent']
                or source['stage']['pool_snapshot'] != snapshot.record()):
            raise ValueError('Check cohort differs from confirmed finalists.')
        old = {m['entry']['identity']: m for m in source['stage']['members']}
        if any(m['gates'] != old[m['entry']['identity']]['gates'] for m in validation['members']):
            raise ValueError('Cannot rewrite confirmed candidate gates.')
    gates = {m['entry']['identity']: m['gates'] for m in validation['members']}
    for member in validation['members']:
        if (len({g['check'] for g in member['gates']}) != len(member['gates']) or any(
                g.get('check') not in GATES or g.get('status') not in ('pass', 'fail', 'inconclusive')
                or type(g.get('samples')) is not int or g['samples'] < 1 or not g.get('evidence') for g in member['gates'])):
            raise ValueError('Invalid candidate gates.')
    first = next((r for m in validation['members'] for r in m['plans']), None)
    fixture = None
    openings = None
    if first:
        settings = first['settings']
        if settings['mode'] == 'fixture':
            start = settings['openings'][0]
            fixture = Position(start['board'], start['side_to_move'])
        else:
            openings = [s['moves'] for s in settings['openings']]
    for name in ('validation', 'official'):
        rebuilt = check_stage(p, entries, validation['incumbent'], snapshot, gates,
                              official=name == 'official', fixture=fixture, openings=openings)
        saved = record[name]
        # Observed planning conditions are provenance, never mutable job settings.
        for a, b in zip(rebuilt['members'], saved['members']):
            for left, right in zip(a['plans'], b['plans']):
                ExperimentPlan.from_record(right)
                left['conditions'] = right['conditions']
                left['identity'] = digest({k: v for k, v in left.items() if k != 'identity'})
        if rebuilt != saved:
            raise ValueError('Checks violate saved coverage, roles or official-clock policy.')
    for previous in record['previous_checks']:
        assess_record_checks(previous['record'], previous['raw'])


def load(output: Path) -> dict[str, Any]:
    envelope = json.loads((output / 'eligibility.json').read_text(encoding='utf-8'))
    record = envelope['checks']
    if envelope['identity'] != digest(record):
        raise ValueError('Eligibility identity mismatch.')
    validate(record)
    return record


def check_conditions(value: dict[str, Any]) -> None:
    if (set(value) != {'power', 'load', 'other_experiments_stopped'}
            or not isinstance(value['power'], str) or not value['power'].strip()
            or not isinstance(value['load'], str) or not value['load'].strip()
            or value['other_experiments_stopped'] is not True):
        raise ValueError('Record actual power/load and stop other experiments before official execution.')


def clock_evidence(member: dict[str, Any], evidence: dict[str, Any], raw: dict[str, dict[str, Any]],
                   p: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    headrooms = []
    conditions = []
    for saved, report in zip(member['plans'], evidence['reports']):
        data = raw.get(saved['identity'], {'results': []})
        segments = {s['id']: s['conditions'] for s in data.get('segments', [])}
        for result in data['results']:
            segment = segments.get(result.get('segment'))
            try:
                if segment is None or segment['workers'] != 1:
                    raise ValueError('one worker required')
                declared = json.loads(segment['contention'])
                check_conditions(declared)
            except (KeyError, ValueError, TypeError):
                reasons.append('unverified_official_conditions')
            else:
                conditions.append(segment)
        counts = report['jobs']['counts']
        if counts['completed'] != counts['planned']:
            reasons.append('official_completion_required')
        for result in data['results']:
            trace = result.get('trace')
            if trace:
                remaining = trace['remaining_ms'][result['candidate_color']]
                if remaining is not None:
                    headrooms.append(remaining)
    minimum = min(headrooms) if headrooms else None
    if minimum is None:
        reasons.append('missing_clock_evidence')
    elif minimum < p['min_official_headroom_ms']:
        reasons.append('insufficient_clock_headroom')
    return {'minimum_remaining_ms': minimum, 'samples': len(headrooms),
            'conditions': conditions, 'reasons': sorted(set(reasons))}


def regressions(member: dict[str, Any], baseline: dict[str, Any], p: dict[str, Any],
                *, historical: set[str] | None = None, weights: dict[str, Any] | None = None) -> list[str]:
    reasons = []
    for name, cell in member['by_opponent'].items():
        old = baseline['by_opponent'].get(name)
        if old is None or cell['value'] is None or old['value'] is None:
            continue
        margin = p['max_historical_regression'] if name in (historical or set()) else p['max_matchup_regression']
        if cell['value'] < old['value'] - margin:
            reasons.append('historical_regression' if name in (historical or set()) else 'worst_matchup_regression')
        for color in ('black', 'white'):
            a, b = cell['by_color'][color]['value'], old['by_color'][color]['value']
            if a is not None and b is not None and a < b - p['max_color_regression']:
                reasons.append('per_color_regression')
    families = {o['family'] for o in member['by_opponent'].values()}
    for family in families:
        names = [n for n, o in member['by_opponent'].items() if o['family'] == family]
        if all(member['by_opponent'][n]['value'] is not None and baseline['by_opponent'].get(n, {}).get('value') is not None for n in names):
            shares = weights or {n: 1 for n in names}
            a = sum(member['by_opponent'][n]['value'] * shares[n] for n in names) / sum(shares[n] for n in names)
            b = sum(baseline['by_opponent'][n]['value'] * shares[n] for n in names) / sum(shares[n] for n in names)
            if a < b - p['max_family_regression']:
                reasons.append('family_regression')
    return sorted(set(reasons))


def assess(output: Path, raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return assess_record_checks(load(output), raw)


def training_vetoes(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """All retained training attempts count, including unsuccessful earlier rounds."""
    vetoes: dict[str, list[dict[str, Any]]] = {}

    def retain(stage: dict[str, Any], raw: dict[str, dict[str, Any]]) -> None:
        report = assess_stage(stage, raw)
        for identity, evidence in report['candidates'].items():
            vetoes.setdefault(identity, []).extend(evidence['vetoes'])

    def history(context: dict[str, Any]) -> None:
        for rung in context['prior_rungs']:
            retain(rung['stage'], rung['raw'])
        for previous in context['prior_rounds']:
            retain(previous['stage']['screening'], previous['raw'])
            history(previous['stage'])

    retain(source['selection'], source['selection_raw'])
    if source['selection_context'] is not None:
        history(source['selection_context'])
    return {identity: list({digest(v): v for v in values}.values()) for identity, values in vetoes.items()}


def assess_record_checks(record: dict[str, Any], raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    validate(record)
    p = record['policy']
    stage = record['validation']
    incumbent = stage['incumbent']
    expected = {r['identity'] for s in ('validation', 'official') for m in record[s]['members'] for r in m['plans']}
    if set(raw) - expected:
        raise ValueError('Foreign validation/official evidence.')
    tables = {s: {m['entry']['identity']: member_evidence(m, record[s], raw)
                  for m in record[s]['members']} for s in ('validation', 'official')}
    for name, table in tables.items():
        for evidence in table.values():
            evidence['game_point_score'] = evidence.pop('fitness')
            evidence['score_scope'] = name + ' check only; excluded from direct training fitness and mutation selection'
    base_member = next(m for m in stage['members'] if m['entry']['identity'] == incumbent)
    base_official_member = next(m for m in record['official']['members'] if m['entry']['identity'] == incumbent)
    base_clock = clock_evidence(base_official_member, tables['official'][incumbent], raw, p)
    source = record['confirmation']
    confirmed = assess_record(source, record['confirmation_raw']) if source is not None else None
    context = source['selection_context'] if source is not None else None
    league = assess_round(context, source['selection_raw']) if context is not None else None
    retained_vetoes = training_vetoes(source) if source is not None else {}
    candidates = {}
    for member, official_member in zip(stage['members'], record['official']['members']):
        identity = member['entry']['identity']
        validation = tables['validation'][identity]
        official = tables['official'][identity]
        clocks = clock_evidence(official_member, official, raw, p)
        reasons = ['validation_' + r for r in validation['reasons']] + official['reasons'] + clocks['reasons']
        vetoes = validation['vetoes'] + official['vetoes'] + retained_vetoes.get(identity, [])
        pair_policy = {'screening': stage['policy']['policy'], 'min_pairs_per_opponent': p['min_validation_pairs'],
                       'min_families': 1}
        paired = paired_effects(member, base_member, validation, tables['validation'][incumbent], raw, pair_policy)
        reasons.extend(paired['pairing_reasons'])
        rejected = []
        if identity != incumbent:
            base_validation = tables['validation'][incumbent]
            if (base_validation['reasons'] or base_validation['vetoes'] or tables['official'][incumbent]['reasons']
                    or tables['official'][incumbent]['vetoes'] or base_clock['reasons']):
                reasons.append('incumbent_check_evidence_incomplete')
            for saved, base_saved in zip(official_member['plans'], base_official_member['plans']):
                for job, base_job in zip(saved['jobs'], base_saved['jobs']):
                    empty: dict[str, Any] = {'results': []}
                    if execution_signature(raw.get(saved['identity'], empty), job['game_id']) != execution_signature(
                            raw.get(base_saved['identity'], empty), base_job['game_id']):
                        reasons.append('incomparable_official_conditions')
            if paired['effect'] is not None and paired['effect'] < -p['max_validation_regression']:
                rejected.append('validation_regression')
            rejected.extend(regressions(validation, base_validation, p))
            if (clocks['minimum_remaining_ms'] is not None and base_clock['minimum_remaining_ms'] is not None
                    and clocks['minimum_remaining_ms'] < base_clock['minimum_remaining_ms'] - p['max_headroom_regression_ms']):
                rejected.append('timing_policy_regression')
            if confirmed is None or confirmed['candidates'][identity]['status'] != 'advance':
                reasons.append('fresh_confirmation_required')
            else:
                vetoes.extend(confirmed['candidates'][identity]['vetoes'])
                if confirmed['candidates'][identity]['sensitivity_range'][0] < p['min_league_gain']:
                    rejected.append('training_gain_below_margin')
                if not confirmed['ordinary_strength_evidence']:
                    reasons.append('artificial_training_evidence')
            if league is None or context is None:
                reasons.append('broader_league_history_required')
            else:
                training = league['candidates'][identity]
                vetoes.extend(training['vetoes'])
                if training['status'] != 'advance':
                    reasons.append('broader_league_not_eligible')
                if training['gain'] is not None and training['gain'] < p['min_league_gain']:
                    rejected.append('league_gain_below_margin')
                histories = {b['entry']['logical_id'] for b in context['history']['champions']}
                rejected.extend(regressions(training, league['candidates'][incumbent], p, historical=histories,
                    weights=context['screening']['policy']['policy']['opponent_weights']))
                if confirmed is not None:
                    rejected.extend('confirmation_' + reason for reason in regressions(
                        confirmed['candidates'][identity], confirmed['candidates'][incumbent], p,
                        historical=histories, weights=source['stage']['policy']['policy']['opponent_weights']))
                required = histories | {member['entry']['logical_id'] for member in context['screening']['members']
                                         if member['entry']['identity'] == incumbent}
                distinct = {o['family'] for n, o in training['by_opponent'].items() if n not in required}
                if len(distinct) < p['min_training_families']:
                    reasons.append('insufficient_diverse_training_families')
                if not histories <= set(training['by_opponent']) or league['historical_gaps']:
                    reasons.append('historical_coverage_required')
                incumbent_name = base_member['entry']['logical_id']
                head = training['by_opponent'].get(incumbent_name)
                if head is None or sum(c['denominator'] for c in head['by_color'].values()) < p['min_incumbent_games']:
                    reasons.append('insufficient_incumbent_comparison')
                elif head['value'] is not None and head['value'] < p['min_incumbent_score']:
                    rejected.append('incumbent_margin_not_met')
        # Retained prior attempts never disappear from reliability eligibility.
        for previous in record['previous_checks']:
            earlier = assess_record_checks(previous['record'], previous['raw'])['candidates'].get(identity)
            if earlier:
                vetoes.extend(earlier['vetoes'])
        fixture = any(r['settings']['mode'] == 'fixture' for r in member['plans'])
        if fixture:
            reasons.append('artificial_validation_evidence')
        status = 'reject' if vetoes or rejected else 'inconclusive' if reasons else 'checked_incumbent' if identity == incumbent else 'eligible'
        candidates[identity] = {'status': status, 'reasons': sorted(set(reasons + rejected)), 'vetoes': vetoes,
            'validation': validation, 'validation_pairing': paired, 'official': official, 'clock': clocks}
    exposures = [{'plan_identity': r['identity'], 'purpose': r['settings']['purpose'],
        'attempts': raw.get(r['identity'], {}).get('attempts', []),
        'results': [dict(game_id=result['game_id'], exposure=result.get('exposure'))
                    for result in raw.get(r['identity'], {}).get('results', [])]}
        for s in ('validation', 'official') for m in record[s]['members'] for r in m['plans']]
    return {'format': FORMAT, 'check_identity': digest(record), 'policy_identity': digest(p),
        'candidates': candidates, 'eligible': sorted(i for i, c in candidates.items() if c['status'] == 'eligible'),
        'retained_incumbent': incumbent, 'promotion': False, 'untouched_final_evidence': False,
        'prior_exposures': record['prior_exposures'], 'exposures': exposures,
        'previous_check_identities': [digest(x['record']) for x in record['previous_checks']],
        'limitations': 'Validation influenced Phase 4 and repeated development decisions; limited design independence. '
            'No untouched final evidence, class rank or qualification claim. Zero failures is sample-limited. '
            'Eligibility only; champion transaction is separate. Power/load are recorded observations/declarations, not isolation guarantees.'}


def run(output: Path, *, conditions: dict[str, Any], max_jobs_per_plan: int) -> dict[str, Any]:
    check_conditions(conditions)
    if type(max_jobs_per_plan) is not int or max_jobs_per_plan < 0:
        raise ValueError('Declare a nonnegative bounded attempt count.')
    record = load(output)
    with owner(output):
        path = output / 'eligibility-results.json'
        previous = {}
        if path.exists():
            envelope = json.loads(path.read_text(encoding='utf-8'))
            data = envelope['data']
            if envelope['identity'] != digest(data) or data['check_identity'] != digest(record):
                raise ValueError('Eligibility results identity mismatch.')
            previous = data['raw']
            assess_record_checks(record, previous)
        plans = [ExperimentPlan.from_record(r) for s in ('validation', 'official')
                 for m in record[s]['members'] for r in m['plans']]
        for plan in plans:
            verify_versions(plan)
            directory = output / plan.identity
            if plan.identity in previous and not (directory / 'checkpoint.json').exists():
                raise ValueError('Missing authoritative eligibility checkpoint.')
            if (directory / 'checkpoint.json').exists():
                with owner(directory):
                    checkpoint = Checkpoint(plan, directory, True, record['policy']['infrastructure_retries'])
                    retained = {a['attempt_id']: a for a in checkpoint.data['attempts']}
                    earlier = previous.get(plan.identity, {})
                    for attempt in earlier.get('attempts', []):
                        current = retained.get(attempt['attempt_id'])
                        fields = set(attempt) - {'state', 'reason'}
                        if (current is None or (attempt['state'] != 'running' and current != attempt)
                                or any(current.get(k) != attempt[k] for k in fields)):
                            raise ValueError('Prior eligibility attempt lost from checkpoint.')
                    segments = {s['id']: s['conditions'] for s in checkpoint.data['segments']}
                    if any(segments.get(s['id']) != s['conditions'] for s in earlier.get('segments', [])):
                        raise ValueError('Prior eligibility conditions lost from checkpoint.')
        raw = dict(previous)
        try:
            for plan in plans:
                directory = output / plan.identity
                raw[plan.identity] = run_experiment(plan, output=directory, resume=directory.exists(),
                    max_jobs=max_jobs_per_plan, infrastructure_retries=record['policy']['infrastructure_retries'],
                    workers=1, contention=canonical(conditions))
                data = {'check_identity': digest(record), 'raw': raw}
                atomic_json(path, {'identity': digest(data), 'data': data})
        finally:
            # Child checkpoints remain authoritative if execution is interrupted.
            report = assess_record_checks(record, raw)
            atomic_json(output / 'eligibility-report.json', report)
        return report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--conditions', type=Path, required=True, help='Actual power/load and stopped experiments declaration')
    parser.add_argument('--max-jobs-per-plan', type=int, required=True)
    args = parser.parse_args()
    report = run(args.output, conditions=json.loads(args.conditions.read_text(encoding='utf-8')),
                 max_jobs_per_plan=args.max_jobs_per_plan)
    print(canonical({k: report[k] for k in ('eligible', 'retained_incumbent', 'promotion')}))


if __name__ == '__main__':
    main()
