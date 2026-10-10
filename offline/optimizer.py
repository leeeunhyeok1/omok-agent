# AI-written by OpenAI Codex, for issue #39.
"""Bounded, single-owner optimization of one immutable proposed cohort."""
from collections.abc import Callable
import json
from math import isfinite
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from offline.batches import Checkpoint, atomic_json, owner, verify_versions
from offline.experiments import ExperimentPlan, execution_conditions
from offline.proposals import ProposalPolicy, resolve_entry, genotype_identity
from offline.registry import Entry, canonical, digest
from offline.screening import assess, load_stage, validate_stage

FORMAT = 'omok-optimizer-run-v1'


def validate_manifest(data: dict[str, Any]) -> None:
    if data['format'] != FORMAT:
        raise ValueError('Unsupported optimizer format.')
    stage, population = data['stage'], data['population']
    validate_stage(stage)
    policy = ProposalPolicy(canonical(population['policy']))
    if policy.identity != population['policy_identity']:
        raise ValueError('Proposal policy mismatch.')
    if data['selection_policy'] != 'fixed cohort barrier; sorted identities; no automatic promotion or next generation':
        raise ValueError('Unsupported logical selection policy.')
    parent_ids = set()
    for parent_record in population['parents']:
        parent = Entry.from_record(parent_record['entry'])
        parent_ids.add(parent.identity)
        if parent_record['configuration'] != resolve_entry(parent):
            raise ValueError('Parent configuration mismatch.')
        if any(parent.data[k] != policy.data[p] for k, p in
               (('sources', 'engine_sources'), ('runtime', 'runtime'), ('dependencies', 'dependencies'))):
            raise ValueError('Population engine/runtime basis mismatch.')
    # Verify the actual immutable genotypes, including their retained engine basis.
    candidates = population['candidates']
    for candidate in candidates:
        entry = Entry.from_record(candidate['entry'])
        if genotype_identity(entry, resolve_entry(entry)) != candidate['genotype']:
            raise ValueError('Candidate genotype mismatch.')
        if candidate['parents'] != population['ancestry'][candidate['genotype']]:
            raise ValueError('Candidate ancestry mismatch.')
        if not candidate['parents'] or set(candidate['parents']) - parent_ids:
            raise ValueError('Unrecorded proposal parent.')
    expected = {c['entry']['identity'] for c in candidates} | {stage['incumbent']}
    if {m['entry']['identity'] for m in stage['members']} != expected:
        raise ValueError('Stage must evaluate exactly the proposed unique population and incumbent.')
    if stage['incumbent'] not in {p['entry']['identity'] for p in population['parents']}:
        raise ValueError('Incumbent must be a recorded proposal parent.')
    if len(expected) != len(candidates) + 1:
        raise ValueError('Duplicate population.')
    for key in ('initial_rng_state', 'final_rng_state'):
        import random
        state = population[key]
        random.Random().setstate((state[0], tuple(state[1]), state[2]))


def create(output: Path, *, proposals: Path, stage: Path) -> None:
    """Bind existing write-once proposals and stage before dispatching any work."""
    data = {'format': FORMAT, 'population': json.loads(proposals.read_text(encoding='utf-8')),
            'stage': load_stage(stage),
            'selection_policy': 'fixed cohort barrier; sorted identities; no automatic promotion or next generation'}
    validate_manifest(data)
    output.mkdir(parents=True, exist_ok=False)
    with owner(output):
        atomic_json(output / 'manifest.json', {'identity': digest(data), 'data': data})
        stage_data = data['stage']
        pending = [j['game_id'] for m in stage_data['members'] for p in m['plans'] for j in p['jobs']]
        state = {'format': FORMAT, 'manifest_identity': digest(data),
            'population': data['population'], 'incumbent': stage_data['incumbent'],
            'history': [stage_data['incumbent']], 'segments': [], 'decisions': [],
            'decision_committed': False, 'evidence': {}, 'exposure': [],
            'pending_jobs': pending, 'eliminated': [], 'progress': {
                'planned_jobs': len(pending), 'pending_jobs': len(pending), 'committed_jobs': 0, 'attempts': 0},
            'stage_assignments':
            {m['entry']['identity']: [p['identity'] for p in m['plans']] for m in stage_data['members']}}
        atomic_json(output / 'optimizer-checkpoint.json', {'data': state, 'sha256': digest(state)})


def read_envelope(path: Path, key: str) -> dict[str, Any]:
    try:
        envelope = json.loads(path.read_text(encoding='utf-8'))
        data = envelope['data']
        if envelope[key] != digest(data):
            raise ValueError('Digest mismatch.')
        return data
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError('Invalid authoritative artifact: ' + str(path)) from error


def run(output: Path, *, max_games: int | None = None, max_seconds: float | None = None,
        workers: int = 1, stop_requested: Callable[[], bool] | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
        contention: str = 'external contention uncontrolled') -> dict[str, Any]:
    """Resume saved jobs. Child checkpoints own attempts; this checkpoint owns decisions."""
    if max_games is not None and (type(max_games) is not int or max_games < 0):
        raise ValueError('Game bound must be a nonnegative integer.')
    if max_seconds is not None and (type(max_seconds) not in (int, float) or not isfinite(max_seconds) or max_seconds < 0):
        raise ValueError('Time bound must be finite and nonnegative.')
    if type(workers) is not int or not 1 <= workers <= 64 or not contention.strip():
        raise ValueError('Invalid execution conditions.')
    start = monotonic()
    with owner(output):
        manifest = read_envelope(output / 'manifest.json', 'identity')
        validate_manifest(manifest)
        identity = digest(manifest)
        stage = manifest['stage']
        # stage.json is a derived view for the existing assessment API.
        atomic_json(output / 'stage.json', {'identity': digest(stage), 'stage': stage})
        checkpoint_path = output / 'optimizer-checkpoint.json'
        state = read_envelope(checkpoint_path, 'sha256')
        if state['manifest_identity'] != identity or state['population'] != manifest['population']:
            raise ValueError('Optimizer configuration/population mismatch.')
        if state['incumbent'] != stage['incumbent'] or state['history'] != [stage['incumbent']]:
            raise ValueError('Invalid incumbent/history; promotion requires a separate transaction.')
        if state['format'] != FORMAT or state['stage_assignments'] != {
                m['entry']['identity']: [p['identity'] for p in m['plans']] for m in stage['members']}:
            raise ValueError('Stage assignment mismatch.')
        plans = [ExperimentPlan.from_record(r) for m in stage['members'] for r in m['plans']]
        retries = stage['policy']['policy']['infrastructure_retries']
        checkpoints = {}
        # Validate every authoritative child before allowing ANY new dispatch.
        for plan in plans:
            verify_versions(plan)
            directory = output / plan.identity
            if plan.identity in state['evidence'] and not (directory / 'checkpoint.json').is_file():
                raise ValueError('Missing authoritative child checkpoint.')
            if directory.exists() and not (directory / 'checkpoint.json').exists():
                # A crash before the first durable attempt leaves no work to repeat.
                if any(directory.glob('*.json')):
                    saved = ExperimentPlan.load(directory / 'manifest.json')
                    if saved.identity != plan.identity or set(p.name for p in directory.glob('*.json')) != {'manifest.json'}:
                        raise ValueError('Incomplete batch initialization contains conflicting artifacts.')
                resume = False
            else:
                resume = directory.exists()
            directory.mkdir(exist_ok=True)
            with owner(directory):
                checkpoints[plan.identity] = Checkpoint(plan, directory, resume, retries)
        observed = execution_conditions(workers, contention)
        previous = state['segments'][-1]['conditions'] if state['segments'] else {}
        segment = {'id': uuid4().hex, 'conditions': observed,
                   'changed_conditions': sorted(k for k in observed if previous and previous.get(k) != observed[k]),
                   'max_games': max_games, 'max_seconds': max_seconds, 'stop_reason': None}
        state['segments'].append(segment)

        def flush() -> None:
            atomic_json(checkpoint_path, {'data': state, 'sha256': digest(state)})

        def reconcile() -> None:
            raw = {key: cp.report() for key, cp in checkpoints.items()}
            state['evidence'] = {key: cp.data['results'] for key, cp in checkpoints.items()}
            state['exposure'] = [{'plan_identity': key, 'attempt_id': a['attempt_id'],
                'state': a['state'], 'exposure': a.get('result', {}).get('exposure'),
                'interrupted_preflight': a.get('interrupted_preflight'),
                'interrupted_trace': a.get('interrupted_trace')}
                for key, cp in checkpoints.items() for a in cp.data['attempts']]
            state['pending_jobs'] = [j['game_id'] for cp in checkpoints.values()
                                     for j in cp.plan.data['jobs'] if cp.retryable(j['game_id'])]
            state['progress'] = {'planned_jobs': sum(len(cp.jobs) for cp in checkpoints.values()),
                'committed_jobs': sum(len(cp.data['results']) for cp in checkpoints.values()),
                'pending_jobs': len(state['pending_jobs']),
                'attempts': sum(len(cp.data['attempts']) for cp in checkpoints.values())}
            report = assess(output, raw)
            if not state['pending_jobs']:
                decision = {'stage_identity': report['stage_identity'], 'advanced': report['advanced'],
                    'candidates': {k: {'status': v['status'], 'reasons': v['reasons']}
                                   for k, v in sorted(report['candidates'].items())},
                    'retained_incumbent': report['retained_incumbent'], 'promotion': False}
                if state['decision_committed'] and state['decisions'] != [decision]:
                    raise ValueError('Committed decision conflicts with authoritative evidence.')
                state['decisions'] = [decision]
                state['decision_committed'] = True
                state['eliminated'] = sorted(k for k, v in report['candidates'].items() if v['status'] == 'fail')
            elif state['decision_committed']:
                raise ValueError('Committed decision has pending work.')
            flush()  # Decision commit precedes its disposable report export.
            atomic_json(output / 'screening-report.json', report)

        # report() needs execution segments even for batches not yet dispatched.
        for cp in checkpoints.values():
            if not cp.data['segments']:
                cp.data['segments'].append({'id': segment['id'], 'conditions': observed,
                    'changed_conditions': [], 'stop_reason': 'not dispatched'})
                cp.flush()
        reconcile()
        dispatched = 0
        try:
            for plan in plans:
                if stop_requested and stop_requested():
                    segment['stop_reason'] = 'graceful stop'
                    break
                remaining = None if max_seconds is None else max(0., max_seconds - (monotonic() - start))
                if remaining == 0 or (max_games is not None and dispatched >= max_games):
                    segment['stop_reason'] = 'time bound' if remaining == 0 else 'game bound'
                    break
                cp = checkpoints[plan.identity]
                if not any(cp.retryable(j) for j in cp.jobs):
                    continue
                from offline.experiments import run_experiment
                before = len(cp.data['attempts'])
                run_experiment(plan, output=cp.output, resume=True,
                    max_jobs=None if max_games is None else max_games - dispatched,
                    max_seconds=remaining, stop_requested=stop_requested, workers=workers,
                    contention=contention, infrastructure_retries=retries,
                    progress=(lambda counts: progress({'plan_identity': plan.identity, **counts})) if progress else None)
                with owner(cp.output):
                    cp = Checkpoint(plan, cp.output, True, retries)
                checkpoints[plan.identity] = cp
                dispatched += len(cp.data['attempts']) - before
                reconcile()
                reason = cp.data['segments'][-1].get('stop_reason')
                if reason in ('keyboard interrupt', 'graceful stop', 'batch time bound'):
                    segment['stop_reason'] = reason
                    break
        except KeyboardInterrupt:
            segment['stop_reason'] = 'keyboard interrupt'
        finally:
            # Recover durable commits even if interruption occurred after child commit.
            for plan in plans:
                cp = checkpoints[plan.identity]
                with owner(cp.output):
                    checkpoints[plan.identity] = Checkpoint(plan, cp.output, True, retries)
            segment['wall_seconds'] = monotonic() - start
            reconcile()
        if progress:
            progress(state['progress'])
        return state


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    initialize = commands.add_parser('create')
    initialize.add_argument('--proposals', type=Path, required=True)
    initialize.add_argument('--stage', type=Path, required=True)
    initialize.add_argument('--output', type=Path, required=True)
    resume = commands.add_parser('run', help='Run or resume the exact saved cohort')
    resume.add_argument('--output', type=Path, required=True)
    resume.add_argument('--max-games', type=int, required=True)
    resume.add_argument('--max-seconds', type=float, required=True)
    resume.add_argument('--workers', type=int, default=1)
    resume.add_argument('--stop-file', type=Path)
    resume.add_argument('--contention', default='external contention uncontrolled')
    args = parser.parse_args()
    if args.command == 'create':
        create(args.output, proposals=args.proposals, stage=args.stage)
        print(canonical({'checkpoint': str(args.output / 'optimizer-checkpoint.json'), 'status': 'prepared'}))
    else:
        state = run(args.output, max_games=args.max_games, max_seconds=args.max_seconds,
            workers=args.workers, stop_requested=args.stop_file.exists if args.stop_file else None,
            contention=args.contention, progress=lambda counts: print(canonical(counts), flush=True))
        print(canonical({'checkpoint': str(args.output / 'optimizer-checkpoint.json'),
            'decision_committed': state['decision_committed'], 'progress': state['progress']}))


if __name__ == '__main__':
    main()
