# AI-written by OpenAI Codex, for issue #43.
"""Retain controlled promotion/rollback evidence and real archived-player reloads."""
import argparse
import gzip
import json
from pathlib import Path
from time import monotonic
from typing import Any

from offline.champions import ChampionStore, commit_evidence, exported_spec
from offline.experiments import save_new_json
from offline.proposals import resolve_entry
from offline.registry import Entry, ROOT, canonical, digest, source_snapshot
from offline.supervised import run_supervised_game
from omok.evaluation import EvaluationConfig
from tests.test_promotion import PromotionTests


def retain_artifacts(output: Path) -> None:
    """Deduplicate repeated declarations/source bundles without dropping evidence."""
    artifacts = {p.relative_to(output).as_posix(): json.loads(p.read_text(encoding='utf-8'))
                 for p in sorted(output.rglob('*.json'))}
    nodes: dict[str, Any] = {}

    def encode(value: Any) -> dict:
        if isinstance(value, dict):
            node = {'kind': 'object', 'items': {k: encode(v) for k, v in value.items()}}
        elif isinstance(value, list):
            node = {'kind': 'array', 'items': [encode(v) for v in value]}
        elif isinstance(value, str) and len(value) > 512:
            node = {'kind': 'value', 'value': value}
        else:
            return {'value': value}
        identity = digest(node)
        nodes[identity] = node
        return {'ref': identity}

    roots = {path: encode(value) for path, value in artifacts.items()}
    retained = {'format': 'omok-evidence-graph-v1', 'identity': digest(artifacts),
                'artifacts': roots, 'nodes': nodes}
    (output / 'evidence.json.gz').write_bytes(gzip.compress(canonical(retained).encode(), mtime=0))


def collect(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    start = monotonic()
    suite_sources = source_snapshot(ROOT, ('tests/test_tactics.py', 'tests/test_simulator.py',
        'tests/test_iterative.py', 'tests/test_transposition.py', 'tests/test_evaluation.py', 'tests/test_threat_effects.py'))
    context: dict[str, Any] = {'run': 'issue-43 controlled decision mechanics; outcomes and clock observations are fabricated',
        'tactical_suite': {'identity': digest(suite_sources), 'sources': suite_sources}}
    controlled = output / 'controlled'
    controlled.mkdir()
    record, raw, incumbent, candidate = PromotionTests().cohort(controlled,
        suite_identity=context['tactical_suite']['identity'])
    store = ChampionStore(output / 'store')
    baseline = store.initialize(incumbent, context=context, reason='Controlled retained incumbent',
        history=record['confirmation']['selection_context']['history'])
    commit_evidence(controlled / 'checks', raw)
    decision = store.promote(controlled / 'checks')
    if decision['winner'] != candidate.identity:
        raise ValueError('Controlled improved candidate did not promote.')
    promoted = store.load()
    artifact = store.export(output / 'exports/champion.json')
    trace = run_supervised_game(exported_spec(output / 'exports/champion.json', seed=43),
        exported_spec(output / 'exports/champion.json', seed=44), move_cap=2, budgets_ms=(1000, 1000))
    if trace['status'] != 'capped' or not all(w['reaped'] for w in trace['workers']):
        raise ValueError('Real archived synthetic callbacks did not complete safely.')
    save_new_json(output / 'reload-game.json', trace)
    restored = store.rollback(baseline['current'], reason='Demonstrate exact known-version rollback')
    if restored['versions'] != promoted['versions'] or restored['current'] != baseline['current']:
        raise ValueError('Rollback changed the retained archive.')
    restored_artifact = store.export(output / 'exports/baseline.json')
    if restored_artifact['version'] != baseline['versions'][baseline['current']]:
        raise ValueError('Rollback did not restore the exact baseline version.')

    # Observe complete nondefault engine configuration and empty score caches
    # through public diagnostics, with a controlled low-time accounting clock.
    parent = Entry.local('engine-basis', module='omok.player', factory='IterativePlayer', source_paths=('omok',),
        origin='local', family='omok', acknowledgment='Local frozen engine')
    configuration = resolve_entry(parent)
    configuration['evaluation']['coefficients']['material'] = 19
    configuration['settings']['max_depth'] = 1
    configuration['settings']['max_nodes'] = 100
    configuration['settings']['table_capacity'] = 32
    engine = Entry.local('configured-export', module='omok.player', factory='IterativePlayer', source_paths=('omok',),
        options={'candidate_configuration': configuration}, origin='local', family='omok',
        acknowledgment='Nondefault local engine reload probe')
    engine_store = ChampionStore(output / 'engine-store')
    engine_store.initialize(engine, context=context, reason='Exact configuration reload probe, no strength claim')
    engine_store.export(output / 'exports/configured-engine.json')
    probes = []
    for _ in range(2):
        specs = [exported_spec(output / 'exports/configured-engine.json') for _ in (0, 1)]
        probe = run_supervised_game(*specs, move_cap=2, budgets_ms=(1, 1), clock=lambda: 0, diagnostics=True)
        returned = [e['search'] for e in probe['events'] if e['type'] == 'returned']
        expected = EvaluationConfig.from_json(canonical(configuration['evaluation'])).identity
        if (probe['status'] != 'capped' or len(returned) != 2 or any(
                r['evaluation']['configuration_id'] != expected or r['config']['max_nodes'] != 100
                or r['config']['max_depth'] != 1 or r['config']['table_capacity'] != 32
                or r['config']['time_policy'] != configuration['settings']['time_policy']
                or r['table_size'] != 0 or r['table_hits'] != 0 or r['evaluation_cache_hits'] != 0 for r in returned)):
            raise ValueError('Exact configuration or fresh cache reload failed.')
        probes.append(probe)
    save_new_json(output / 'engine-probes.json', {'accounting': 'controlled constant clock; low-time cache/config probe', 'games': probes})
    summary = {'candidate': candidate.identity, 'winner': decision['winner'],
        'baseline_version': baseline['current'], 'promoted_version': promoted['current'],
        'restored_version': restored['current'], 'export_identity': digest(artifact),
        'historical_identities': sorted(promoted['history_slots']),
        'tactical_suite_identity': context['tactical_suite']['identity'],
        'real_reload_status': trace['status'], 'real_reload_moves': len(trace['moves']),
        'configuration_identity': expected, 'configuration_reload_games': len(probes),
        'holdout_exposures': [], 'elapsed_seconds': monotonic() - start,
        'limitations': 'Controlled feasible outcome/clock fixtures prove decision mechanics, not measured strength. '
            'Archived synthetic callbacks were actually executed. Config/cache probes use an injected accounting clock. '
            'No qualification, untouched validation, class-rank or hidden-TA claim.'}
    save_new_json(output / 'summary.json', summary)
    retain_artifacts(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(canonical(collect(args.output)))


if __name__ == '__main__':
    main()
