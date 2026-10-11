# AI-written by OpenAI Codex, for issue #43.
"""Single-checkpoint champion transactions, exact exports and historical rollback."""
from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

from offline.batches import atomic_json, owner
from offline.confirmation import assess_record as assess_confirmation
from offline.league import champion_bundle, validate_history, with_adapter
from offline.promotion import load as load_checks, assess_record_checks
from offline.registry import Entry, canonical, digest
from offline.supervised import PlayerSpec

FORMAT = 'omok-champion-store-v1'
EXPORT = 'omok-champion-export-v1'
SELECTION = 'complete declared check cohort; maximum fresh-confirmation sensitivity lower bound; ascending identity breaks ties'


def validate_suite(suite: dict[str, Any]) -> None:
    if (set(suite) != {'identity', 'sources'} or not suite['sources']
            or suite['identity'] != digest(suite['sources'])
            or any(not isinstance(value, str) or len(value) != 64
                   or any(c not in '0123456789abcdef' for c in value) for value in suite['sources'].values())):
        raise ValueError('Identify the fixed tactical suite by its source hashes.')


def read_envelope(path: Path) -> dict[str, Any]:
    envelope = json.loads(path.read_text(encoding='utf-8'))
    if envelope['identity'] != digest(envelope['data']):
        raise ValueError('Champion/evidence artifact identity mismatch.')
    return envelope['data']


def commit_evidence(checks: Path, raw: dict[str, dict[str, Any]], *,
                    interrupt: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Commit a complete eligibility evidence snapshot before any champion decision."""
    with owner(checks):
        record = load_checks(checks)
        report = assess_record_checks(record, raw)
        data = {'check_identity': digest(record), 'raw': raw}
        path = checks / 'eligibility-results.json'
        if path.exists():
            if read_envelope(path) != data:
                raise ValueError('Committed evidence differs; prepare a new eligibility check.')
        else:
            if interrupt:
                interrupt('before_evidence_commit')
            atomic_json(path, {'identity': digest(data), 'data': data})
            if interrupt:
                interrupt('after_evidence_commit')
        return report


def validate_version(version: dict[str, Any]) -> None:
    validate_history({'champions': [version['bundle']]})
    if version['entry_identity'] != version['bundle']['entry']['identity']:
        raise ValueError('Champion version identity mismatch.')
    if not version['reason'] or not isinstance(version['context'], dict):
        raise ValueError('Champion requires decision reason and saved context.')
    validate_suite(version['context'].get('tactical_suite', {}))


def load_export(path: Path) -> dict[str, Any]:
    data = read_envelope(path)
    if data['format'] != EXPORT or data['version_identity'] != digest(data['version']):
        raise ValueError('Champion export version mismatch.')
    validate_version(data['version'])
    reference = data['version']['context'].get('evidence_identity')
    if reference is not None:
        retained = data['evidence']
        if (digest(retained['data']) != reference or retained['data']['check_identity'] != digest(retained['checks'])
                or data['decision']['request']['evidence'] != reference):
            raise ValueError('Champion export evidence mismatch.')
    return data


def exported_spec(path: Path, *, seed: int = 0) -> PlayerSpec:
    """Pin the artifact identity; each supervised worker loads a fresh isolated tree."""
    data = load_export(path)
    return PlayerSpec('offline.champions_worker', 'create',
        {'artifact': str(path.resolve()), 'identity': digest(data), 'seed': seed}, seed)


class ChampionStore:
    def __init__(self, output: Path):
        self.output = output
        self.path = output / 'champions.json'

    def _commit(self, data: dict[str, Any], interrupt: Callable[[str], None] | None = None) -> None:
        if interrupt:
            interrupt('before_champion_commit')
        atomic_json(self.path, {'identity': digest(data), 'data': data})
        if interrupt:
            interrupt('after_champion_commit')

    def initialize(self, incumbent: Entry, *, context: dict[str, Any], reason: str,
                   history: dict[str, Any] | None = None, history_period: int = 1,
                   history_slots: dict[str, int] | None = None) -> dict[str, Any]:
        if not context or not reason or type(history_period) is not int or history_period < 1:
            raise ValueError('Declare baseline provenance, reason and regression period.')
        validate_suite(context.get('tactical_suite', {}))
        archive = history or {'champions': []}
        previous = validate_history(archive)
        slots = history_slots if history_slots is not None else {e.identity: 0 for e in previous}
        if (set(slots) != {e.identity for e in previous} or incumbent.identity in slots
                or any(type(s) is not int or not 0 <= s < history_period for s in slots.values())):
            raise ValueError('Schedule each historical champion exactly once.')
        self.output.mkdir(parents=True, exist_ok=True)
        with owner(self.output):
            if self.path.exists():
                raise FileExistsError(self.path)
            versions = {}
            for original in archive['champions'] + [champion_bundle(incumbent)]:
                bundle = with_adapter(original)
                version = {'entry_identity': bundle['entry']['identity'], 'parent': None,
                    'bundle': bundle, 'context': context, 'reason': reason}
                versions[digest(version)] = version
            current = next(k for k, v in versions.items() if v['entry_identity'] == incumbent.identity)
            data = {'format': FORMAT, 'selection': SELECTION, 'current': current, 'versions': versions,
                'history_period': history_period, 'history_slots': slots, 'transactions': {}, 'evidence': {}}
            self._commit(data)
        return self.load()

    def load(self) -> dict[str, Any]:
        data = read_envelope(self.path)
        if data['format'] != FORMAT or data['selection'] != SELECTION or data['current'] not in data['versions']:
            raise ValueError('Invalid champion checkpoint.')
        for identity, version in data['versions'].items():
            if identity != digest(version) or (version['parent'] is not None and version['parent'] not in data['versions']):
                raise ValueError('Corrupt champion version/parent.')
            validate_version(version)
            reference = version['context'].get('evidence_identity')
            if reference is not None and reference not in data['evidence']:
                raise ValueError('Champion evidence is missing.')
        entries = {v['entry_identity'] for v in data['versions'].values()}
        if (not set(data['history_slots']) <= entries or type(data['history_period']) is not int
                or data['history_period'] < 1 or any(type(s) is not int or not 0 <= s < data['history_period']
                                                  for s in data['history_slots'].values())):
            raise ValueError('Invalid retained historical rotation.')
        for identity, transaction in data['transactions'].items():
            if identity != digest(transaction['request']) or transaction['current'] not in data['versions']:
                raise ValueError('Corrupt champion transaction.')
        return data

    def promote(self, checks: Path, *, interrupt: Callable[[str], None] | None = None) -> dict[str, Any]:
        with owner(self.output):
            data = self.load()
            record = load_checks(checks)
            evidence = read_envelope(checks / 'eligibility-results.json')
            if evidence['check_identity'] != digest(record):
                raise ValueError('Committed evidence belongs to another eligibility check.')
            request = {'kind': 'promotion', 'checks': digest(record), 'evidence': digest(evidence)}
            transaction_id = digest(request)
            if transaction_id in data['transactions']:
                return data['transactions'][transaction_id]
            incumbent = data['versions'][data['current']]['entry_identity']
            if record['validation']['incumbent'] != incumbent:
                raise ValueError('Stale eligibility incumbent; remeasure before promotion.')
            report = assess_record_checks(record, evidence['raw'])
            suite = data['versions'][data['current']]['context']['tactical_suite']
            missing_suite = {m['entry']['identity'] for m in record['validation']['members']
                if not any(g['check'] == 'mandatory_tactic' and g.get('suite_identity') == suite['identity'] for g in m['gates'])}
            for identity, candidate in report['candidates'].items():
                if identity in missing_suite or incumbent in missing_suite:
                    candidate['status'] = 'reject' if candidate['status'] == 'reject' else 'inconclusive'
                    candidate['reasons'] = sorted(set(candidate['reasons'] + ['tactical_suite_identity_missing_or_changed']))
            complete = all({r['game_id'] for r in evidence['raw'].get(p['identity'], {}).get('results', [])}
                           == {j['game_id'] for j in p['jobs']}
                           for stage in ('validation', 'official') for m in record[stage]['members'] for p in m['plans'])
            source = record['confirmation']
            history_context = source['selection_context'] if source is not None else None
            incoming = history_context['history'] if history_context is not None else {'champions': []}
            incoming_entries = validate_history(incoming)
            declared = {e.identity for e in incoming_entries}
            known = set(data['history_slots']) - {incumbent}
            blockers = [] if complete else ['promotion_cohort_incomplete']
            if known - declared:
                blockers.append('retained_historical_coverage_missing')
            rotation = history_context['policy'] if history_context is not None else None
            if rotation is not None and (
                    (data['history_slots'] and data['history_period'] != rotation['history_period'])
                    or any(data['history_slots'][i] != rotation['history_slots'].get(i) for i in known & declared)):
                blockers.append('retained_historical_schedule_changed')
            for identity, candidate in report['candidates'].items():
                if blockers and identity != incumbent:
                    candidate['status'] = 'reject' if candidate['status'] == 'reject' else 'inconclusive'
                    candidate['reasons'] = sorted(set(candidate['reasons'] + blockers))
            report['cohort_complete'] = complete
            report['eligible'] = sorted(i for i, c in report['candidates'].items() if c['status'] == 'eligible')
            data['evidence'][digest(evidence)] = {'checks': record, 'data': evidence}
            candidates = report['eligible']
            winner = None
            if candidates:
                confirmed = assess_confirmation(record['confirmation'], record['confirmation_raw'])
                winner = min(candidates, key=lambda i: (-confirmed['candidates'][i]['sensitivity_range'][0], i))
            previous = data['current']
            if winner is not None:
                assert rotation is not None
                if not data['history_slots']:
                    data['history_period'] = rotation['history_period']
                retained = {v['entry_identity'] for v in data['versions'].values()}
                for original in incoming['champions']:
                    historical = original['entry']['identity']
                    if historical not in retained:
                        version = {'entry_identity': historical, 'parent': None, 'bundle': with_adapter(original),
                            'context': {'tactical_suite': suite, 'check_identity': digest(record),
                                'limitations': 'Imported unchanged historical source/configuration from the saved run archive; '
                                    'earlier promotion metadata was not supplied. Suite declaration belongs to this run.'},
                            'reason': 'Retain historical opponent and its predeclared rotation from committed eligibility evidence'}
                        data['versions'][digest(version)] = version
                    data['history_slots'].setdefault(historical, rotation['history_slots'][historical])
                entry = next(Entry.from_record(m['entry']) for m in record['validation']['members']
                             if m['entry']['identity'] == winner)
                version = {'entry_identity': winner, 'parent': previous, 'bundle': champion_bundle(entry),
                    'context': {'evidence_identity': digest(evidence), 'decision_identity': transaction_id,
                        'run_identity': digest(record['confirmation']),
                        'pool_identity': record['validation']['pool_snapshot']['identity'],
                        'tactical_suite': suite,
                        'policy_identity': report['policy_identity'], 'limitations': report['limitations']},
                    'reason': 'Eligible under saved policy; selected by ' + SELECTION}
                current = digest(version)
                data['versions'][current] = version
                data['history_slots'].setdefault(incumbent, len(data['history_slots']) % data['history_period'])
                data['current'] = current
            transaction = {'request': request, 'previous': previous, 'current': data['current'],
                'winner': winner, 'reason': 'promote eligible candidate' if winner else 'retain incumbent: no eligible candidate',
                'report': report}
            data['transactions'][transaction_id] = transaction
            self._commit(data, interrupt)
            return transaction

    def rollback(self, version_identity: str, *, reason: str,
                 interrupt: Callable[[str], None] | None = None) -> dict[str, Any]:
        if not reason:
            raise ValueError('Record a rollback reason.')
        with owner(self.output):
            data = self.load()
            if version_identity not in data['versions']:
                raise ValueError('Rollback requires a known archived version.')
            if version_identity == data['current']:
                return data
            previous = data['current']
            request = {'kind': 'rollback', 'previous': previous, 'target': version_identity, 'reason': reason}
            data['history_slots'].setdefault(data['versions'][previous]['entry_identity'],
                                            len(data['history_slots']) % data['history_period'])
            data['current'] = version_identity
            data['transactions'][digest(request)] = {'request': request, 'previous': previous,
                'current': version_identity, 'reason': reason}
            self._commit(data, interrupt)
            return data

    def history(self, round_index: int | None = None) -> dict[str, Any]:
        data = self.load()
        current = data['versions'][data['current']]['entry_identity']
        if round_index is not None and (type(round_index) is not int or round_index < 0):
            raise ValueError('Round index must be nonnegative.')
        versions = {v['entry_identity']: v for v in data['versions'].values()}
        slots = {i: s for i, s in data['history_slots'].items() if i != current}
        selected = [i for i, slot in slots.items() if round_index is None or slot == round_index % data['history_period']]
        return {'champions': [versions[i]['bundle'] for i in sorted(selected)],
                'history_period': data['history_period'], 'history_slots': slots}

    def export(self, path: Path, *, version_identity: str | None = None) -> dict[str, Any]:
        data = self.load()
        identity = version_identity or data['current']
        if identity not in data['versions']:
            raise ValueError('Export requires a known champion version.')
        version = data['versions'][identity]
        artifact = {'format': EXPORT, 'version_identity': identity, 'version': version,
            'evidence': data['evidence'].get(version['context'].get('evidence_identity')),
            'decision': data['transactions'].get(version['context'].get('decision_identity'))}
        path.parent.mkdir(parents=True, exist_ok=True)
        with owner(path.parent):
            if path.exists():
                if load_export(path) != artifact:
                    raise FileExistsError('Export destination contains a different champion.')
            else:
                atomic_json(path, {'identity': digest(artifact), 'data': artifact})
        return artifact


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('initialize')
    init.add_argument('--incumbent', type=Path, required=True, help='Saved registry Entry record')
    init.add_argument('--context', type=Path, required=True, help='Baseline version/gate/run provenance JSON')
    init.add_argument('--reason', required=True)
    init.add_argument('--history', type=Path)
    init.add_argument('--history-period', type=int, default=1)
    init.add_argument('--history-slots', type=Path)
    promote = sub.add_parser('promote')
    promote.add_argument('--checks', type=Path, required=True)
    export = sub.add_parser('export')
    export.add_argument('--output', type=Path, required=True)
    export.add_argument('--version')
    rollback = sub.add_parser('rollback')
    rollback.add_argument('--version', required=True)
    rollback.add_argument('--reason', required=True)
    history = sub.add_parser('history')
    history.add_argument('--round', type=int)
    sub.add_parser('show')
    args = parser.parse_args()
    store = ChampionStore(args.store)

    def read(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding='utf-8'))

    if args.command == 'initialize':
        result = store.initialize(Entry.from_record(read(args.incumbent)), context=read(args.context), reason=args.reason,
            history=read(args.history) if args.history else None, history_period=args.history_period,
            history_slots=read(args.history_slots) if args.history_slots else None)
    elif args.command == 'promote':
        result = store.promote(args.checks)
    elif args.command == 'export':
        result = store.export(args.output, version_identity=args.version)
    elif args.command == 'rollback':
        result = store.rollback(args.version, reason=args.reason)
    elif args.command == 'history':
        result = store.history(args.round)
    else:
        result = store.load()
    print(canonical(result))


if __name__ == '__main__':
    main()
