# AI-written by OpenAI Codex, for issue #15.
"""Bounded Phase 2 evidence collection, not a tournament or promotion framework."""
import argparse
from collections import Counter
import cProfile
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import pstats
import statistics
import subprocess
import sys
from time import monotonic

from offline.replay import replay
from verification.integration import check_lines


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def environment():
    from omok.player import IterativePlayer
    player = IterativePlayer(0)
    player.take_turn([[-1] * 19 for _ in range(19)], 0)
    snapshot = player.diagnostics()
    hardware = {}
    if sys.platform == 'darwin':
        for key in ('machdep.cpu.brand_string', 'hw.memsize', 'hw.physicalcpu', 'hw.logicalcpu'):
            hardware[key] = subprocess.check_output(['sysctl', '-n', key], text=True).strip()
    return {'python': sys.version, 'executable': sys.executable,
            'platform': platform.platform(), 'machine': platform.machine(),
            'logical_cpus': os.cpu_count(), 'hardware': hardware, 'workers': 1,
            'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'engine_sha256': {str(p): sha256(p.read_bytes()).hexdigest()
                              for p in sorted(Path('omok').glob('*.py'))},
            'configuration': snapshot['config'], 'evaluator': snapshot['evaluator']}


def distribution(values):
    ordered = sorted(values)
    return {'count': len(values), 'min': min(values), 'median': statistics.median(values),
            'p95_nearest_rank': ordered[max(0, (95 * len(values) + 99) // 100 - 1)],
            'max': max(values)}


def measurements(output):
    # Existing probes validate each returned move through independent reference rules.
    probes = json.loads(subprocess.check_output([sys.executable, '-m', 'verification.iterative'], text=True))
    write(output / 'timing.json', probes)
    from omok.player import IterativePlayer
    from verification.reference import ReferencePosition
    board = [[-1] * 19 for _ in range(19)]
    board[9][10:13] = [1, 1, 0]
    before = [row[:] for row in board]
    player = IterativePlayer(0)
    profiler = cProfile.Profile()
    calls = []
    profiler.enable()
    for _ in range(10):
        move = player.take_turn(board, 60000)
        ReferencePosition(before, 0).play(move)
        assert board == before
        calls.append(player.diagnostics())
    profiler.disable()
    profiler.dump_stats(str(output / 'profile.pstats'))
    stats = pstats.Stats(profiler)
    functions = [{'file': key[0], 'line': key[1], 'function': key[2],
                  'primitive_calls': value[0], 'calls': value[1],
                  'self_seconds': value[2], 'cumulative_seconds': value[3]}
                 for key, value in stats.stats.items() if '/omok/' in key[0]]
    functions.sort(key=lambda item: item['cumulative_seconds'], reverse=True)
    groups = {}
    for record in probes['probes']:
        key = f"{record['mode']}:{record['remaining_ms']}"
        groups.setdefault(key, []).append(record['elapsed_ms'])
    report = {'environment': environment(), 'timing_distributions_ms':
              {key: distribution(values) for key, values in groups.items()},
              'incoming_clock_overruns': [p for p in probes['probes'] if p['exceeds_incoming_clock']],
              'failures': [p for p in probes['probes'] if p['failures']],
              'profile': {'calls': calls, 'fixture': 'sparse capture', 'functions': functions[:25],
                          'notes': 'Serial local cProfile, warm table retained; reference legality checks '
                                   'included in total profile but excluded from engine function rows. '
                                   'Instrumentation affects timing; no throughput gate.'}}
    write(output / 'measurements.json', report)


def games(output, kind):
    budget, cap = (1000, 120) if kind == 'screening' else (60000, 1000)
    records = []
    report = {'environment': environment(), 'kind': kind, 'budget_ms_per_player': budget,
              'move_cap': cap, 'external_deadline_seconds': 180,
              'opening': 'empty; seeded duplicates are not independent evidence', 'games': records}
    for opponent in ('baseline', 'random', 'simple'):
        for color in ('black', 'white'):
            for seed in range(20261009, 20261013):
                trace_path = output / f'{kind}-{opponent}-{color}-{seed}.json'
                trace_path.unlink(missing_ok=True)
                command = [sys.executable, '-m', 'offline', '--engine', 'search', '--diagnostics',
                           '--opponent', opponent, '--agent-color', color, '--seed', str(seed),
                           '--black-ms', str(budget), '--white-ms', str(budget),
                           '--move-cap', str(cap), '--output', str(trace_path)]
                start = monotonic()
                record = {'opponent': opponent, 'search_color': color, 'seed': seed, 'command': command}
                try:
                    process = subprocess.run(command, text=True, capture_output=True, timeout=180)
                    if process.returncode:
                        record.update(status='failed', reason='process_exit', stderr=process.stderr,
                                      returncode=process.returncode)
                    else:
                        trace = json.loads(trace_path.read_text())
                        replay(trace)
                        lines = check_lines(trace)
                        for key in ('status', 'reason', 'winner', 'failure', 'remaining_ms'):
                            record[key] = trace[key]
                        record['moves'] = len(trace['moves'])
                        record['verified_complete_pvs'] = lines
                        reports = [e['search'] for e in trace['events'] if 'search' in e]
                        record['completed_depths'] = dict(Counter(r['completed_depth'] for r in reports))
                        record['public_elapsed_ms'] = distribution([r['elapsed_ms'] for r in reports]) if reports else None
                        record['nodes'] = sum(r['nodes'] for r in reports)
                        record['max_table_size'] = max((r['table_size'] for r in reports), default=0)
                        record['provided_sources'] = trace['config']['provided_source_sha256']
                        compressed = trace_path.with_suffix('.json.gz')
                        with gzip.open(compressed, 'wt') as stream:
                            json.dump(trace, stream, separators=(',', ':'), allow_nan=False)
                        record['trace'] = str(compressed)
                        record['trace_sha256'] = sha256(compressed.read_bytes()).hexdigest()
                        trace_path.unlink()
                except subprocess.TimeoutExpired:
                    record.update(status='failed', reason='external_timeout', failure='offending player unknown')
                record['wall_seconds'] = monotonic() - start
                records.append(record)
                report['status_counts'] = dict(Counter(r['status'] for r in records))
                write(output / f'{kind}.json', report)
                print(json.dumps(record), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('measure', 'screening', 'official', 'replay'))
    parser.add_argument('--output-dir', type=Path, default=Path('docs/verification/issue-15'))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == 'measure':
        measurements(args.output_dir)
    elif args.mode == 'replay':
        paths = sorted(args.output_dir.glob('*.json.gz'))
        if not paths:
            parser.error('No preserved traces found.')
        lines = 0
        for path in paths:
            with gzip.open(path, 'rt') as stream:
                trace = json.load(stream)
            replay(trace)
            lines += check_lines(trace)
        print(json.dumps({'replayed_traces': len(paths), 'verified_complete_pvs': lines}))
    else:
        games(args.output_dir, args.mode)


if __name__ == '__main__':
    main()
