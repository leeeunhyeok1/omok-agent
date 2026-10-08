# AI-written by OpenAI Codex, for issue #7.
"""Serial, externally bounded supplied-bot integration evidence."""
import argparse
from collections import Counter
import json
from math import isfinite
from pathlib import Path
import platform
import subprocess
import sys
from time import monotonic
from typing import Any

from offline.replay import load_trace, replay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--budget-ms', type=float, default=60000)
    parser.add_argument('--deadline-seconds', type=float, default=180)
    parser.add_argument('--move-cap', type=int, default=1000)
    parser.add_argument('--output', type=Path, default=Path('docs/verification/issue-7-integration.json'))
    parser.add_argument('--traces', type=Path, default=Path('.scratch/issue-7-integration'))
    args = parser.parse_args()
    if (not isfinite(args.budget_ms) or args.budget_ms <= 0
            or not isfinite(args.deadline_seconds) or args.deadline_seconds <= 0
            or args.move_cap < 0):
        parser.error('Budgets and deadlines must be finite and positive; caps nonnegative.')
    args.traces.mkdir(parents=True, exist_ok=True)
    games: list[dict[str, Any]] = []
    for opponent in ('random', 'simple'):
        for color in ('black', 'white'):
            for seed in range(20261008, 20261012):
                path = args.traces / f'{opponent}-{color}-{seed}.json'
                path.unlink(missing_ok=True)
                command = [sys.executable, '-m', 'offline', '--opponent', opponent,
                           '--baseline-color', color, '--seed', str(seed),
                           '--black-ms', str(args.budget_ms), '--white-ms', str(args.budget_ms),
                           '--move-cap', str(args.move_cap), '--output', str(path)]
                start = monotonic()
                record: dict[str, Any] = {'opponent': opponent, 'baseline_color': color, 'seed': seed,
                          'command': command, 'trace': str(path)}
                try:
                    process = subprocess.run(command, capture_output=True, text=True,
                                             timeout=args.deadline_seconds)
                    if process.returncode:
                        summary = {'status': 'failed', 'reason': 'process_exit',
                                   'returncode': process.returncode, 'stderr': process.stderr}
                    else:
                        trace = load_trace(path)
                        replay(trace)
                        summary = {key: trace[key] for key in
                                   ('status', 'reason', 'winner', 'failure', 'remaining_ms')}
                        summary['moves'] = len(trace['moves'])
                        record['sources'] = trace['config']['provided_source_sha256']
                except subprocess.TimeoutExpired:
                    summary = {'status': 'failed', 'reason': 'external_timeout',
                               'offending_player': 'unknown: process terminated during game'}
                record.update(wall_seconds=monotonic() - start, summary=summary)
                games.append(record)
                report = {
                    'python': platform.python_version(), 'platform': platform.platform(),
                    'machine': platform.machine(), 'workers': 1,
                    'budget_ms_per_player': args.budget_ms,
                    'budget_kind': '60000-ms total-budget integration' if args.budget_ms == 60000
                                   else 'cheaper screening',
                    'external_deadline_seconds': args.deadline_seconds, 'move_cap': args.move_cap,
                    'opening': 'empty; deterministic repeats are duplicate evidence',
                    'counts': dict(Counter(g['summary']['status'] for g in games)),
                    'failure_reasons': dict(Counter(g['summary']['reason'] for g in games
                                                   if g['summary']['status'] == 'failed')),
                    'games': games,
                }
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
                print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
