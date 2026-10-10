# AI-written by OpenAI Codex, for issue #36.
"""Freeze the retained incumbent, verify restoration, then measure bounded screening."""
import argparse
import gzip
from hashlib import sha256
import io
import json
from math import isfinite
from pathlib import Path
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from typing import Any
from time import monotonic

from offline.experiments import ExperimentPlan, run_experiment
from offline.registry import (ROOT, PHASE3, Entry, PoolSnapshot, checkpoint_archive,
                              default_catalog, digest, source_snapshot)
from verification.league_acceptance import gates, inspect_run, write

# Restore and inspect the actual callback, rather than substituting a preset.
PROBE = '''import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from omok.player import IterativePlayer
from omok.simulator import Position
from omok.search import material_evaluation
import omok.player
assert Path(omok.player.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
board = [list(row) for row in Position.empty().board]
board[9][9] = 0
assert material_evaluation(Position(board, 0)) == 1
for color in (0, 1):
    player = IterativePlayer(color)
    supplied = [row[:] for row in board]
    move = player.take_turn(supplied, 0)
    Position(board, color).play(move)
    assert supplied == board
data = player.diagnostics()
data['config'].pop('compatibility') # Contains process-local object identities.
print(json.dumps({key: data[key] for key in ('engine', 'evaluator', 'evaluation', 'config')}, sort_keys=True))
'''


def restored_player(archive: bytes, expected: dict[str, str]) -> dict[str, Any]:
    with TemporaryDirectory(prefix='omok-incumbent-') as directory:
        root = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(root, filter='data')
        if source_snapshot(root, ('omok', 'players', 'configs')) != expected:
            raise ValueError('Incumbent archive sources changed.')
        process = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', PROBE, str(root)],
            cwd=root, text=True, capture_output=True, timeout=30)
        if process.returncode:
            raise ValueError('Isolated incumbent restoration failed: ' + process.stderr)
        return json.loads(process.stdout)


def freeze(output: Path) -> dict[str, Any]:
    """Create a new content-addressed basis; existing artifacts are never overwritten."""
    output.mkdir(parents=True, exist_ok=False)
    catalog, snapshot = default_catalog()
    incumbent = catalog['phase3-material']
    archive = checkpoint_archive(PHASE3, ('omok', 'players', 'configs'))
    with TemporaryDirectory(prefix='omok-basis-') as directory:
        root = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(root, filter='data')
        sources = source_snapshot(root, ('omok', 'players', 'configs'))
    if any(sources[name] != value for name, value in incumbent.data['sources'].items()):
        raise ValueError('Registered incumbent and exported engine disagree.')
    (output / 'incumbent.tar.gz').write_bytes(gzip.compress(archive, mtime=0))
    resolved = restored_player(archive, sources)
    # Preserve the fixed fixtures, contracts and actual prior evidence locally.
    inputs = ('omok', 'offline', 'players', 'tests', 'verification', 'configs', 'docs/phase-01-handoff.md',
        'docs/phase-02-handoff.md', 'docs/phase-03-handoff.md', 'docs/phase-04-handoff.md',
        'docs/evaluation.md', 'docs/search.md', 'docs/experiments.md', 'docs/matches.md',
        'docs/verification/issue-22', 'docs/verification/issue-34')
    hashes = source_snapshot(ROOT, inputs)
    with tarfile.open(output / 'basis-inputs.tar.gz', 'w:gz') as stream:
        for name, expected in hashes.items():
            data = (ROOT / name).read_bytes()
            if sha256(data).hexdigest() != expected:
                raise ValueError('Experimental inputs changed during freeze: ' + name)
            info = tarfile.TarInfo(name)
            info.size = len(data)
            stream.addfile(info, io.BytesIO(data))
    basis = {'format': 'omok-optimizer-basis-v1', 'incumbent': incumbent.record(),
        'experimental_effects': catalog['phase3-effects'].record(),
        'resolved_player': resolved, 'incumbent_sources': sources,
        'runtime': sys.version, 'source_commit': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'pool_snapshot': snapshot.record(),
        'tactical_suite': {'identity': digest({k: v for k, v in hashes.items()
            if k.startswith(('tests/', 'verification/'))}),
            'source_sha256': {k: v for k, v in hashes.items()
                             if k.startswith(('tests/', 'verification/'))}},
        'input_sha256': hashes,
        'artifacts': {name: sha256((output / name).read_bytes()).hexdigest()
                      for name in ('incumbent.tar.gz', 'basis-inputs.tar.gz')},
        'clock_policy': 'separate cumulative clocks; dispatch through response; floor public milliseconds',
        'official_budget_ms': 60000, 'screening_budget_ms': 5000,
        'validation_exposure': 'synthetic-defensive already exposed in Phase 4; validation is not untouched',
        'holdout_exposures': [],
        'competitive_acceptance': {'passed': False, 'simple_strict_wins': 0, 'simple_games': 8,
            'effects_simple_strict_wins': 0, 'effects_simple_games': 8,
            'source': 'docs/verification/issue-22/integration.json',
            'tiny_clock_acceptance': 'partial; four dense 0.5 ms overruns retained in development.json'},
        'policy': 'retain material; effects experimental; no mutation, fitness or promotion policy selected'}
    record = {'identity': digest(basis), 'basis': basis}
    write(output / 'baseline.json', record)
    return record


def verify(output: Path) -> dict[str, Any]:
    """Verify saved bytes and reproduce exact settings without importing working engine code."""
    record = json.loads((output / 'baseline.json').read_text(encoding='utf-8'))
    basis = record['basis']
    if record['identity'] != digest(basis) or basis['runtime'] != sys.version:
        raise ValueError('Baseline identity or compatible Python runtime changed.')
    Entry.from_record(basis['incumbent'])
    PoolSnapshot.from_record(basis['pool_snapshot'])
    for name, expected in basis['artifacts'].items():
        path = (output / name).resolve()
        if not path.is_relative_to(output.resolve()) or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Baseline artifact changed: ' + name)
    archive = gzip.decompress((output / 'incumbent.tar.gz').read_bytes())
    resolved = restored_player(archive, basis['incumbent_sources'])
    if resolved != basis['resolved_player']:
        raise ValueError('Restored player configuration differs from frozen incumbent.')
    return {'identity': record['identity'], 'restoration': 'exact',
            'isolated': True, 'no_site': True, 'resolved_player': resolved}


def collect(output: Path, *, probe_seconds: float = 60,
            contention: str = 'one local game worker; external OS load uncontrolled') -> None:
    if not isfinite(probe_seconds) or not 0 < probe_seconds <= 120:
        raise ValueError('Probe budget must be positive, finite and at most 120 seconds.')
    record = freeze(output)
    write(output / 'restoration.json', verify(output))
    basis = record['basis']
    # Existing suites exercise the exact incumbent only while source bytes match.
    current = source_snapshot(ROOT, ('omok', 'players'))
    if any(current.get(k) != v for k, v in basis['incumbent']['sources'].items()):
        raise ValueError('Working engine differs from incumbent; establish compatible gates separately.')
    # No game throughput is collected if correctness/reliability gates fail.
    gates(output)
    command = [sys.executable, '-m', 'unittest', *('tests.test_' + name for name in (
        'tactics', 'transposition', 'lines', 'potential', 'captures', 'provided',
        'integration', 'measurement', 'reference', 'optimizer_baseline')), '-v']
    start = monotonic()
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=600)
    write(output / 'fixed-suite-gates.json', {'command': command, 'exit_code': process.returncode,
        'wall_seconds': monotonic() - start, 'stdout': process.stdout, 'stderr': process.stderr})
    print(json.dumps({'gate': 'fixed-tactical-and-public-suites', 'exit_code': process.returncode}), flush=True)
    if process.returncode:
        raise RuntimeError('Fixed tactical/public suite failed; no throughput evidence collected.')
    if source_snapshot(ROOT, tuple(basis['input_sha256'])) != basis['input_sha256']:
        raise ValueError('Experimental basis changed while running gates.')
    snapshot = PoolSnapshot.from_record(basis['pool_snapshot'])
    incumbent = Entry.from_record(basis['incumbent'])
    plan = ExperimentPlan.resolve(incumbent, snapshot, purpose='training',
        opponents=['simple', 'synthetic-capture', 'synthetic-pattern'], mode='screening',
        games_per_opponent=2, total_ms=5000, move_cap=20, seed=20261010, diagnostics=True)
    directory = output / 'throughput-1'
    directory.mkdir()
    raw = run_experiment(plan, output=directory / 'run', workers=1,
        max_seconds=probe_seconds, contention=contention,
        progress=lambda counts: print(json.dumps({'probe': counts}), flush=True))
    summary = inspect_run(plan, raw, directory)
    summary.update(format='omok-optimizer-baseline-probe-v1', basis_identity=record['identity'],
        requested_max_seconds=probe_seconds, workers=1, purpose='training', mode='screening',
        total_ms_per_player=5000, move_cap=20, planned_games=len(plan.data['jobs']),
        holdout_played_or_tactical_exposures=[], validation_game_exposures=[],
        official_completed_game_throughput=None,
        resource_choice='one worker; retain serial wall-clock comparisons; no GPU/cloud dependency',
        limitations='Capped reduced-clock screening slots do not estimate official completed games; '
                    'CPU/RAM snapshots are recorded, peak per-process memory and OS contention are not measured.')
    write(output / 'probe.json', summary)
    print(json.dumps({'basis_identity': record['identity'], 'counts': raw['counts'],
                      'output': str(output)}), flush=True)
    if raw['counts']['infrastructure_failed'] or raw['counts']['failed']:
        raise RuntimeError('Probe failures retained; baseline requires investigation before optimization.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('collect', 'freeze', 'verify'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--probe-seconds', type=float, default=60)
    parser.add_argument('--contention', default='one local game worker; external OS load uncontrolled')
    args = parser.parse_args()
    if not 0 < args.probe_seconds <= 120:
        parser.error('--probe-seconds must be positive and at most 120')
    if args.mode == 'collect':
        collect(args.output, probe_seconds=args.probe_seconds, contention=args.contention)
    elif args.mode == 'freeze':
        print(json.dumps({'identity': freeze(args.output)['identity'], 'output': str(args.output)}))
    else:
        print(json.dumps(verify(args.output)))


if __name__ == '__main__':
    main()
