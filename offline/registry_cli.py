# AI-written by OpenAI Codex, for issue #26.
"""Freeze a registry or play one registered game with explicit exposure purpose."""
import argparse
import json
from pathlib import Path

from offline.registry import Entry, PoolSnapshot, PURPOSES, default_catalog, run_registered_game
from offline.supervised import Supervision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze', help='Save current exposed versions; never overwrites an existing file')
    freeze.add_argument('--output', type=Path, required=True)
    play = commands.add_parser('play')
    play.add_argument('--registry', type=Path, required=True)
    play.add_argument('--candidate', required=True)
    play.add_argument('--opponent', required=True)
    play.add_argument('--candidate-color', choices=('black', 'white'), default='black')
    play.add_argument('--purpose', choices=PURPOSES, default='development')
    play.add_argument('--seed', type=int, default=20261010)
    play.add_argument('--total-ms', type=float, default=60000)
    play.add_argument('--move-cap', type=int, default=1000)
    play.add_argument('--startup-ms', type=float, default=5000)
    play.add_argument('--diagnostics', action='store_true')
    play.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'freeze':
            catalog, snapshot = default_catalog()
            result = {'format': 'omok-registry-v1', 'entries': [e.record() for e in catalog.values()],
                      'pool_snapshot': snapshot.record()}
        else:
            data = json.loads(args.registry.read_text(encoding='utf-8'))
            if data['format'] != 'omok-registry-v1':
                raise ValueError('Unsupported registry format.')
            entries = [Entry.from_record(record) for record in data['entries']]
            catalog = {entry.data['logical_id']: entry for entry in entries}
            if len(catalog) != len(entries):
                raise ValueError('Duplicate candidate logical ID.')
            if args.candidate not in catalog:
                raise ValueError('Unknown candidate: ' + args.candidate)
            snapshot = PoolSnapshot.from_record(data['pool_snapshot'])
            # Reject conflicting entry versions instead of mixing catalog/snapshot identities.
            for pool in data['pool_snapshot']['pools'].values():
                for record in pool:
                    if record['logical_id'] not in catalog or catalog[record['logical_id']].identity != record['identity']:
                        raise ValueError('Catalog and pool snapshot disagree: ' + record['logical_id'])
            if args.output.exists():
                raise ValueError('Output already exists: ' + str(args.output))
            result = run_registered_game(catalog[args.candidate], snapshot, args.opponent,
                candidate_color=0 if args.candidate_color == 'black' else 1,
                purpose=args.purpose, seed=args.seed, move_cap=args.move_cap,
                budgets_ms=(args.total_ms, args.total_ms), diagnostics=args.diagnostics,
                supervision=Supervision(startup_ms=args.startup_ms))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'output': str(args.output), 'format': result['format'],
                          'status': result.get('status')}))
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
