# AI-written by OpenAI Codex, for issue #38.
"""Predeclared training screening over immutable Phase 4 plans and evidence."""
from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from typing import Any

from offline.batches import atomic_json, owner
from offline.experiments import ExperimentPlan, run_experiment, save_new_json
from offline.matches import game_score, FORFEIT_REASONS
from offline.registry import Entry, PoolSnapshot, canonical, digest
from offline.reports import report_experiment, attempt_history
from omok.simulator import Position

FORMAT = 'omok-training-screening-v1'
GATES = ('restoration', 'invalid_score', 'mandatory_tactic')


@dataclass(frozen=True)
class ScreeningPolicy:
    definition: str

    def __post_init__(self) -> None:
        data = json.loads(self.definition)
        if set(data) != set(self.create_defaults()) or data['version'] != FORMAT:
            raise ValueError('Unsupported screening policy.')
        defaults = self.create_defaults()
        for key in ('purpose', 'objective', 'denominators', 'completion', 'stopping', 'failures'):
            if data[key] != defaults[key]:
                raise ValueError('Screening invariants cannot be weakened: ' + key)
        opponents = data['opponents']
        if not isinstance(opponents, dict) or not opponents or set(opponents) != set(data['opponent_weights']):
            raise ValueError('Declare the stage subset, budgets and opponent weights.')
        if any(type(n) is not int or n <= 0 or n % 2 for n in opponents.values()):
            raise ValueError('Every opponent requires positive balanced color pairs.')
        for weights in (data['opponent_weights'], data['family_weights'], data['color_weights']):
            if not weights or any(type(w) not in (int, float) or not isfinite(w) or w <= 0 for w in weights.values()):
                raise ValueError('Weights must be finite and positive.')
        if set(data['color_weights']) != {'black', 'white'}:
            raise ValueError('Both colors require declared weights.')
        for name in ('draw_credit', 'min_gain', 'max_cap_excess'):
            value = data[name]
            if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 1:
                raise ValueError('Invalid score/censoring threshold: ' + name)
        if type(data['min_evidence_per_color']) is not int or data['min_evidence_per_color'] < 1:
            raise ValueError('Declare a positive evidence minimum per opponent/color.')
        if type(data['infrastructure_retries']) is not int or not 0 <= data['infrastructure_retries'] <= 3:
            raise ValueError('Infrastructure retries must be bounded in 0..3.')
        if type(data['move_cap']) is not int or data['move_cap'] < 0:
            raise ValueError('Invalid move cap.')
        if type(data['seed']) is not int:
            raise ValueError('Seed must be an integer.')
        clock = data['total_ms']
        if type(clock) not in (int, float) or not isfinite(clock) or not 0 < clock < 60000:
            raise ValueError('Screening requires a reduced positive finite total clock.')
        object.__setattr__(self, 'definition', canonical(data))

    @staticmethod
    def create_defaults() -> dict[str, Any]:
        return {'version': FORMAT, 'purpose': 'training',
            'objective': 'weighted game points: win=1, loss=0, draw=draw_credit; no match coins or ratings',
            'denominators': 'recognized games per opponent/color; normalized colors, opponents within family, then families',
            'completion': '100% requested recognized jobs, all opponents available; partial display only',
            'stopping': 'fixed saved jobs; no outcome-driven resampling; advance requires strictly positive gain >= min_gain',
            'failures': 'any candidate player failure in any validated attempt vetoes; external gates required; infrastructure unresolved',
            'opponents': {}, 'opponent_weights': {}, 'family_weights': {},
            'color_weights': {'black': 1, 'white': 1}, 'draw_credit': .5,
            'min_gain': .05, 'min_evidence_per_color': 2, 'max_cap_excess': 0,
            'infrastructure_retries': 1, 'total_ms': 5000, 'move_cap': 1000, 'seed': 38}

    @classmethod
    def create(cls, **settings: Any) -> 'ScreeningPolicy':
        return cls(canonical(cls.create_defaults() | settings))

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self.definition)

    @property
    def identity(self) -> str:
        return digest(self.data)

    def save(self, path: Path) -> None:
        save_new_json(path, {'identity': self.identity, 'policy': self.data})

    @classmethod
    def load(cls, path: Path) -> 'ScreeningPolicy':
        record = json.loads(path.read_text(encoding='utf-8'))
        policy = cls(canonical(record['policy']))
        if record['identity'] != policy.identity:
            raise ValueError('Saved screening policy identity mismatch.')
        return policy


def prepare(policy_path: Path, incumbent: Entry, candidates: list[Entry], snapshot: PoolSnapshot, *,
            output: Path, fixture: Position | None = None,
            openings: list[list[list[int]]] | None = None,
            gates: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Save the entire cohort and requested coverage before any jobs are dispatched."""
    policy = ScreeningPolicy.load(policy_path)
    stage = build_stage(policy, incumbent, candidates, snapshot, fixture=fixture, openings=openings, gates=gates)
    output.mkdir(parents=True, exist_ok=False)
    save_new_json(output / 'stage.json', {'identity': digest(stage), 'stage': stage})
    return stage


def build_stage(policy: ScreeningPolicy, incumbent: Entry, candidates: list[Entry], snapshot: PoolSnapshot, *,
                fixture: Position | None = None, openings: list[list[list[int]]] | None = None,
                gates: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Resolve and validate a cohort without dispatch or filesystem side effects."""
    data = policy.data
    pools = snapshot.record()['pools']
    requested = {}
    for name in data['opponents']:
        found = [(pool, r) for pool, records in pools.items() for r in records if r['logical_id'] == name]
        if not found or found[0][0] != 'training':
            raise ValueError('Screening requests training opponents only: ' + name)
        requested[name] = found[0][1]
    if set(data['family_weights']) != {r['family'] for r in requested.values()}:
        raise ValueError('Declare exactly the requested family weights.')
    entries = [incumbent] + sorted(candidates, key=lambda e: e.identity)
    if len({e.identity for e in entries}) != len(entries):
        raise ValueError('Duplicate candidate/incumbent identity.')
    members = []
    for entry in entries:
        snapshot.validate_candidate(entry, purpose='training')
        plans = []
        for name, count in data['opponents'].items():
            if requested[name]['availability'] != 'ready':
                continue
            plan = ExperimentPlan.resolve(entry, snapshot, purpose='training', opponents=[name],
                mode='fixture' if fixture is not None else 'screening', fixture=fixture,
                openings=openings, games_per_opponent=count, seed=data['seed'],
                total_ms=data['total_ms'], move_cap=data['move_cap'], diagnostics=True)
            plans.append(plan.record())
        members.append({'entry': entry.record(), 'plans': plans,
                        'gates': (gates or {}).get(entry.identity, [])})
    stage = {'format': FORMAT, 'policy': {'identity': policy.identity, 'policy': data},
             'pool_snapshot': snapshot.record(), 'requested_opponents': requested,
             'incumbent': incumbent.identity, 'members': members}
    validate_stage(stage)
    return stage


def validate_stage(stage: dict[str, Any]) -> None:
    policy = ScreeningPolicy(canonical(stage['policy']['policy']))
    if stage['format'] != FORMAT or policy.identity != stage['policy']['identity']:
        raise ValueError('Invalid stage/policy identity.')
    snapshot = PoolSnapshot.from_record(stage['pool_snapshot'])
    p = policy.data
    members = stage['members']
    identities = [Entry.from_record(m['entry']).identity for m in members]
    if len(set(identities)) != len(identities) or stage['incumbent'] not in identities:
        raise ValueError('Invalid cohort.')
    requested = {r['logical_id']: r for r in snapshot.record()['pools']['training']
                 if r['logical_id'] in p['opponents']}
    if requested != stage['requested_opponents'] or set(requested) != set(p['opponents']):
        raise ValueError('Requested coverage must be training only.')
    if {r['family'] for r in requested.values()} != set(p['family_weights']):
        raise ValueError('Family coverage mismatch.')
    comparison = None
    for member in members:
        entry = Entry.from_record(member['entry'])
        snapshot.validate_candidate(entry, purpose='training')
        signature = []
        names = []
        for record in member['plans']:
            plan = ExperimentPlan.from_record(record)
            settings = plan.data['settings']
            name = settings['opponents'][0]
            if (settings['purpose'] != 'training' or settings['mode'] not in ('screening', 'fixture')
                    or plan.data['candidate'] != member['entry'] or plan.data['pool_snapshot'] != snapshot.record()
                    or len(settings['opponents']) != 1 or name not in requested
                    or settings['games_per_opponent'] != p['opponents'][name]
                    or settings['seed'] != p['seed'] or settings['budgets_ms'] != [p['total_ms']] * 2
                    or settings['move_cap'] != p['move_cap']):
                raise ValueError('Plan violates saved training policy.')
            names.append(name)
            signature.append(settings)
        if set(names) != {n for n, r in requested.items() if r['availability'] == 'ready'} or len(names) != len(set(names)):
            raise ValueError('Ready opponents must have exactly one plan.')
        if comparison is not None and comparison != signature:
            raise ValueError('Cohort jobs/settings must be comparable.')
        comparison = signature
        for gate in member['gates']:
            if (gate.get('check') not in GATES or gate.get('status') not in ('pass', 'fail', 'inconclusive')
                    or type(gate.get('samples')) is not int or gate['samples'] < 1 or not gate.get('evidence')):
                raise ValueError('Gate requires a known check, status, sample size and evidence.')
        if len({g['check'] for g in member['gates']}) != len(member['gates']):
            raise ValueError('Duplicate gate check.')


def load_stage(output: Path) -> dict[str, Any]:
    record = json.loads((output / 'stage.json').read_text(encoding='utf-8'))
    stage = record['stage']
    if record['identity'] != digest(stage):
        raise ValueError('Saved stage identity mismatch.')
    validate_stage(stage)
    return stage


def member_evidence(member: dict[str, Any], stage: dict[str, Any], raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    p = stage['policy']['policy']
    vetoes = [g for g in member['gates'] if g['status'] == 'fail']
    reasons = []
    if {g['check'] for g in member['gates'] if g['status'] == 'pass'} != set(GATES):
        reasons.append('external_gates_not_passed')
    reports = []
    by_opponent = {}
    cap_count = 0
    committed_attempts = 0
    candidate_failure_attempts = 0
    for record in member['plans']:
        plan = ExperimentPlan.from_record(record)
        evidence = raw.get(plan.identity, dict(format='omok-experiment-results-v1',
                       manifest_identity=plan.identity, results=[]))
        report = report_experiment(plan, evidence)
        reports.append(report)
        attempts, _, _ = attempt_history(plan, evidence)
        jobs = {j['game_id']: j for j in plan.data['jobs']}
        prior_commits: dict[str, list[dict[str, Any]]] = {}
        for attempt in attempts:
            if attempt['state'] != 'committed':
                continue
            committed_attempts += 1
            result = attempt['result']
            job = jobs[attempt['game_id']]
            prior = prior_commits.setdefault(job['game_id'], [])
            if prior:
                previous = prior[-1]
                previous_trace = previous.get('trace') or {}
                if (len(prior) > p['infrastructure_retries']
                        or previous['status'] not in ('setup_failed', 'supervisor_error')
                        or previous_trace.get('prior_result', {}).get('status') == 'failed'):
                    reasons.append('invalid_retry_history')
            prior.append(result)
            scored = game_score(job, result, plan.record())
            if 'validation_error' in scored:
                reasons.append('invalid_attempt_evidence')
                continue
            trace = result.get('trace') or {}
            failures = [trace.get('failure'), trace.get('prior_result', {}).get('failure')]
            attempt_failed = False
            for failure in failures:
                if failure and failure['color'] == job['candidate_color'] and any(
                        v in FORFEIT_REASONS for v in failure['violations']):
                    vetoes.append({'game_id': job['game_id'], 'attempt_id': attempt.get('attempt_id'),
                                   'failure': failure, 'result': result})
                    attempt_failed = True
            candidate_failure_attempts += attempt_failed
        # Latest results cannot erase a player failure in an earlier attempt.
        cap_count += report['jobs']['counts']['capped']
        opponent = report['opponents'][0]
        cells = {}
        for color in ('black', 'white'):
            cell = opponent['jobs']['by_color'][color]
            counts = cell['recognized']
            denominator = counts['wins'] + counts['losses'] + counts['draws']
            numerator = counts['wins'] + p['draw_credit'] * counts['draws']
            unique = {j.get('duplicate_evidence_group') or j['game_id'] for j in jobs.values()
                      if j['candidate_color'] == (0 if color == 'black' else 1)
                      and any(s['game_id'] == j['game_id'] and s['recognized_result'] is not None
                              for s in report['matches'][0]['slots'])}
            if denominator != cell['counts']['planned']:
                reasons.append('incomplete_coverage')
            if len(unique) < p['min_evidence_per_color']:
                reasons.append('insufficient_distinct_evidence')
            cells[color] = {'numerator': numerator, 'denominator': denominator,
                           'value': numerator / denominator if denominator else None,
                           'distinct_evidence': len(unique), 'counts': cell['counts']}
        available = all(c['value'] is not None for c in cells.values())
        value = sum(cells[c]['value'] * w for c, w in p['color_weights'].items()) / sum(p['color_weights'].values()) if available else None
        by_opponent[opponent['logical_id']] = {'by_color': cells, 'value': value,
                                               'family': opponent['family']}
    unavailable = [n for n, r in stage['requested_opponents'].items() if r['availability'] != 'ready']
    if unavailable:
        reasons.append('unavailable_opponents')
    complete = not any(r in reasons for r in ('incomplete_coverage', 'unavailable_opponents', 'invalid_attempt_evidence'))
    partial = None
    if by_opponent and all(o['value'] is not None for o in by_opponent.values()):
        families = {}
        for family in p['family_weights']:
            names = [n for n, o in by_opponent.items() if o['family'] == family]
            if names:
                families[family] = sum(by_opponent[n]['value'] * p['opponent_weights'][n] for n in names) / sum(p['opponent_weights'][n] for n in names)
        if families:
            partial = sum(v * p['family_weights'][f] for f, v in families.items()) / sum(p['family_weights'][f] for f in families)
    return {'fitness': partial if complete else None, 'partial_score': partial,
            'score_scope': 'declared training stage subset; partial_score is descriptive only',
            'by_opponent': by_opponent, 'unavailable_opponents': unavailable,
            'cap_rate': cap_count / sum(p['opponents'].values()), 'vetoes': vetoes,
            'reasons': sorted(set(reasons)), 'reports': reports, 'gates': member['gates'],
            'requested_jobs': sum(p['opponents'].values()),
            'reliability_samples': {'committed_attempts': committed_attempts,
                                    'candidate_failure_attempts': candidate_failure_attempts},
            'zero_observed_player_failures': not vetoes}


def assess(output: Path, raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Interpret controlled or saved execution results using the already saved policy."""
    stage = load_stage(output)
    return assess_stage(stage, raw)


def assess_stage(stage: dict[str, Any], raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Assess an embedded immutable stage, retaining the same validation boundary."""
    validate_stage(stage)
    expected = {r['identity'] for m in stage['members'] for r in m['plans']}
    if set(raw) - expected:
        raise ValueError('Foreign cohort evidence.')
    evidence = {m['entry']['identity']: member_evidence(m, stage, raw) for m in stage['members']}
    incumbent = evidence[stage['incumbent']]
    p = stage['policy']['policy']
    for identity, member in evidence.items():
        if member['cap_rate'] > incumbent['cap_rate'] + p['max_cap_excess']:
            member['reasons'].append('suspicious_censoring')
        member['gain'] = (member['fitness'] - incumbent['fitness']
                          if member['fitness'] is not None and incumbent['fitness'] is not None else None)
        if member['vetoes']:
            member['status'] = 'fail'
            member['reasons'].append('reliability_veto')
        elif member['reasons'] or incumbent['reasons'] or incumbent['vetoes']:
            member['status'] = 'inconclusive'
            if incumbent['reasons'] or incumbent['vetoes']:
                member['reasons'].append('incumbent_evidence_not_eligible')
        elif identity == stage['incumbent']:
            member['status'] = 'retain'
        elif member['gain'] is not None and member['gain'] > 0 and member['gain'] >= p['min_gain']:
            member['status'] = 'advance'
        else:
            member['status'] = 'fail'
            member['reasons'].append('insufficient_favorable_gain')
    return {'format': FORMAT, 'stage_identity': digest(stage), 'policy_identity': stage['policy']['identity'],
            'candidates': evidence, 'retained_incumbent': stage['incumbent'], 'promotion': False,
            'advanced': sorted(i for i, e in evidence.items() if e['status'] == 'advance'),
            'limitations': 'Descriptive fixed-stage screening; advance requires fresh broader confirmation, validation and official-clock checks.'}


def run(output: Path, *, max_jobs_per_plan: int | None = None) -> dict[str, Any]:
    """Resume bounded Phase 4 batches; the saved cohort/policy never changes."""
    stage = load_stage(output)
    raw = {}
    with owner(output):
        for member in stage['members']:
            if any(g['status'] == 'fail' for g in member['gates']):
                continue
            for record in member['plans']:
                plan = ExperimentPlan.from_record(record)
                directory = output / plan.identity
                raw[plan.identity] = run_experiment(plan, output=directory, resume=directory.exists(),
                    max_jobs=max_jobs_per_plan, infrastructure_retries=stage['policy']['policy']['infrastructure_retries'])
        report = assess(output, raw)
        atomic_json(output / 'screening-report.json', report)
    return report
