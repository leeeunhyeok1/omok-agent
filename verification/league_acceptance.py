# AI-written by OpenAI Codex, for issue #34.
"""Collect Phase 4 gates and bounded real-player evidence without tuning players."""
import argparse
import gzip
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any

from offline.experiments import ExperimentPlan, run_experiment
from offline.inspection import inspect_loss
from offline.registry import ROOT, default_catalog
from offline.replay import replay
from offline.reports import report_experiment
from verification.reference import ReferencePosition

PREREQUISITES = ('simulator', 'differential', 'player', 'iterative', 'evaluation',
                 'threat_effects', 'search')
FRAMEWORK = ('runner', 'supervised', 'registry', 'experiments', 'matches', 'batches',
             'synthetic', 'replay', 'loss_inspection', 'concurrency', 'reports')


def write(path: Path, value: Any) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def compressed(path: Path, value: Any) -> None:
    with gzip.open(path, 'xt', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)


def gates(output: Path) -> None:
    records = []
    for name, modules in (('prerequisites', PREREQUISITES), ('framework', FRAMEWORK)):
        command = [sys.executable, '-m', 'unittest', *('tests.test_' + m for m in modules), '-v']
        start = monotonic()
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=600)
        records.append({'gate': name, 'command': command, 'exit_code': process.returncode,
                        'wall_seconds': monotonic() - start,
                        'stdout': process.stdout, 'stderr': process.stderr})
        print(json.dumps({'gate': name, 'exit_code': process.returncode}), flush=True)
        if process.returncode:
            write(output / 'gates.json', records)
            raise RuntimeError('Acceptance gate failed; see gates.json.')
    write(output / 'gates.json', records)


def restore(output: Path, ref: str) -> None:
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', ref + '^{commit}'],
                                     cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(['git', 'archive', commit], cwd=ROOT)
    with TemporaryDirectory(prefix='omok-phase04-restore-') as directory:
        root = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(root, filter='data')
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        command = [sys.executable, '-B', '-m', 'unittest',
            'tests.test_experiments.ExperimentTests.test_official_plan_saves_and_recreates_all_eight_slots',
            'tests.test_supervised.SupervisedTests.test_nonreturning_player_is_bounded_and_next_game_runs',
            'tests.test_reports', '-v']
        start = monotonic()
        process = subprocess.run(command, cwd=root, env=environment,
                                 text=True, capture_output=True, timeout=120)
        record = {'commit': commit, 'archive_sha256': sha256(archive).hexdigest(),
            'command': command, 'exit_code': process.returncode, 'wall_seconds': monotonic() - start,
            'stdout': process.stdout, 'stderr': process.stderr,
            'restored_sources': {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
                for name in ('omok', 'offline', 'players', 'configs')
                for p in sorted((root / name).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}}
        write(output / 'restoration.json', record)
        if process.returncode:
            raise RuntimeError('Restored checkpoint failed; see restoration.json.')


def inspect_run(plan: ExperimentPlan, raw: dict[str, Any], output: Path) -> dict[str, Any]:
    """Validate saved moves independently and retain failures instead of hiding them."""
    games = []
    for result in raw['results']:
        trace = result['trace']
        oracle_checked = False
        reaped = False
        if trace is not None:
            final = replay(trace)
            oracle = ReferencePosition(trace['initial']['board'], trace['initial']['side_to_move'])
            for move in trace['moves']:
                oracle = oracle.play(move['move']).position
            if (oracle.board, oracle.outcome, oracle.reason) != (final.board, final.outcome, final.reason):
                raise AssertionError('Independent rules replay disagrees: ' + result['game_id'])
            oracle_checked = True
            workers = trace['workers']
            preflight = result.get('preflight', [])
            reaped = (len(workers) == 2 and all(w['reaped'] for w in workers)
                      and all(p['worker']['reaped'] for p in preflight))
            if not reaped:
                raise AssertionError('Worker cleanup not established: ' + result['game_id'])
            if trace['failure'] or (trace['winner'] is not None and trace['winner'] != result['candidate_color']):
                compressed(output / (result['game_id'] + '-loss.json.gz'),
                           inspect_loss(trace, color=result['candidate_color'], max_positions=4))
        games.append({'game_id': result['game_id'], 'opponent': next(
            j['opponent']['logical_id'] for j in plan.data['jobs'] if j['game_id'] == result['game_id']),
            'candidate_color': result['candidate_color'], 'status': result['status'],
            'reason': trace['reason'] if trace else result['error'],
            'moves': len(trace['moves']) if trace else None,
            'independent_replay': oracle_checked, 'all_workers_reaped': reaped})
    report = report_experiment(plan, raw)
    compressed(output / 'report.json.gz', report)
    # Full durable run directory remains available for resume. These compact copies
    # preserve the exact plan, attempts, segments, traces and exposure for Git.
    compressed(output / 'plan.json.gz', plan.record())
    compressed(output / 'results.json.gz', raw)
    segments = raw['segments']
    wall = sum(s['wall_seconds'] for s in segments)
    return {'manifest_identity': plan.identity, 'counts': raw['counts'], 'games': games,
            'conditions': [s['conditions'] for s in segments], 'wall_seconds': wall,
            'observed_slots_per_second': len(raw['results']) / wall if wall else None,
            'completed_rule_games_per_second': raw['counts']['completed'] / wall if wall else None,
            'rating': report['rating'], 'averages': report['averages'],
            'candidate': plan.data['candidate']['identity']}


def smoke(output: Path) -> None:
    catalog, snapshot = default_catalog()
    compressed(output / 'registry.json.gz', {'format': 'omok-registry-v1',
        'entries': [e.record() for e in catalog.values()], 'pool_snapshot': snapshot.record()})
    reserved = [e['logical_id'] for e in snapshot.record()['pools']['holdout']]
    if any(e.data['logical_id'] in reserved for _, e in snapshot.select()):
        raise AssertionError('Default selection exposed holdout.')
    for name in reserved:
        try:
            snapshot.select([name], purpose='development')
        except ValueError:
            continue
        raise AssertionError('Explicit development selection exposed holdout.')
    opponents = ['phase1', 'phase2', 'synthetic-capture', 'synthetic-pattern',
                 'synthetic-search2', 'synthetic-defensive']
    supplied = {name: catalog[name].data['availability'] for name in ('random', 'simple')}
    opponents += [name for name, status in supplied.items() if status == 'ready']
    runs = []
    definitions = [('material', 'phase3-material', opponents, 20),
                   ('experimental-effects', 'phase3-effects', ['phase2', 'simple']
                    if supplied['simple'] == 'ready' else ['phase2'], 12)]
    scheduled = []
    for label, candidate, selected, cap in definitions:
        plan = ExperimentPlan.resolve(catalog[candidate], snapshot, opponents=selected,
            mode='screening', games_per_opponent=2, total_ms=5000, move_cap=cap,
            seed=20261010, diagnostics=True)
        scheduled.append((label, plan, 1, 300))
    # Identical saved fixed schedule under two concurrency conditions. This is
    # reduced-clock screening, not a fixed-work or official timing comparison.
    plan = ExperimentPlan.resolve(catalog['phase2'], snapshot,
        opponents=['synthetic-capture', 'synthetic-pattern'], mode='screening',
        games_per_opponent=2, total_ms=5000, move_cap=8, seed=20261010)
    for workers in (1, 2):
        scheduled.append(('throughput-' + str(workers), plan, workers, 120))
    for label, plan, workers, seconds in scheduled:
        directory = output / label
        directory.mkdir()
        raw = run_experiment(plan, output=directory / 'run', workers=workers, max_seconds=seconds,
            contention='acceptance; no other agent experiments; external OS load uncontrolled',
            progress=lambda counts: print(json.dumps({'run': label, **counts}), flush=True))
        summary = inspect_run(plan, raw, directory)
        write(directory / 'summary.json', summary)
        runs.append({'label': label, **summary})
    summary = {'format': 'omok-phase04-acceptance-v1', 'command': sys.argv,
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'pool_snapshot_identity': snapshot.identity, 'reserved_holdout': reserved,
        'holdout_played_or_tactical_exposures': [], 'supplied_availability': supplied,
        'zero_observed_player_failures': all(r['counts']['failed'] == 0 for r in runs),
        'framework_execution_complete': all(r['counts'][key] == 0 for r in runs
                                             for key in ('infrastructure_failed', 'pending')),
        'runs': runs, 'limitations': 'Short empty-board color-balanced screening; caps are not draws. '
        'Related designs and paired seeds are not independent trials. No strategic-win or throughput gate. '
        'Classmates and hidden TA agents unavailable. No tuning, promotion or final holdout evaluation.'}
    write(output / 'summary.json', summary)
    if not summary['framework_execution_complete']:
        raise RuntimeError('Smoke collection has infrastructure failures/pending jobs; see summary.json.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('gates', 'smoke', 'restore'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ref', default='HEAD', help='Immutable Git checkpoint to restore in a temporary directory')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.command == 'gates':
        gates(args.output)
    elif args.command == 'smoke':
        smoke(args.output)
    else:
        restore(args.output, args.ref)


if __name__ == '__main__':
    main()
