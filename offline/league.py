# AI-written by OpenAI Codex, for issue #40.
# Issue #43 adds portable archives and compatible construction adapters.
"""Frozen broader training rounds, retained screening evidence and champion history."""
import base64
from dataclasses import dataclass
from hashlib import sha256
import io
import json
from math import isfinite
from pathlib import Path
import tarfile
from typing import Any

from offline.batches import Checkpoint, atomic_json, owner, verify_versions
from offline.experiments import ExperimentPlan, run_experiment, save_new_json
from offline.registry import Entry, PoolSnapshot, ROOT, canonical, checkpoint_archive, digest, archived_bundle
from offline.screening import ScreeningPolicy, assess_stage, load_stage, prepare as prepare_screening
from omok.simulator import Position

FORMAT = 'omok-training-league-v1'


@dataclass(frozen=True)
class LeaguePolicy:
    definition: str

    def __post_init__(self) -> None:
        data = json.loads(self.definition)
        if set(data) != {'version', 'screening', 'history_period', 'history_slots',
                         'max_family_regression', 'max_color_regression', 'max_matchup_regression'} or data['version'] != FORMAT:
            raise ValueError('Unsupported league policy.')
        ScreeningPolicy(canonical(data['screening']))
        if type(data['history_period']) is not int or data['history_period'] < 1:
            raise ValueError('History period must be positive.')
        if not isinstance(data['history_slots'], dict) or any(
                type(slot) is not int or not 0 <= slot < data['history_period']
                for slot in data['history_slots'].values()):
            raise ValueError('Invalid historical rotation slots.')
        for key in ('max_family_regression', 'max_color_regression', 'max_matchup_regression'):
            value = data[key]
            if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 1:
                raise ValueError('Invalid regression margin.')
        object.__setattr__(self, 'definition', canonical(data))

    @classmethod
    def create(cls, **settings: Any) -> 'LeaguePolicy':
        return cls(canonical({'version': FORMAT, 'screening': ScreeningPolicy.create_defaults(),
            'history_period': 1, 'history_slots': {}, 'max_family_regression': 0,
            'max_color_regression': 0, 'max_matchup_regression': 0} | settings))

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self.definition)

    def save(self, path: Path) -> None:
        save_new_json(path, {'identity': digest(self.data), 'policy': self.data})


def champion_bundle(entry: Entry) -> dict[str, Any]:
    """Capture verified source bytes and the unchanged registered configuration."""
    data = entry.data
    loader = data['loader']
    if loader['kind'] == 'archive':
        archived = archived_bundle(loader)
        bundle = {'entry': entry.record(), 'sources': archived['sources'], 'adapter': archived['adapter']}
        validate_history({'champions': [bundle]})
        return bundle
    if loader['kind'] == 'checkpoint':
        archive = checkpoint_archive(loader['commit'], tuple(loader['paths']))
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            files = {m.name: stream.extractfile(m).read() for m in stream.getmembers() if m.isfile()}  # type: ignore[union-attr]
    else:
        root = (ROOT / loader['root']).resolve()
        files = {name: (root / name).read_bytes() for name in data['sources']}
    sources = {name: base64.b64encode(files[name]).decode('ascii') for name in data['sources']}
    bundle = with_adapter({'entry': entry.record(), 'sources': sources})
    validate_history({'champions': [bundle]})
    return bundle


def with_adapter(bundle: dict[str, Any]) -> dict[str, Any]:
    """Retain the exact registered construction adapter alongside player code."""
    if 'adapter' in bundle:
        validate_history({'champions': [bundle]})
        return bundle
    entry = Entry.from_record(bundle['entry'])
    files = {name: (ROOT / name).read_bytes() for name in entry.data['adapter_sources']}
    if {name: sha256(value).hexdigest() for name, value in files.items()} != entry.data['adapter_sources']:
        raise ValueError('Registered construction adapter changed; retain compatible bytes or revalidate.')
    result = dict(bundle, adapter={name: base64.b64encode(value).decode('ascii') for name, value in files.items()})
    validate_history({'champions': [result]})
    return result


def archive_history(output: Path, champions: list[Entry]) -> dict[str, Any]:
    """Append write-once code/configuration bundles; never remove older champions."""
    output.mkdir(parents=True, exist_ok=True)
    with owner(output):
        for entry in champions:
            path = output / (entry.identity + '.json')
            if path.exists():
                continue
            bundle = champion_bundle(entry)
            save_new_json(path, {'identity': digest(bundle), 'bundle': bundle})
        bundles = []
        for path in sorted(output.glob('*.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            if record['identity'] != digest(record['bundle']):
                raise ValueError('Corrupt champion archive.')
            bundles.append(record['bundle'])
        result = {'champions': bundles}
        validate_history(result)
        return result


def validate_history(history: dict[str, Any]) -> list[Entry]:
    entries = []
    for bundle in history['champions']:
        if any(not name or Path(name).is_absolute() or Path(name).drive or '..' in Path(name).parts
               for name in bundle['sources'] | bundle.get('adapter', {})):
            raise ValueError('Archived source paths must stay inside their snapshot.')
        entry = Entry.from_record(bundle['entry'])
        hashes = {name: sha256(base64.b64decode(value, validate=True)).hexdigest()
                  for name, value in bundle['sources'].items()}
        if hashes != entry.data['sources']:
            raise ValueError('Archived champion source mismatch.')
        if 'adapter' in bundle:
            adapter = {name: sha256(base64.b64decode(value, validate=True)).hexdigest()
                       for name, value in bundle['adapter'].items()}
            if adapter != entry.data['adapter_sources']:
                raise ValueError('Archived construction adapter mismatch.')
        entries.append(entry)
    if len({e.identity for e in entries}) != len(entries):
        raise ValueError('Duplicate historical champion.')
    return entries


def prepare(policy_path: Path, incumbent: Entry, snapshot: PoolSnapshot, *, history: dict[str, Any],
            rungs: list[tuple[Path, dict[str, dict[str, Any]]]], output: Path,
            round_index: int = 0, previous_rounds: list[Path] | None = None,
            fixture: Position | None = None, openings: list[list[list[int]]] | None = None,
            gates: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Freeze survivors, all prior rungs, rotation and a newly measured incumbent."""
    record = json.loads(policy_path.read_text(encoding='utf-8'))
    policy = LeaguePolicy(canonical(record['policy']))
    if record['identity'] != digest(policy.data):
        raise ValueError('League policy identity mismatch.')
    originals = validate_history(history)
    champions = [Entry.archived(with_adapter(bundle)) for bundle in history['champions']]
    p = policy.data
    if type(round_index) is not int or round_index < 0 or len(previous_rounds or []) != round_index:
        raise ValueError('All preceding rounds are required for historical coverage.')
    prior = [load_results(path) for path in previous_rounds or []]
    if any(r['stage']['round_index'] != i for i, r in enumerate(prior)):
        raise ValueError('Historical rounds must be consecutive from zero.')
    if any(r['stage']['prior_rounds'] != prior[i - 1:i] for i, r in enumerate(prior) if i):
        raise ValueError('Historical predecessor evidence changed; prepare a new later round.')
    if prior:
        previous = prior[-1]['stage']['policy']
        if previous['history_period'] != p['history_period'] or any(
                p['history_slots'].get(key) != slot for key, slot in previous['history_slots'].items()):
            raise ValueError('Historical rotation cannot silently change or delete versions.')
    if set(p['history_slots']) != {e.identity for e in originals}:
        raise ValueError('Schedule every archived historical champion.')
    if incumbent.identity in p['history_slots']:
        raise ValueError('Current incumbent is not a historical opponent.')
    previous_rungs = []
    survivors: set[str] | None = None
    last_stage = None
    for path, raw in rungs:
        rung = load_stage(path)
        report = assess_stage(rung, raw)
        if rung['incumbent'] != incumbent.identity:
            raise ValueError('Screening incumbent mismatch.')
        cohort = {m['entry']['identity'] for m in rung['members']} - {incumbent.identity}
        if survivors is not None and cohort != survivors:
            raise ValueError('Every screening rung must retain exactly the preceding survivors.')
        survivors = set(report['advanced'])
        previous_rungs.append({'stage': rung, 'raw': raw})
        last_stage = rung
    if not previous_rungs or last_stage is None:
        raise ValueError('Broader league requires recorded screening rungs.')
    candidates = [Entry.from_record(m['entry']) for m in last_stage['members']
                  if m['entry']['identity'] in (survivors or set())]
    pools = {pool: [Entry.from_record(r) for r in records]
             for pool, records in snapshot.record()['pools'].items()}
    names = {e.data['logical_id'] for entries in pools.values() for e in entries}
    for e in [incumbent] + champions:
        if e.data['logical_id'] in names:
            existing = next(r for entries in pools.values() for r in entries if r.data['logical_id'] == e.data['logical_id'])
            original = next((o for o in originals if o.data['logical_id'] == e.data['logical_id']), e)
            if existing.identity not in (e.identity, original.identity) or existing.identity not in {r.identity for r in pools['training']}:
                raise ValueError('Incumbent/history conflicts with pool membership.')
            if existing.identity != e.identity:
                pools['training'] = [e if r.identity == existing.identity else r for r in pools['training']]
        else:
            pools['training'].append(e)
            names.add(e.data['logical_id'])
    league_snapshot = PoolSnapshot.freeze(pools)
    screen_data = p['screening']
    required = {incumbent.data['logical_id']} | {e.data['logical_id'] for e in champions}
    if not required <= set(screen_data['opponents']):
        raise ValueError('Declare incumbent and all historical sample allocations.')
    historical_names = {e.data['logical_id'] for e in champions}
    diverse = [e for e in pools['training'] if e.data['logical_id'] in screen_data['opponents']
               and e.data['logical_id'] not in required]
    if len({(e.data['origin'], e.data['family']) for e in diverse}) < 2:
        raise ValueError('Broader league requires at least two frozen training design families.')
    selected_history = [e for e in originals if p['history_slots'][e.identity] == round_index % p['history_period']]
    selected_names = set(screen_data['opponents']) - historical_names | {e.data['logical_id'] for e in selected_history}
    selected = league_snapshot.record()['pools']['training']
    requested = {r['logical_id']: r for r in selected if r['logical_id'] in screen_data['opponents']}
    if set(requested) != set(screen_data['opponents']):
        raise ValueError('League opponents must belong to training, including unavailable requests.')
    if {r['family'] for r in requested.values()} != set(screen_data['family_weights']):
        raise ValueError('Declare exactly the full league family weights.')
    effective = ScreeningPolicy.create(**(screen_data | {
        'seed': screen_data['seed'] + round_index,
        'opponents': {n: v for n, v in screen_data['opponents'].items() if n in selected_names},
        'opponent_weights': {n: v for n, v in screen_data['opponent_weights'].items() if n in selected_names},
        'family_weights': {f: w for f, w in screen_data['family_weights'].items()
                           if f in {r['family'] for r in selected if r['logical_id'] in selected_names}}}))
    output.mkdir(parents=True, exist_ok=False)
    effective.save(output / 'effective-policy.json')
    screen_stage = prepare_screening(output / 'effective-policy.json', incumbent, candidates,
        league_snapshot, output=output / 'screening', fixture=fixture, openings=openings, gates=gates)
    stage = {'format': FORMAT, 'policy': p, 'round_index': round_index, 'history': history,
             'selected_history': [e.identity for e in selected_history], 'prior_rounds': prior[-1:],
             'prior_rungs': previous_rungs, 'screening': screen_stage}
    save_new_json(output / 'league.json', {'identity': digest(stage), 'stage': stage})
    return stage


def load(output: Path) -> dict[str, Any]:
    record = json.loads((output / 'league.json').read_text(encoding='utf-8'))
    stage = record['stage']
    if record['identity'] != digest(stage) or stage['format'] != FORMAT:
        raise ValueError('League stage identity mismatch.')
    LeaguePolicy(canonical(stage['policy']))
    validate_history(stage['history'])
    return stage


def assess(output: Path, raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return assess_round(load(output), raw)


def assess_round(stage: dict[str, Any], raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    report = assess_stage(stage['screening'], raw)
    report.update(format=FORMAT, stage_identity=digest(stage), round_index=stage['round_index'],
                  policy_identity=digest(stage['policy']),
                  prior_rungs=[assess_stage(r['stage'], r['raw']) for r in stage['prior_rungs']])
    p = stage['policy']
    incumbent = report['candidates'][report['retained_incumbent']]
    for identity, member in report['candidates'].items():
        families: dict[str, float] = {}
        colors: dict[str, float] = {}
        opponents = member['by_opponent']
        weights = stage['screening']['policy']['policy']
        for family in weights['family_weights']:
            names = [n for n, o in opponents.items() if o['family'] == family]
            if names and all(opponents[n]['value'] is not None for n in names):
                families[family] = sum(opponents[n]['value'] * weights['opponent_weights'][n]
                    for n in names) / sum(weights['opponent_weights'][n] for n in names)
        for color in ('black', 'white'):
            if opponents and all(o['by_color'][color]['value'] is not None for o in opponents.values()):
                by_family = {f: sum(opponents[n]['by_color'][color]['value'] * weights['opponent_weights'][n]
                    for n in opponents if opponents[n]['family'] == f) /
                    sum(weights['opponent_weights'][n] for n in opponents if opponents[n]['family'] == f)
                    for f in families}
                if by_family:
                    colors[color] = sum(v * weights['family_weights'][f] for f, v in by_family.items()) / sum(weights['family_weights'][f] for f in by_family)
        member.update(by_family=families, by_color=colors,
            worst_matchup=min((o['value'] for o in opponents.values() if o['value'] is not None), default=None))
    for identity, member in report['candidates'].items():
        regressions = []
        for metric, margin in (('by_family', 'max_family_regression'), ('by_color', 'max_color_regression')):
            for name, value in member[metric].items():
                baseline = incumbent[metric].get(name)
                if baseline is not None and value < baseline - p[margin]:
                    regressions.append({'metric': metric, 'name': name, 'candidate': value, 'incumbent': baseline})
        for name, matchup in member['by_opponent'].items():
            baseline = incumbent['by_opponent'].get(name, {}).get('value')
            if baseline is not None and matchup['value'] is not None and matchup['value'] < baseline - p['max_matchup_regression']:
                regressions.append({'metric': 'matchup', 'name': name, 'candidate': matchup['value'], 'incumbent': baseline})
        member['regressions'] = regressions
        if regressions and member['status'] == 'advance':
            member['status'] = 'fail'
            member['reasons'].append('league_regression')
    report['history_coverage'] = {e['entry']['identity']: {
        'due': e['entry']['identity'] in stage['selected_history'],
        'complete': all(e['entry']['logical_id'] in m['by_opponent'] and
            all(c['denominator'] == c['counts']['planned'] for c in m['by_opponent'][e['entry']['logical_id']]['by_color'].values())
            for m in report['candidates'].values()) if e['entry']['identity'] in stage['selected_history'] else None}
        for e in stage['history']['champions']}
    report['historical_gaps'] = []
    for previous in stage['prior_rounds']:
        prior_report = assess_round(previous['stage'], previous['raw'])
        report['historical_gaps'].extend(prior_report['historical_gaps'])
        report['historical_gaps'].extend({'round_index': prior_report['round_index'], 'identity': key}
            for key, coverage in prior_report['history_coverage'].items() if coverage['due'] and not coverage['complete'])
    report['historical_gaps'] = list({canonical(g): g for g in report['historical_gaps']}.values())
    if report['historical_gaps']:
        for member in report['candidates'].values():
            if member['status'] == 'advance':
                member['status'] = 'inconclusive'
                member['reasons'].append('historical_schedule_incomplete')
    report['advanced'] = sorted(i for i, m in report['candidates'].items() if m['status'] == 'advance')
    report['limitations'] = ('Training round only; fresh confirmation, validation and official-clock checks remain required. '
        'Related families and external acknowledgments are retained; no class rank or hidden TA claim.')
    return report


def load_results(output: Path) -> dict[str, Any]:
    record = json.loads((output / 'league-results.json').read_text(encoding='utf-8'))
    data = record['data']
    if record['identity'] != digest(data) or data['stage'] != load(output):
        raise ValueError('Saved league evidence identity mismatch.')
    assess_round(data['stage'], data['raw'])
    return data


def run(output: Path, *, max_jobs_per_plan: int | None = None) -> dict[str, Any]:
    """Resume the fixed broader round with Phase 4 durable attempts."""
    stage = load(output)
    raw = {}
    with owner(output):
        previous = load_results(output)['raw'] if (output / 'league-results.json').exists() else {}
        plans = [ExperimentPlan.from_record(r) for m in stage['screening']['members'] for r in m['plans']]
        # Reject incompatible or lost authoritative evidence before ANY dispatch.
        for plan in plans:
            verify_versions(plan)
            directory = output / plan.identity
            if plan.identity in previous and not (directory / 'checkpoint.json').exists():
                raise ValueError('Missing authoritative league checkpoint.')
            if (directory / 'checkpoint.json').exists():
                with owner(directory):
                    Checkpoint(plan, directory, True, stage['screening']['policy']['policy']['infrastructure_retries'])
        for member in stage['screening']['members']:
            for record in member['plans']:
                plan = ExperimentPlan.from_record(record)
                directory = output / plan.identity
                raw[plan.identity] = run_experiment(plan, output=directory, resume=directory.exists(),
                    max_jobs=max_jobs_per_plan,
                    infrastructure_retries=stage['screening']['policy']['policy']['infrastructure_retries'])
        report = assess_round(stage, raw)
        data = {'stage': stage, 'raw': raw}
        atomic_json(output / 'league-results.json', {'identity': digest(data), 'data': data})
        atomic_json(output / 'league-report.json', report)
    return report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Previously prepared frozen league round')
    parser.add_argument('--max-jobs-per-plan', type=int, required=True,
                        help='Bound dispatched attempts per candidate/opponent plan in this invocation')
    args = parser.parse_args()
    report = run(args.output, max_jobs_per_plan=args.max_jobs_per_plan)
    print(canonical({'stage_identity': report['stage_identity'], 'advanced': report['advanced'],
                     'retained_incumbent': report['retained_incumbent'], 'promotion': False}))


if __name__ == '__main__':
    main()
