# AI-written by OpenAI Codex, for issue #27.
"""Save a resolved experiment plan, then execute its exact serial schedule."""
import argparse
import json
from pathlib import Path

from offline.experiments import ExperimentPlan, MODES, run_experiment, save_new_json
from offline.matches import score_experiment
from offline.registry import Entry, PoolSnapshot, PURPOSES
from offline.supervised import Supervision
from omok.simulator import Position


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('--registry', type=Path, required=True)
    plan.add_argument('--candidate', required=True)
    plan.add_argument('--opponent', action='append', help='Repeat to select opponents; defaults to permitted pools')
    plan.add_argument('--mode', choices=MODES, default='development')
    plan.add_argument('--purpose', choices=PURPOSES, default='development')
    plan.add_argument('--seed', type=int, default=20261010)
    plan.add_argument('--games', type=int, default=8)
    plan.add_argument('--total-ms', type=float, default=60000, help='Remaining total per player; -1 for capped unlimited')
    plan.add_argument('--move-cap', type=int, default=1000)
    plan.add_argument('--openings', type=Path, help='JSON list of legal move sequences')
    plan.add_argument('--fixture', type=Path, help='JSON object containing board and explicit side_to_move')
    plan.add_argument('--startup-ms', type=float, default=5000)
    plan.add_argument('--cleanup-ms', type=float, default=500)
    plan.add_argument('--unlimited-call-ms', type=float, default=1000)
    plan.add_argument('--output-bytes', type=int, default=16384)
    plan.add_argument('--diagnostics', action='store_true')
    plan.add_argument('--output', type=Path, required=True)
    run = commands.add_parser('run')
    run.add_argument('--plan', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True, help='New directory for manifest, job records and results')
    # AI-written by OpenAI Codex, for issue #28.
    score = commands.add_parser('score', help='Score saved raw results, including partial runs')
    score.add_argument('--plan', type=Path, required=True)
    score.add_argument('--results', type=Path, required=True)
    score.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'score':
            report = score_experiment(ExperimentPlan.load(args.plan),
                json.loads(args.results.read_text(encoding='utf-8')))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            save_new_json(args.output, report)
            print(json.dumps({'matches': len(report['matches']),
                              'unresolved': sum(not m['complete'] for m in report['matches'])}))
            return
        if args.command == 'run':
            result = run_experiment(ExperimentPlan.load(args.plan), output=args.output)
            print(json.dumps(result['counts']))
            return
        registry = json.loads(args.registry.read_text(encoding='utf-8'))
        if registry['format'] != 'omok-registry-v1':
            raise ValueError('Unsupported registry format.')
        entries = [Entry.from_record(r) for r in registry['entries']]
        catalog = {e.data['logical_id']: e for e in entries}
        if len(catalog) != len(entries):
            raise ValueError('Duplicate registry logical ID.')
        snapshot = PoolSnapshot.from_record(registry['pool_snapshot'])
        for records in registry['pool_snapshot']['pools'].values():
            for record in records:
                if catalog[record['logical_id']].identity != record['identity']:
                    raise ValueError('Catalog and pool snapshot disagree.')
        fixture = None
        if args.fixture:
            start = json.loads(args.fixture.read_text(encoding='utf-8'))
            fixture = Position(start['board'], start['side_to_move'])
        resolved = ExperimentPlan.resolve(catalog[args.candidate], snapshot,
            mode=args.mode, opponents=args.opponent, purpose=args.purpose, seed=args.seed,
            games_per_opponent=args.games, total_ms=None if args.total_ms == -1 else args.total_ms,
            move_cap=args.move_cap, fixture=fixture,
            openings=json.loads(args.openings.read_text(encoding='utf-8')) if args.openings else None,
            diagnostics=args.diagnostics, supervision=Supervision(startup_ms=args.startup_ms,
                cleanup_ms=args.cleanup_ms, unlimited_call_ms=args.unlimited_call_ms,
                output_bytes=args.output_bytes))
        resolved.save(args.output)
        print(json.dumps({'identity': resolved.identity, 'games': len(resolved.data['jobs'])}))
    except (ValueError, TypeError, KeyError, IndexError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
