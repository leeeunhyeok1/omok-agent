# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
"""Externally bounded CLI games, serial to avoid concurrent timing distortion."""
import json
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path
from time import monotonic

from offline.replay import replay


def main() -> None:
    directory = Path('.scratch/issue-4-smoke')
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    for color in ('black', 'white'):
        for seed in range(20261008, 20261012):
            path = directory / f'{color}-{seed}.json'
            command = [sys.executable, '-m', 'offline', '--baseline-color', color,
                       '--seed', str(seed), '--output', str(path)]
            start = monotonic()
            completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
            trace = json.loads(path.read_text())
            replay(trace)
            results.append({'color': color, 'seed': seed, 'wall_seconds': monotonic() - start,
                            'trace': str(path), 'summary': json.loads(completed.stdout)})
    probes = []
    for name, options in [('cap', ['--move-cap', '2']),
                          ('exhausted', ['--black-ms', '0']),
                          ('unlimited', ['--black-ms', '-1', '--white-ms', '-1', '--move-cap', '2'])]:
        path = directory / f'{name}.json'
        completed = subprocess.run([sys.executable, '-m', 'offline', *options, '--output', str(path)],
                                   capture_output=True, text=True, timeout=30, check=True)
        replay(json.loads(path.read_text()))
        probes.append({'name': name, 'trace': str(path), 'summary': json.loads(completed.stdout)})
    report = {'python': platform.python_version(), 'platform': platform.platform(),
              'machine': platform.machine(), 'workers': 1, 'external_deadline_seconds': 30,
              'budget_ms_per_player': 60000, 'move_cap': 1000,
              'smoke_counts': dict(Counter(r['summary']['status'] for r in results)),
              'probe_counts': dict(Counter(p['summary']['status'] for p in probes)),
              'games': results, 'contract_probes': probes}
    destination = Path('docs/verification/issue-4-smoke.json')
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('smoke_counts', 'probe_counts')}))


if __name__ == '__main__':
    main()
