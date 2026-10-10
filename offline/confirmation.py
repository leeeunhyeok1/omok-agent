# AI-written by OpenAI Codex, for issue #41.
"""Fresh, fixed-budget training confirmation with conservative paired sensitivity."""
from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from typing import Any

from offline.batches import Checkpoint, atomic_json, owner, verify_versions
from offline.experiments import ExperimentPlan, run_experiment, save_new_json
from offline.registry import Entry, PoolSnapshot, canonical, digest
from offline.league import assess_round, load as load_league
from offline.screening import (ScreeningPolicy, assess_stage, build_stage, load_stage,
                               validate_stage)
from omok.simulator import Position

FORMAT = 'omok-training-confirmation-v1'
METHOD = 'paired distinct color-block effects; weighted families; leave-one-block/family sensitivity'
STOPPING = 'fixed saved jobs and bounded infrastructure retries; no outcome-driven elimination or resampling'
CONDITION_KEYS = ('cpu', 'cpu_count', 'ram_bytes', 'machine', 'platform', 'python',
                  'implementation', 'affinity', 'workers', 'contention', 'start_method')


def starting_state(job: dict[str, Any]) -> list[Any]:
    # Players start fresh from this state; earlier opening move order is provenance.
    return [job['opening']['board'], job['opening']['side_to_move']]


def variation(job: dict[str, Any]) -> str:
    """Conservative dependence block: unsupported seeding earns no replication credit."""
    support = job['seed_support']
    seeds = {role: job['seeds'][role] for role, kind in support.items()
             if kind not in ('deterministic', 'unsupported')} if 'unsupported' not in support.values() else {}
    return digest([job['opponent']['identity'], starting_state(job), seeds])


def sample_keys(member: dict[str, Any]) -> set[tuple[str, int]]:
    return {(variation(j), j['candidate_color']) for p in member['plans'] for j in p['jobs']}


def assess_selection(source: dict[str, Any], context: dict[str, Any] | None,
                     raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if context is not None:
        if context['screening'] != source:
            raise ValueError('Broader selection context mismatch.')
        return assess_round(context, raw)
    return assess_stage(source, raw)


@dataclass(frozen=True)
class ConfirmationPolicy:
    definition: str

    def __post_init__(self) -> None:
        data = json.loads(self.definition)
        if set(data) != {'version', 'screening', 'method', 'stopping', 'min_pairs_per_opponent',
                         'min_families', 'max_family_regression', 'max_color_regression'}:
            raise ValueError('Unsupported confirmation policy.')
        if data['version'] != FORMAT or data['method'] != METHOD or data['stopping'] != STOPPING:
            raise ValueError('Confirmation method/stopping invariants cannot change.')
        ScreeningPolicy(canonical(data['screening']))
        for key in ('min_pairs_per_opponent', 'min_families'):
            if type(data[key]) is not int or data[key] < 1:
                raise ValueError('Declare positive distinct coverage minima.')
        for key in ('max_family_regression', 'max_color_regression'):
            value = data[key]
            if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 1:
                raise ValueError('Invalid regression margin.')
        object.__setattr__(self, 'definition', canonical(data))

    @classmethod
    def create(cls, **settings: Any) -> 'ConfirmationPolicy':
        return cls(canonical({'version': FORMAT, 'screening': ScreeningPolicy.create_defaults(),
            'method': METHOD, 'stopping': STOPPING, 'min_pairs_per_opponent': 2, 'min_families': 2,
            'max_family_regression': 0, 'max_color_regression': 0} | settings))

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self.definition)

    def save(self, path: Path) -> None:
        save_new_json(path, {'identity': digest(self.data), 'policy': self.data})

    @classmethod
    def load(cls, path: Path) -> 'ConfirmationPolicy':
        record = json.loads(path.read_text(encoding='utf-8'))
        result = cls(canonical(record['policy']))
        if record['identity'] != digest(result.data):
            raise ValueError('Confirmation policy identity mismatch.')
        return result


def prepare(policy_path: Path, *, selection: Path, selection_raw: dict[str, dict[str, Any]],
            output: Path, fixture: Position | None = None,
            openings: list[list[list[int]]] | None = None) -> dict[str, Any]:
    """Freeze finalists, source evidence and fresh comparable jobs before dispatch."""
    policy = ConfirmationPolicy.load(policy_path)
    context = load_league(selection) if (selection / 'league.json').exists() else None
    source = context['screening'] if context is not None else load_stage(selection)
    decision = assess_selection(source, context, selection_raw)
    if not decision['advanced']:
        raise ValueError('Selection has no eligible finalists.')
    entries = {m['entry']['identity']: Entry.from_record(m['entry']) for m in source['members']}
    gates = {m['entry']['identity']: m['gates'] for m in source['members']}
    stage = build_stage(ScreeningPolicy(canonical(policy.data['screening'])), entries[source['incumbent']],
        [entries[i] for i in decision['advanced']], PoolSnapshot.from_record(source['pool_snapshot']),
        fixture=fixture, openings=openings, gates=gates)
    record = {'format': FORMAT, 'policy': policy.data, 'selection': source,
              'selection_context': context, 'selection_raw': selection_raw, 'stage': stage}
    validate(record)
    output.mkdir(parents=True, exist_ok=False)
    save_new_json(output / 'confirmation.json', {'identity': digest(record), 'confirmation': record})
    return stage


def validate(record: dict[str, Any]) -> None:
    policy = ConfirmationPolicy(canonical(record['policy']))
    if record['format'] != FORMAT:
        raise ValueError('Unsupported confirmation stage.')
    validate_stage(record['stage'])
    validate_stage(record['selection'])
    source, stage = record['selection'], record['stage']
    context = record['selection_context']
    decision = assess_selection(source, context, record['selection_raw'])
    if (stage['policy']['policy'] != policy.data['screening']
            or stage['incumbent'] != source['incumbent']
            or stage['pool_snapshot'] != source['pool_snapshot']
            or {m['entry']['identity'] for m in stage['members']} != set(decision['advanced']) | {source['incumbent']}):
        raise ValueError('Confirmation must retain selected identities, incumbent and pool.')
    old = {m['entry']['identity']: m for m in source['members']}
    sources = [source]
    def collect(round_stage: dict[str, Any]) -> None:
        sources.extend(r['stage'] for r in round_stage['prior_rungs'])
        for previous in round_stage['prior_rounds']:
            sources.append(previous['stage']['screening'])
            collect(previous['stage'])
    if context is not None:
        collect(context)
    for member in stage['members']:
        if member['gates'] != old[member['entry']['identity']]['gates']:
            raise ValueError('Confirmation cannot rewrite selection gates.')
        for earlier in sources:
            for prior in earlier['members']:
                if prior['entry']['identity'] == member['entry']['identity'] and sample_keys(member) & sample_keys(prior):
                    raise ValueError('Confirmation requires fresh effective seeds/openings, including deterministic groups.')


def load(output: Path) -> dict[str, Any]:
    envelope = json.loads((output / 'confirmation.json').read_text(encoding='utf-8'))
    record = envelope['confirmation']
    if envelope['identity'] != digest(record):
        raise ValueError('Confirmation identity mismatch.')
    validate(record)
    return record


def execution_signature(evidence: dict[str, Any], game_id: str) -> dict[str, Any] | None:
    result = next((r for r in evidence['results'] if r['game_id'] == game_id), None)
    if result is None:
        return None
    segment = next((s for s in evidence.get('segments', []) if s['id'] == result.get('segment')), None)
    return {k: segment['conditions'].get(k) for k in CONDITION_KEYS} if segment else None


def paired_effects(member: dict[str, Any], incumbent: dict[str, Any], report: dict[str, Any],
                   baseline: dict[str, Any], raw: dict[str, dict[str, Any]], p: dict[str, Any]) -> dict[str, Any]:
    """Pair by opponent, recorded variation and color, then collapse duplicate blocks."""
    policy = p['screening']
    base_plans = {r['settings']['opponents'][0]: r for r in incumbent['plans']}
    blocks = []
    reasons = []
    pairings = []
    for saved, matchup in zip(member['plans'], report['reports']):
        name = saved['settings']['opponents'][0]
        other = base_plans[name]
        base_report = next(r for r in baseline['reports'] if r['opponents'][0]['logical_id'] == name)
        slots = {s['game_id']: s for s in matchup['matches'][0]['slots']}
        base_slots = {s['game_id']: s for s in base_report['matches'][0]['slots']}
        grouped: dict[str, dict[int, list[float]]] = {}
        outcomes: dict[tuple[str, int], set[tuple[str, str]]] = {}
        for job, base_job in zip(saved['jobs'], other['jobs']):
            support = list(job['seed_support'].values()) + list(base_job['seed_support'].values())
            varied = 'unsupported' not in support and any(s != 'deterministic' for s in support)
            key = digest([job['opponent']['identity'], starting_state(job), job['game_seed'] if varied else None])
            a, b = slots[job['game_id']], base_slots[base_job['game_id']]
            values = {'candidate_win': 1, 'opponent_win': 0, 'draw': policy['draw_credit']}
            left, right = a['recognized_result'], b['recognized_result']
            empty: dict[str, Any] = {'results': []}
            conditions = execution_signature(raw.get(saved['identity'], empty), job['game_id'])
            base_conditions = execution_signature(raw.get(other['identity'], empty), base_job['game_id'])
            pairings.append({'candidate_job': job['game_id'], 'incumbent_job': base_job['game_id'],
                'block': key, 'opponent': name, 'color': job['candidate_color'],
                'candidate_result': left, 'incumbent_result': right,
                'candidate_conditions': conditions, 'incumbent_conditions': base_conditions})
            if left in values and right in values:
                if conditions != base_conditions:
                    reasons.append('incomparable_execution_segments')
                if (conditions is None or base_conditions is None) and saved['settings']['mode'] != 'fixture':
                    reasons.append('unassigned_execution_segment')
                outcomes.setdefault((key, job['candidate_color']), set()).add((left, right))
                grouped.setdefault(key, {}).setdefault(job['candidate_color'], []).append(values[left] - values[right])
        if any(len(v) > 1 for v in outcomes.values()):
            reasons.append('conflicting_duplicate_outcomes')
        for key, block_colors in grouped.items():
            if set(block_colors) != {0, 1}:
                continue
            if any(len(set(v)) > 1 for v in block_colors.values()):
                reasons.append('conflicting_duplicate_outcomes')
            blocks.append({'id': key, 'opponent': name, 'family': saved['jobs'][0]['opponent']['family'],
                           'colors': {str(c): sum(v) / len(v) for c, v in block_colors.items()}})
    by_opponent = {}
    for name in policy['opponents']:
        observed = [b for b in blocks if b['opponent'] == name]
        if len(observed) < p['min_pairs_per_opponent']:
            reasons.append('insufficient_distinct_pairs')
        by_opponent[name] = {'distinct_pairs': len(observed),
            'by_color': {color: sum(b['colors'][str(c)] for b in observed) / len(observed) if observed else None
                         for c, color in enumerate(('black', 'white'))}}

    def aggregate(selected: list[dict[str, Any]], color: str | None = None) -> tuple[float | None, dict[str, float]]:
        opponents = {}
        for name in {b['opponent'] for b in selected}:
            chosen = [b for b in selected if b['opponent'] == name]
            opponents[name] = sum(b['colors'][color] if color is not None else
                sum(b['colors'][str(c)] * policy['color_weights'][n] for c, n in enumerate(('black', 'white')))
                / sum(policy['color_weights'].values()) for b in chosen) / len(chosen)
        families = {}
        for family in {b['family'] for b in selected}:
            names = {b['opponent'] for b in selected if b['family'] == family}
            families[family] = sum(opponents[n] * policy['opponent_weights'][n] for n in names) / sum(
                policy['opponent_weights'][n] for n in names)
        value = sum(v * policy['family_weights'][f] for f, v in families.items()) / sum(
            policy['family_weights'][f] for f in families) if families else None
        return value, families

    effect, families = aggregate(blocks)
    colors = {n: aggregate(blocks, str(c))[0] for c, n in enumerate(('black', 'white'))}
    if len(families) < p['min_families']:
        reasons.append('insufficient_families')
    sensitivity = []
    for block in blocks:
        reduced = [b for b in blocks if b is not block]
        if {b['opponent'] for b in reduced} == set(policy['opponents']):
            sensitivity.append({'omitted_block': block['id'], 'effect': aggregate(reduced)[0]})
    for family in families:
        reduced = [b for b in blocks if b['family'] != family]
        if reduced:
            sensitivity.append({'omitted_family': family, 'effect': aggregate(reduced)[0]})
    if not sensitivity:
        reasons.append('insufficient_sensitivity_coverage')
    effects = [effect] + [s['effect'] for s in sensitivity] if effect is not None else []
    return {'effect': effect, 'by_family_effect': families, 'by_color_effect': colors,
            'paired_opponents': by_opponent, 'pairings': pairings, 'blocks': blocks,
            'distinct_pairs': len(blocks), 'sensitivity': sensitivity,
            'sensitivity_range': [min(effects), max(effects)] if effects else None,
            'independent_trials_assumed': False, 'pairing_reasons': sorted(set(reasons))}


def assess(output: Path, raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    record = load(output)
    return assess_record(record, raw)


def assess_record(record: dict[str, Any], raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    validate(record)
    report = assess_stage(record['stage'], raw)
    report.update(format=FORMAT, confirmation_identity=digest(record),
        selection_identity=digest(record['selection']), policy_identity=digest(record['policy']))
    stage, p = record['stage'], record['policy']
    incumbent = next(m for m in stage['members'] if m['entry']['identity'] == stage['incumbent'])
    baseline = report['candidates'][stage['incumbent']]
    for saved in stage['members']:
        identity = saved['entry']['identity']
        member = report['candidates'][identity]
        member.update(paired_effects(saved, incumbent, member, baseline, raw, p))
        member['reasons'] = sorted(set(member['reasons']) - {'insufficient_favorable_gain'})
        if identity == stage['incumbent']:
            member['status'] = 'retain'
            continue
        member['reasons'] += member['pairing_reasons']
        if member['vetoes']:
            member['status'] = 'reject'
        elif member['reasons'] or baseline['reasons'] or baseline['vetoes']:
            member['status'] = 'inconclusive'
        elif any(v < -p['max_family_regression'] for v in member['by_family_effect'].values()) or any(
                v is not None and v < -p['max_color_regression'] for v in member['by_color_effect'].values()):
            member['status'] = 'reject'
            member['reasons'].append('family_or_color_regression')
        elif member['effect'] is None or member['effect'] <= 0 or member['effect'] < p['screening']['min_gain']:
            member['status'] = 'reject'
            member['reasons'].append('insufficient_favorable_effect')
        elif member['sensitivity_range'][0] <= 0 or member['sensitivity_range'][0] < p['screening']['min_gain']:
            member['status'] = 'inconclusive'
            member['reasons'].append('sensitivity_does_not_support_gain')
        else:
            member['status'] = 'advance'
    report['advanced'] = sorted(i for i, e in report['candidates'].items() if e['status'] == 'advance')
    report['decision_method'] = METHOD
    report['stopping'] = STOPPING
    selection_report = assess_selection(record['selection'], record['selection_context'], record['selection_raw'])
    report['selection_summary'] = {'stage_identity': selection_report['stage_identity'],
        'cohort_size': len(selection_report['candidates']) - 1, 'advanced': selection_report['advanced'],
        'reuse_for_confirmation_effect': False}
    report['ordinary_strength_evidence'] = all(r['settings']['mode'] != 'fixture'
        for m in stage['members'] for r in m['plans'])
    report['limitations'] = ('Selection-winning samples are excluded from effect estimates. Sensitivity ranges are '
        'descriptive robustness checks, not confidence intervals or fixed-sample statistical proof. Colors share '
        'variation blocks; related opponents share family weight. Seeds cannot guarantee independent games. '
        'Training confirmation only; later validation and official-clock checks required. Artificial fixtures '
        'test decision mechanics; reduced-clock evidence never establishes official qualification.')
    return report


def run(output: Path, *, max_jobs_per_plan: int | None = None) -> dict[str, Any]:
    record = load(output)
    raw = {}
    with owner(output):
        previous = {}
        evidence_path = output / 'confirmation-results.json'
        if evidence_path.exists():
            envelope = json.loads(evidence_path.read_text(encoding='utf-8'))
            data = envelope['data']
            if envelope['identity'] != digest(data) or data['confirmation_identity'] != digest(record):
                raise ValueError('Confirmation results identity mismatch.')
            previous = data['raw']
            assess(output, previous)
        plans = [ExperimentPlan.from_record(r) for m in record['stage']['members'] for r in m['plans']]
        # Check every child before starting another job in any plan.
        for plan in plans:
            verify_versions(plan)
            directory = output / plan.identity
            if plan.identity in previous and not (directory / 'checkpoint.json').exists():
                raise ValueError('Missing authoritative confirmation checkpoint.')
            if (directory / 'checkpoint.json').exists():
                with owner(directory):
                    checkpoint = Checkpoint(plan, directory, True, record['policy']['screening']['infrastructure_retries'])
                    retained = {a['attempt_id']: a for a in checkpoint.data['attempts']}
                    earlier = previous.get(plan.identity, {})
                    for attempt in earlier.get('attempts', []):
                        current = retained.get(attempt['attempt_id'])
                        fields = set(attempt) - {'state', 'reason'}
                        if (current is None or (attempt['state'] != 'running' and current != attempt)
                                or any(current.get(k) != attempt[k] for k in fields)):
                            raise ValueError('Prior evidence lost from authoritative confirmation checkpoint.')
                    segments = {s['id']: s['conditions'] for s in checkpoint.data['segments']}
                    if any(segments.get(s['id']) != s['conditions'] for s in earlier.get('segments', [])):
                        raise ValueError('Prior execution conditions lost from authoritative confirmation checkpoint.')
        for member in record['stage']['members']:
            for saved in member['plans']:
                plan = ExperimentPlan.from_record(saved)
                directory = output / plan.identity
                raw[plan.identity] = run_experiment(plan, output=directory, resume=directory.exists(),
                    max_jobs=max_jobs_per_plan,
                    infrastructure_retries=record['policy']['screening']['infrastructure_retries'])
        report = assess(output, raw)
        data = {'confirmation_identity': digest(record), 'raw': raw}
        atomic_json(evidence_path, {'identity': digest(data), 'data': data})
        atomic_json(output / 'confirmation-report.json', report)
    return report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Previously prepared confirmation stage')
    parser.add_argument('--max-jobs-per-plan', type=int, required=True, help='Bound attempts per saved plan for this invocation')
    args = parser.parse_args()
    report = run(args.output, max_jobs_per_plan=args.max_jobs_per_plan)
    print(canonical({k: report[k] for k in ('confirmation_identity', 'advanced', 'retained_incumbent', 'promotion')}))


if __name__ == '__main__':
    main()
