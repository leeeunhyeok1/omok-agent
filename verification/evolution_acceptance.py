# AI-written by OpenAI Codex for issue #45; offline acceptance only.
"""Bounded public-command autonomous pilot, clock audit and exact export restore."""
import argparse
import json
from hashlib import file_digest
import tarfile
from pathlib import Path
import subprocess
import sys
from time import monotonic
from typing import Any

from offline.champions import ChampionStore, exported_spec
from offline.evolution import starter_policy, status
from offline.experiments import save_new_json
from offline.registry import ROOT, canonical, default_catalog, digest, source_snapshot
from offline.replay import replay
from offline.supervised import run_supervised_game
from verification.reviews import collect as checked_failure


def collect(output: Path, *, power: str, load: str) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    start = monotonic()
    catalog, snapshot = default_catalog()
    incumbent = catalog['phase3-material']
    policy = starter_policy(incumbent)
    # A near-win opening limits pilot cost. This measures execution, not general strength.
    opening = [[9, 5], [10, 5], [9, 6], [10, 6], [9, 7], [10, 7], [9, 8], [10, 8]]
    policy.update(population_size=1, validation_every=2, seed=46)
    for name in ('screening', 'league', 'confirmation'):
        screen = policy[name] if name == 'screening' else policy[name]['screening']
        screen.update(opponents={'smoke': 2, 'synthetic-aggressive': 2},
                      opponent_weights={'smoke': 1, 'synthetic-aggressive': 1},
                      family_weights={'random-smoke': 1, 'line-pattern': 1},
                      min_evidence_per_color=1, move_cap=20)
    policy['screening_openings'] = policy['league_openings'] = [opening]
    # Validation includes an ordinary empty-board game; official games always start empty.
    policy['validation_openings'] = [[], opening]
    policy['promotion'].update(validation_ms=5000, validation_cap=100)
    save_new_json(output / 'policy.json', policy)
    conditions = {'power': power, 'load': load, 'other_experiments_stopped': True}
    save_new_json(output / 'conditions.json', conditions)
    context = {'sources': source_snapshot(ROOT, ('omok', 'offline', 'verification', 'tests')),
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'machine_conditions': conditions,
        'scope': 'Actual mutated engine candidates, both colors; two automatic rounds; no holdout.'}
    save_new_json(output / 'context.json', context)
    run_output = output / 'autonomous'

    def command(label: str, *arguments: str) -> None:
        argv = [sys.executable, '-m', 'offline.optimizer', *arguments, '--output', str(run_output)]
        print(label, flush=True)
        with (output / (label + '.log')).open('w') as log:
            result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT)
        save_new_json(output / (label + '-command.json'), {'argv': argv, 'returncode': result.returncode})
        if result.returncode:
            raise ValueError('Public command failed; inspect ' + label + '.log')

    command('initialize', 'initialize', '--policy', str(output / 'policy.json'))
    command('partial', 'run', '--max-games', '1', '--max-seconds', '120', '--contention', load)
    partial = status(run_output)
    save_new_json(output / 'partial.json', partial)
    command('first-round', 'run', '--max-games', '100', '--max-seconds', '600', '--max-rounds', '1',
            '--conditions', str(output / 'conditions.json'), '--contention', load)
    first = status(run_output)
    if len(first['rounds']) != 1 or first['rounds'][0]['stage'] != 'committed':
        raise ValueError('First round did not commit honestly within its allocation.')
    stop_file = output / 'STOP'
    stop_file.touch()
    command('stop-at-boundary', 'run', '--max-games', '100', '--max-seconds', '120',
            '--stop-file', str(stop_file), '--contention', load)
    stopped = status(run_output)
    if stopped['rounds'] != first['rounds'] or stopped['segments'][-1]['attempts'] != 0:
        raise ValueError('Stop file changed a committed round or dispatched work.')
    stop_file.unlink()
    command('second-round', 'run', '--max-games', '150', '--max-seconds', '900', '--max-rounds', '1',
            '--conditions', str(output / 'conditions.json'), '--contention', load)
    final = status(run_output)
    if len(final['rounds']) != 2 or any(r['stage'] != 'committed' for r in final['rounds']):
        raise ValueError('Second autonomous round did not commit within its allocation.')
    if final['rounds'][1]['parents'] != first['rounds'][0]['decision']['parents']:
        raise ValueError('Next population did not use committed parent selection.')
    if final['rounds'][0]['population'] != partial['rounds'][0]['population']:
        raise ValueError('Resume regenerated the first population.')
    command('status', 'status')
    command('review', 'review', '--round', '1')
    command('export', 'export', '--destination', str(output / 'exports/incumbent.json'))
    command('idempotent', 'run', '--max-games', '0', '--max-seconds', '0')
    if status(run_output)['rounds'] != final['rounds']:
        raise ValueError('Zero-budget resume changed logical decisions.')

    replayed, exposures = 0, []
    for round_record in final['rounds']:
        for stage in round_record['stages'].values():
            for raw in stage['raw'].values():
                for result in raw['results']:
                    exposures.append(result['exposure'])
                    if result.get('trace') is not None:
                        replay(result['trace'])
                        replayed += 1
    unknown_exposures = [e for e in exposures if not e.get('purpose') or e.get('kind') == 'unknown-supervisor-failure']
    if any(e.get('pool') == 'holdout' or e.get('purpose') in ('final', 'final-evaluation') for e in exposures):
        raise ValueError('Reserved final evidence was consumed.')
    checks = final['rounds'][1]['stages']['checks']['report']
    checked = checks['candidates'][final['rounds'][1]['incumbent']['identity']]
    if checked['validation']['requested_jobs'] != 4 or checked['official']['requested_jobs'] != 8:
        raise ValueError('Required actual validation/official allocation missing.')
    probe = run_supervised_game(exported_spec(output / 'exports/incumbent.json', seed=45),
        exported_spec(output / 'exports/incumbent.json', seed=46), move_cap=2,
        budgets_ms=(5000, 5000), diagnostics=True)
    if probe['status'] != 'capped' or len(probe['moves']) != 2 or probe['failure']:
        raise ValueError('Exact champion export did not restore.')
    save_new_json(output / 'export-probe.json', probe)
    print('Two rounds, actual clock checks and exact export complete; retaining checked failure evidence.', flush=True)
    checked_failure(output / 'checked-failure')
    save_new_json(output / 'exposure-audit.json', {'snapshot': snapshot.record(), 'exposures': exposures,
        'known_holdout_execution_count': 0, 'holdout_tactical_calls': 0,
        'unknown_exposures': unknown_exposures,
        'scope': 'This collector; historical development exposure retained in earlier reports.'})
    training_attempts = sum(len(raw['attempts']) for r in final['rounds']
                           for name, stage in r['stages'].items() if name != 'checks'
                           for raw in stage['raw'].values())
    summary = {'format': 'omok-phase05-acceptance-v1', 'context_identity': digest(context),
        'rounds': [{'index': r['index'], 'seed': r['seed'], 'parents': [p['identity'] for p in r['parents']],
                    'candidates': [c['entry']['identity'] for c in r['population']['candidates']],
                    'decision': r['decision']} for r in final['rounds']],
        'segments': final['segments'], 'incumbent': final['incumbent']['identity'],
        'actual_validation': {k: checked['validation'][k] for k in ('requested_jobs', 'by_opponent', 'reliability_samples')},
        'actual_official': {k: checked['official'][k] for k in ('requested_jobs', 'by_opponent', 'reliability_samples')},
        'clock': checked['clock'], 'training_attempts': training_attempts,
        'first_round_attempts_per_second': sum(s['attempts'] for s in first['segments']) /
            max(sum(s['wall_seconds'] for s in first['segments']), .001),
        'replayed_traces': replayed, 'export_identity': digest(json.loads((output / 'exports/incumbent.json').read_text())),
        'champion_transactions': len(ChampionStore(run_output / 'champions').load()['transactions']),
        'holdout_exposures': 0, 'unknown_exposure_count': len(unknown_exposures), 'elapsed_seconds': monotonic() - start,
        'limitations': 'Tiny near-win-opening pilot proves execution, not strength gain. Official smoke '
            'audit is not professor-player qualification. Validation was already development-exposed. '
            'Checked missed-win fixture is fabricated mechanics evidence. No Phase 6 or submission package.'}
    from tests.test_evolution import EvolutionTests
    print('Collecting fabricated complete multi-round promotion/history mechanics.', flush=True)
    EvolutionTests().test_controlled_complete_path_promotes_retains_history_and_resumes_transaction(
        evidence_output=output / 'controlled-autonomous')
    summary['controlled_mechanics'] = 'Fabricated outcomes; promotion, rejected confirmation, history, crash recovery; no strength claim'
    summary['elapsed_seconds'] = monotonic() - start
    save_new_json(output / 'summary.json', summary)
    # Stream files instead of building a second in-memory copy of all run evidence.
    inventory = {}
    with tarfile.open(output / 'evidence.tar.gz', 'w:gz', compresslevel=3) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file() and path.suffix in ('.json', '.log', '.md'):
                name = path.relative_to(output).as_posix()
                with path.open('rb') as stream:
                    inventory[name] = file_digest(stream, 'sha256').hexdigest()
                archive.add(path, arcname=name, recursive=False)
    save_new_json(output / 'inventory.json', inventory)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--power', required=True)
    parser.add_argument('--load', required=True)
    args = parser.parse_args()
    result = collect(args.output, power=args.power, load=args.load)
    print(canonical({k: result[k] for k in ('elapsed_seconds', 'training_attempts', 'holdout_exposures')}))


if __name__ == '__main__':
    main()
