# AI-written by OpenAI Codex, for issue #37.
"""Saved, bounded parameter proposals on a frozen implemented engine basis."""
from dataclasses import dataclass
import io
import json
from math import isfinite
from pathlib import Path
import random
import tarfile
from tempfile import TemporaryDirectory
from typing import Any

from offline.experiments import save_new_json
from offline.measurement import search_settings
from offline.registry import Entry, ROOT, canonical, checkpoint_archive, digest, source_snapshot
from omok.evaluation import EvaluationConfig, FAMILY_FEATURES
from omok.player import TimePolicy
from omok.search import EVALUATION_LIMIT, WIN_SCORE

FORMAT = 'omok-proposals-v1'
POLICY_VERSION = 'coherent-mutation-v1'
# Conservative local screening domains: table entry count is bounded, not a byte guarantee.
SEARCH_DOMAINS = {
    'max_depth': ('integer', 1, 16, 8, 1),
    'max_nodes': ('integer', 100, 100000, 10000, 2000),
    'candidate_radius': ('integer', 1, 4, 2, 1),
    'candidate_cap': ('integer', 4, 64, 24, 4),
    'table_capacity': ('integer', 0, 8192, 4096, 512),
    'max_time_ms': ('real', 5.0, 250.0, 100.0, 10.0),
    'return_margin_ms': ('real', 2.0, 20.0, 2.0, 1.0),
    'reserve_fraction': ('real', 0.25, 0.75, 0.5, 0.05),
    'turn_fraction': ('real', 0.02, 0.2, 0.1, 0.02),
    'soft_fraction': ('real', 0.5, 0.95, 0.8, 0.05),
}
TIME_NAMES = set(TimePolicy.__dataclass_fields__)
SEARCH_GROUPS = {
    'candidates': ('candidate_radius', 'candidate_cap'),
    'resources': ('max_depth', 'max_nodes', 'table_capacity'),
    'time': tuple(sorted(TIME_NAMES)),
}


def schema(evaluation: EvaluationConfig) -> dict[str, Any]:
    defaults = EvaluationConfig(feature_version=evaluation.feature_version).coefficients()
    genes: dict[str, Any] = {}
    groups: dict[str, list[str]] = {}
    for family in evaluation.enabled_families():
        groups[family] = []
        for name in FAMILY_FEATURES[family]:
            path = 'evaluation.coefficients.' + name
            groups[family].append(path)
            genes[path] = {'type': 'integer', 'domain': [-4000, 4000],
                'default': defaults[name], 'transformation': 'identity',
                'step': max(1, abs(defaults[name]) // 10)}
    for group, names in SEARCH_GROUPS.items():
        groups[group] = []
        for name in names:
            kind, low, high, default, step = SEARCH_DOMAINS[name]
            path = 'settings.' + ('time_policy.' if name in TIME_NAMES else '') + name
            groups[group].append(path)
            genes[path] = {'type': kind, 'domain': [low, high], 'default': default,
                           'transformation': 'identity', 'step': step}
    return {'genes': genes, 'groups': groups,
            'feature_version': evaluation.feature_version,
            'enabled_families': evaluation.enabled_families()}


def validate_configuration(value: dict[str, Any]) -> dict[str, Any]:
    """Validate actual JSON values, never cast a malformed integer or clamp silently."""
    canonical(value)  # Also rejects NaN/Infinity anywhere in the serialized proposal.
    if type(value) is not dict or set(value) != {'evaluation', 'settings'}:
        raise ValueError('Configuration requires evaluation and settings only.')
    evaluation = EvaluationConfig.from_json(canonical(value['evaluation']))
    if not 0 < EVALUATION_LIMIT < WIN_SCORE:
        raise ValueError('Heuristic bounds must preserve terminal dominance.')
    settings = value['settings']
    expected = set(search_settings(depth=8, nodes=10000, radius=2, cap=24, policy=TimePolicy()))
    if type(settings) is not dict or set(settings) != expected:
        raise ValueError('Unknown or missing implemented search setting.')
    if (settings['full_width'] is not False or settings['extensions'] != 'none'
            or settings['ordering'] != 'omok.tactics.static_rank'):
        raise ValueError('Tactical protection and implemented ordering/extension semantics are frozen.')
    time = settings['time_policy']
    if type(time) is not dict or set(time) != TIME_NAMES:
        raise ValueError('Unknown or missing time setting.')
    for name, (kind, low, high, _, _) in SEARCH_DOMAINS.items():
        actual = time[name] if name in TIME_NAMES else settings[name]
        if (type(actual) is not int if kind == 'integer' else type(actual) not in (int, float)):
            raise ValueError('Invalid serialized type for ' + name)
        if not low <= actual <= high or not isfinite(actual):
            raise ValueError('Outside finite resource/time domain: ' + name)
    TimePolicy(**time)
    # All coefficients are black-centric differences in the frozen evaluator.
    # Side-to-move conversion, clipping and terminal scores remain engine-owned.
    return {'evaluation': json.loads(evaluation.canonical_json()), 'settings': json.loads(canonical(settings))}


def resolve_entry(entry: Entry) -> dict[str, Any]:
    """Resolve the supported IterativePlayer registry options, including retained code."""
    data = entry.data
    loader, options = data['loader'], data['options']
    if (loader['module'], loader['factory']) != ('omok.player', 'IterativePlayer'):
        raise ValueError('Proposals require a registered IterativePlayer basis.')
    if data['availability'] != 'ready':
        raise ValueError('Parent must be ready.')
    # Parameter tuning is supported only against the verified, unchanged implementation.
    current = source_snapshot(ROOT, ('omok',))
    if {k: v for k, v in data['sources'].items() if k.startswith('omok/')} != current:
        raise ValueError('Parent engine differs from the frozen supported implementation.')
    if set(options) == {'candidate_configuration'}:
        return validate_configuration(options['candidate_configuration'])
    if set(options) - {'max_depth', 'max_nodes', 'evaluation_path'}:
        raise ValueError('Unsupported parent options; no guessed or omitted settings.')
    evaluation = EvaluationConfig()
    if 'evaluation_path' in options:
        name = options['evaluation_path']
        if loader['kind'] == 'checkpoint':
            with TemporaryDirectory() as directory:
                root = Path(directory)
                with tarfile.open(fileobj=io.BytesIO(checkpoint_archive(loader['commit'], tuple(loader['paths'])))) as stream:
                    stream.extractall(root, filter='data')
                if source_snapshot(root, tuple(data['source_paths'])) != data['sources']:
                    raise ValueError('Parent source identity changed.')
                evaluation = EvaluationConfig.load(root / name)
        elif loader['kind'] == 'local':
            root = ROOT if loader['root'] == '.' else Path(loader['root'])
            if source_snapshot(root, tuple(data['source_paths'])) != data['sources']:
                raise ValueError('Parent source identity changed.')
            evaluation = EvaluationConfig.load(root / name)
        else:
            raise ValueError('Unsupported parent loader.')
    settings = search_settings(depth=options.get('max_depth', 8), nodes=options.get('max_nodes', 10000),
                               radius=2, cap=24, policy=TimePolicy())
    return validate_configuration({'evaluation': json.loads(evaluation.canonical_json()), 'settings': settings})


def genotype_identity(entry: Entry, configuration: dict[str, Any]) -> str:
    data = entry.data
    # Names, ancestry and display variants do not create extra statistical identities.
    return digest({'configuration': validate_configuration(configuration),
                   'sources': data['sources'], 'runtime': data['runtime'],
                   'dependencies': data['dependencies']})


@dataclass(frozen=True)
class ProposalPolicy:
    definition: str

    def __post_init__(self) -> None:
        data = json.loads(self.definition)
        expected = {'version', 'schema', 'engine_sources', 'adapter_sources', 'runtime', 'dependencies', 'batch', 'groups', 'scales', 'diversity_probability',
                    'max_attempts', 'repair', 'constraints'}
        if type(data) is not dict or set(data) != expected or data['version'] != POLICY_VERSION:
            raise ValueError('Unsupported proposal policy.')
        spec = data['schema']
        evaluation = EvaluationConfig(feature_version=spec['feature_version'], **{
            family + '_enabled': family in spec['enabled_families']
            for family in EvaluationConfig(feature_version=spec['feature_version']).enabled_families()})
        if spec != schema(evaluation):
            raise ValueError('Gene schema cannot add unsupported mechanisms or alter domains.')
        eligible = set(evaluation.enabled_families()) if data['batch'] == 'evaluation' else set(SEARCH_GROUPS)
        if data['batch'] not in ('evaluation', 'search-time'):
            raise ValueError('Unknown batch kind.')
        groups = data['groups']
        if (type(groups) is not list or not groups or any(type(g) is not str or g not in eligible for g in groups)
                or len(set(groups)) != len(groups) or set(data['scales']) != set(groups)):
            raise ValueError('Batch requires small coherent eligible groups and their scales.')
        for scale in data['scales'].values():
            if type(scale) not in (int, float) or not 0 < scale <= 10 or not isfinite(scale):
                raise ValueError('Mutation scale must be finite in (0, 10].')
        probability = data['diversity_probability']
        if type(probability) not in (int, float) or not 0 <= probability <= 1 or not isfinite(probability):
            raise ValueError('Invalid diversity probability.')
        if type(data['max_attempts']) is not int or not 1 <= data['max_attempts'] <= 100:
            raise ValueError('Invalid bounded retry count.')
        if data['repair'] not in ('reject', 'clip-domain') or data['constraints'] != constraints():
            raise ValueError('Unsupported repair or weakened invariant.')
        object.__setattr__(self, 'definition', canonical(data))

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self.definition)

    @property
    def identity(self) -> str:
        return digest(self.data)

    def save(self, path: Path) -> None:
        save_new_json(path, {'identity': self.identity, 'policy': self.data})

    @classmethod
    def load(cls, path: Path) -> 'ProposalPolicy':
        record = json.loads(path.read_text(encoding='utf-8'))
        policy = cls(canonical(record['policy']))
        if record['identity'] != policy.identity:
            raise ValueError('Saved proposal policy identity mismatch.')
        return policy

    @classmethod
    def for_parent(cls, parent: Entry, *, batch: str, groups: list[str],
                   scales: dict[str, float] | None = None, diversity_probability: float = 0.1,
                   max_attempts: int = 12, repair: str = 'reject') -> 'ProposalPolicy':
        config = resolve_entry(parent)
        return cls(canonical({'version': POLICY_VERSION,
            'engine_sources': parent.data['sources'], 'runtime': parent.data['runtime'],
            'adapter_sources': source_snapshot(ROOT, ('offline',)),
            'dependencies': parent.data['dependencies'],
            'schema': schema(EvaluationConfig.from_json(canonical(config['evaluation']))),
            'batch': batch, 'groups': groups, 'scales': scales if scales is not None else {g: 1.0 for g in groups},
            'diversity_probability': diversity_probability, 'max_attempts': max_attempts,
            'repair': repair, 'constraints': constraints()}))


def constraints() -> dict[str, Any]:
    return {'perspective': 'black-centric feature differences; negamax converts once',
            'evaluation_limit': EVALUATION_LIMIT, 'terminal_score': WIN_SCORE,
            'memory': 'table_capacity <= 8192 entries; no byte-memory guarantee',
            'semantics': 'feature version/families fixed; mandatory tactics, rules, total clocks, outcome accounting and pools engine-owned',
            'mutation': 'one coherent group; uniform integer steps; additive real steps rounded to 6 decimals',
            'diversity': 'uniform actual values within the selected group domains',
            'deduplication': 'exact resolved values plus engine source/runtime/dependencies; no normalization',
            'retry': 'at most max_attempts per requested slot; duplicates and invalid attempts consume retries'}


def resolve_mutation_target(value: dict[str, Any], path: str) -> tuple[dict[str, Any], str]:
    parts = path.split('.')
    target = value
    for name in parts[:-1]:
        target = target[name]
    return target, parts[-1]


def generate(policy_path: Path, parents: list[Entry], *, seed: int, count: int,
             output: Path) -> dict[str, Any]:
    """Read a policy saved before generation; save immutable candidates and every attempt."""
    policy = ProposalPolicy.load(policy_path)
    if type(seed) is not int or type(count) is not int or not 1 <= count <= 1000 or not parents:
        raise ValueError('Integer seed, 1..1000 slots, and recorded parents are required.')
    data = policy.data
    if source_snapshot(ROOT, ('offline',)) != data['adapter_sources']:
        raise ValueError('Registry adapter differs from saved policy; establish a new policy.')
    ordered = sorted({p.identity: p for p in parents}.values(), key=lambda p: p.identity)
    for parent in ordered:
        basis = parent.data
        if (basis['sources'] != data['engine_sources'] or basis['runtime'] != data['runtime']
                or basis['dependencies'] != data['dependencies']):
            raise ValueError('Parent source basis/runtime/dependencies differs from saved policy.')
    resolved = {p.identity: resolve_entry(p) for p in ordered}
    for value in resolved.values():
        if schema(EvaluationConfig.from_json(canonical(value['evaluation']))) != data['schema']:
            raise ValueError('Parents must share the saved feature semantics.')
    output.mkdir(parents=True, exist_ok=False)
    save_new_json(output / 'policy.json', {'identity': policy.identity, 'policy': data})
    parent_records = [{'entry': p.record(), 'configuration': resolved[p.identity]} for p in ordered]
    save_new_json(output / 'parents.json', {'parents': parent_records})
    rng = random.Random(seed)
    initial_state = rng.getstate()
    known: dict[str, dict[str, Any]] = {}
    for parent in ordered:
        key = genotype_identity(parent, resolved[parent.identity])
        record = known.setdefault(key, {'genotype': key, 'entry': parent.record(), 'parents': []})
        record['parents'].append(parent.identity)
    candidates: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for slot in range(count):
        for retry in range(data['max_attempts']):
            proposal_seed = rng.getrandbits(128)
            proposal_rng = random.Random(proposal_seed)
            parent = proposal_rng.choice(ordered)
            group = proposal_rng.choice(data['groups'])
            diversity = proposal_rng.random() < data['diversity_probability']
            proposal = json.loads(canonical(resolved[parent.identity]))
            repairs = []
            changes = {}
            for path in data['schema']['groups'][group]:
                gene = data['schema']['genes'][path]
                target, name = resolve_mutation_target(proposal, path)
                before = target[name]
                low, high = gene['domain']
                if gene['type'] == 'integer':
                    step = max(1, round(gene['step'] * data['scales'][group]))
                    proposed = proposal_rng.randint(low, high) if diversity else before + proposal_rng.randint(-step, step)
                else:
                    step = gene['step'] * data['scales'][group]
                    proposed = round(proposal_rng.uniform(low, high) if diversity else before + proposal_rng.uniform(-step, step), 6)
                actual = proposed
                if data['repair'] == 'clip-domain' and not low <= proposed <= high:
                    actual = max(low, min(high, proposed))
                    repairs.append({'path': path, 'proposed': proposed, 'actual': actual, 'rule': 'clip-domain'})
                target[name] = actual
                if before != actual:
                    changes[path] = {'before': before, 'actual': actual}
            attempt: dict[str, Any] = {'slot': slot, 'retry': retry, 'parent': parent.identity,
                'proposal_seed': proposal_seed, 'rng_state': digest(proposal_rng.getstate()),
                'group': group, 'diversity': diversity, 'changes': changes, 'repairs': repairs,
                'proposal': proposal, 'status': None, 'reason': None, 'genotype': None}
            attempts.append(attempt)
            try:
                actual = validate_configuration(proposal)
            except (ValueError, TypeError) as error:
                attempt.update(status='rejected', reason=str(error))
                continue
            key = genotype_identity(parent, actual)
            attempt['genotype'] = key
            if key in known:
                ancestry = known[key]['parents']
                if parent.identity not in ancestry:
                    ancestry.append(parent.identity)
                    ancestry.sort()
                attempt.update(status='duplicate', reason='exact genotype already recorded')
                continue
            entry_data = parent.data
            entry_data.update(logical_id='candidate-' + key, variant='proposal-' + key,
                              options={'candidate_configuration': actual})
            # Keep parent source/loader identity, use the current verified execution adapter.
            entry_data['adapter_sources'] = data['adapter_sources']
            candidate = {'genotype': key, 'entry': Entry(canonical(entry_data)).record(), 'parents': [parent.identity]}
            known[key] = candidate
            candidates.append(candidate)
            attempt['status'] = 'accepted'
            break
    result = json.loads(canonical({'format': FORMAT, 'policy_identity': policy.identity,
        'policy': data, 'parents': parent_records, 'seed': seed,
        'initial_rng_state': initial_state, 'final_rng_state': rng.getstate(),
        'requested_slots': count, 'candidates': candidates, 'attempts': attempts,
        'ancestry': {key: record['parents'] for key, record in sorted(known.items())},
        'exhausted_slots': [slot for slot in range(count) if not any(a['slot'] == slot and a['status'] == 'accepted' for a in attempts)]}))
    save_new_json(output / 'proposals.json', result)
    return result


def main() -> None:
    """Separate policy saving from generation so choices exist before any RNG draws."""
    import argparse
    from offline.registry import default_catalog
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='command', required=True)
    policy_parser = subcommands.add_parser('policy')
    policy_parser.add_argument('--parent', type=Path, help='JSON Entry record; default: retained phase3-material')
    policy_parser.add_argument('--output', type=Path, required=True)
    policy_parser.add_argument('--batch', choices=('evaluation', 'search-time'), required=True)
    policy_parser.add_argument('--groups', nargs='+', required=True)
    policy_parser.add_argument('--diversity-probability', type=float, default=0.1)
    policy_parser.add_argument('--max-attempts', type=int, default=12)
    policy_parser.add_argument('--repair', choices=('reject', 'clip-domain'), default='reject')
    proposal_parser = subcommands.add_parser('generate')
    proposal_parser.add_argument('--policy', type=Path, required=True)
    proposal_parser.add_argument('--parent', action='append', type=Path)
    proposal_parser.add_argument('--seed', type=int, required=True)
    proposal_parser.add_argument('--count', type=int, required=True)
    proposal_parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def read_parent(path: Path | None) -> Entry:
        return Entry.from_record(json.loads(path.read_text(encoding='utf-8'))) if path else default_catalog()[0]['phase3-material']
    if args.command == 'policy':
        policy = ProposalPolicy.for_parent(read_parent(args.parent), batch=args.batch, groups=args.groups,
            diversity_probability=args.diversity_probability, max_attempts=args.max_attempts, repair=args.repair)
        policy.save(args.output)
        print(canonical({'policy_identity': policy.identity, 'path': str(args.output)}))
    else:
        batch = generate(args.policy, [read_parent(path) for path in (args.parent or [None])],
                         seed=args.seed, count=args.count, output=args.output)
        print(canonical({'accepted': len(batch['candidates']), 'attempts': len(batch['attempts']),
                        'exhausted_slots': batch['exhausted_slots'], 'path': str(args.output)}))


if __name__ == '__main__':
    main()
