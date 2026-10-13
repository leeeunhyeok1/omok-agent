# AI-written by OpenAI Codex for issue #45.
"""Durable repeated optimization using the existing Phase 5 stage contracts."""
from collections.abc import Callable
import json
import os
from math import isfinite
from pathlib import Path
import random
import shutil
import subprocess
import sys
from time import monotonic
from typing import Any
from uuid import uuid4

from offline import confirmation, gates, league, promotion, screening
from offline.batches import Checkpoint, atomic_json, owner, verify_versions
from offline.champions import ChampionStore
from offline.experiments import ExperimentPlan, execution_conditions, run_experiment, save_new_json
from offline.optimizer import read_envelope
from offline.proposals import ProposalPolicy, generate
from offline.registry import Entry, PoolSnapshot, ROOT, canonical, default_catalog, digest, source_snapshot
from offline.reviews import review_batch

FORMAT = 'omok-evolution-v1'
SUITE = ('tests/test_tactics.py', 'tests/test_simulator.py', 'tests/test_iterative.py',
         'tests/test_transposition.py', 'tests/test_evaluation.py', 'tests/test_threat_effects.py')
SELECTION = 'incumbent elite plus best advanced training fitness; identity tie break; no validation fitness'


def starter_policy(incumbent: Entry) -> dict[str, Any]:
    """Conservative local starter; budgets are declarations, not strength claims."""
    training = dict(opponents={'smoke': 4, 'synthetic-aggressive': 4},
        opponent_weights={'smoke': 1, 'synthetic-aggressive': 1},
        family_weights={'random-smoke': 1, 'line-pattern': 1}, total_ms=5000,
        move_cap=100, seed=45001)
    return {'format': FORMAT, 'population_size': 2, 'parent_count': 2, 'seed': 45,
        'selection': SELECTION, 'no_survivors': 'continue with incumbent',
        'exhaustion': 'stop if no proposals; record partial populations',
        'historical_gaps': 'stop after recorded round; do not erase obligations',
        'validation_every': 2, 'workers': 1, 'gate_timeout_seconds': 30,
        'seed_schedule': 'stage seed plus round index; openings remain stage-specific',
        'repeat_configurations': 'allowed across rounds with fresh seeded jobs; deduplicate within population and against parents',
        'resource_basis': 'Issue #36 measured 0.415 slots/s, 0.277 completed games/s under reduced clocks; start with one worker and measure locally',
        'proposal': ProposalPolicy.for_parent(incumbent, batch='evaluation', groups=['material']).data,
        'screening': screening.ScreeningPolicy.create(**training).data,
        'league': league.LeaguePolicy.create(screening=screening.ScreeningPolicy.create(**training).data).data,
        'incumbent_games': 16, 'historical_games': 4,
        'confirmation': confirmation.ConfirmationPolicy.create(
            screening=screening.ScreeningPolicy.create(**(training | {'seed': 45002})).data).data,
        'promotion': promotion.PromotionPolicy.create(validation={'synthetic-defensive': 4},
            official_opponents=['smoke']).data,
        'screening_openings': [[], [[9, 9], [9, 10]]],
        'league_openings': [[], [[9, 9], [9, 10]]],
        'confirmation_openings': [[[8, 8], [8, 9]], [[10, 10], [10, 11]]],
        'validation_openings': [[], [[9, 9], [9, 10]]],
        'prior_exposures': [{'source': 'docs/phase-04-handoff.md and docs/verification/issue-42.md',
            'details': 'Validation already development-exposed; earlier counts retained in those reports.'}]}


def validate_policy(p: dict[str, Any]) -> None:
    if p['format'] != FORMAT or p['selection'] != SELECTION:
        raise ValueError('Unsupported evolution/selection policy.')
    if p['seed_schedule'] != 'stage seed plus round index; openings remain stage-specific' or not p['resource_basis']:
        raise ValueError('Declare the seed schedule and measured resource basis.')
    if p['repeat_configurations'] != 'allowed across rounds with fresh seeded jobs; deduplicate within population and against parents':
        raise ValueError('Unsupported repeated-configuration policy.')
    for name, limit in (('population_size', 1000), ('parent_count', 1000), ('workers', 64)):
        if type(p[name]) is not int or not 1 <= p[name] <= limit:
            raise ValueError('Invalid ' + name)
    if type(p['seed']) is not int or type(p['validation_every']) is not int or p['validation_every'] < 1:
        raise ValueError('Declare seed and positive validation cadence.')
    for name in ('incumbent_games', 'historical_games'):
        if type(p[name]) is not int or p[name] < 2 or p[name] % 2:
            raise ValueError('Declare balanced incumbent/history coverage.')
    if p['incumbent_games'] < 16:
        raise ValueError('Promotion requires at least sixteen incumbent games.')
    if (p['no_survivors'] != 'continue with incumbent' or
            p['exhaustion'] != 'stop if no proposals; record partial populations' or
            p['historical_gaps'] != 'stop after recorded round; do not erase obligations'):
        raise ValueError('Unsupported failure/exhaustion handling.')
    if (type(p['gate_timeout_seconds']) not in (int, float) or
            not isfinite(p['gate_timeout_seconds']) or not 0 < p['gate_timeout_seconds'] <= 60):
        raise ValueError('Gate timeout must be in (0, 60].')
    ProposalPolicy(canonical(p['proposal']))
    screening.ScreeningPolicy(canonical(p['screening']))
    league.LeaguePolicy(canonical(p['league']))
    confirmation.ConfirmationPolicy(canonical(p['confirmation']))
    promotion.PromotionPolicy(canonical(p['promotion']))
    for key in ('screening_openings', 'league_openings', 'confirmation_openings', 'validation_openings'):
        if not p[key]:
            raise ValueError('Declare opening variation.')
        from omok.simulator import Position
        for opening in p[key]:
            position = Position.empty()
            for move in opening:
                position = position.play(move).position
            if position.outcome != 'ongoing':
                raise ValueError('Opening must remain playable.')


def initialize(output: Path, *, policy: dict[str, Any] | None = None,
               incumbent: Entry | None = None, snapshot: PoolSnapshot | None = None,
               history: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog, default_pool = default_catalog()
    incumbent = incumbent or catalog['phase3-material']
    snapshot = snapshot or default_pool
    p = policy or starter_policy(incumbent)
    validate_policy(p)
    snapshot.validate_optimizer_candidate(incumbent)
    for entry in league.validate_history(history or {'champions': []}):
        snapshot.validate_optimizer_candidate(entry)
    suite_sources = source_snapshot(ROOT, SUITE)
    basis: dict[str, Any] = {'format': FORMAT, 'policy': p, 'incumbent': incumbent.record(),
        'snapshot': snapshot.record(), 'history': history or {'champions': []},
        'sources': source_snapshot(ROOT, ('omok', 'offline')),
        'tactical_suite': {'sources': suite_sources, 'identity': digest(suite_sources)}}
    # Resolve all pool and role assignments before proposing or dispatching anything.
    for name in ('screening', 'league', 'confirmation'):
        screen = p[name] if name == 'screening' else p[name]['screening']
        screening.build_stage(screening.ScreeningPolicy(canonical(screen)), incumbent, [], snapshot,
                              openings=p[name + '_openings'])
    for official in (False, True):
        promotion.check_stage(p['promotion'], [incumbent], incumbent.identity, snapshot, {}, official=official)
    rng = random.Random(p['seed'])
    output.mkdir(parents=True, exist_ok=False)
    with owner(output):
        atomic_json(output / 'evolution.json', {'identity': digest(basis), 'data': basis})
        ChampionStore(output / 'champions').initialize(incumbent, context={
            'tactical_suite': basis['tactical_suite'], 'run_identity': digest(basis),
            'limitations': 'Frozen baseline; optimization establishes no initial strength gain'},
            reason='Frozen evolution incumbent', history=basis['history'],
            history_period=p['league']['history_period'], history_slots=p['league']['history_slots'])
        state = {'format': FORMAT, 'basis_identity': digest(basis), 'rng_state': rng.getstate(),
            'parents': [incumbent.record()], 'rounds': [], 'segments': [], 'stopped': None}
        write_state(output, state)
    return status(output)


def write_state(output: Path, state: dict[str, Any]) -> None:
    atomic_json(output / 'evolution-checkpoint.json', {'sha256': digest(state), 'data': state})


def status(output: Path) -> dict[str, Any]:
    basis = read_envelope(output / 'evolution.json', 'identity')
    state = read_envelope(output / 'evolution-checkpoint.json', 'sha256')
    validate_policy(basis['policy'])
    if state['format'] != FORMAT or state['basis_identity'] != digest(basis):
        raise ValueError('Evolution checkpoint/policy mismatch.')
    store = ChampionStore(output / 'champions').load()
    return dict(state, incumbent=store['versions'][store['current']]['bundle']['entry'],
                history=ChampionStore(output / 'champions').history())


def publish_directory(path: Path, build: Callable[[Path], Any]) -> None:
    """Uncommitted preparation may repeat; a published immutable declaration cannot."""
    temporary = path.with_name('.' + path.name + '-preparing')
    if temporary.exists():
        shutil.rmtree(temporary)
    try:
        build(temporary)
        if path.exists():
            # Recover the rename-to-controller-commit window without trusting a foreign declaration.
            for artifact in temporary.rglob('*.json'):
                saved = path / artifact.relative_to(temporary)
                if not saved.is_file() or json.loads(saved.read_text()) != json.loads(artifact.read_text()):
                    raise ValueError('Conflicting prepared artifact: ' + str(saved))
        else:
            temporary.rename(path)
            try:
                descriptor = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            except OSError:
                # Same directory-durability limitation as the existing atomic writer.
                pass
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


class Invocation:
    """One dispatch budget shared across every round, stage and retry."""
    def __init__(self, games: int, seconds: float, stop: Callable[[], bool] | None,
                 progress: Callable[[dict[str, Any]], None] | None):
        if type(games) is not int or games < 0 or type(seconds) not in (int, float) or not isfinite(seconds) or seconds < 0:
            raise ValueError('Declare nonnegative finite invocation bounds.')
        self.games, self.deadline, self.stop, self.progress = games, monotonic() + seconds, stop, progress
        self.dispatched = 0
        self.reason: str | None = None

    def remaining(self) -> float:
        return max(0., self.deadline - monotonic())

    def stopped(self) -> bool:
        if self.reason:
            return True
        if self.stop and self.stop():
            self.reason = 'graceful stop'
        elif self.remaining() == 0:
            self.reason = 'time bound'
        elif self.dispatched >= self.games:
            self.reason = 'game bound'
        return self.reason is not None


def stage_definition(directory: Path, name: str) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    if name == 'screening':
        record = screening.load_stage(directory)
        stages = [record]
        retries = record['policy']['policy']['infrastructure_retries']
    elif name == 'league':
        record = league.load(directory)
        stages = [record['screening']]
        retries = record['policy']['screening']['infrastructure_retries']
    elif name == 'confirmation':
        record = confirmation.load(directory)
        stages = [record['stage']]
        retries = record['policy']['screening']['infrastructure_retries']
    else:
        record = promotion.load(directory)
        stages = [record['validation'], record['official']]
        retries = record['policy']['infrastructure_retries']
    return record, stages, retries


def stage_checkpoints(directory: Path, name: str, saved: dict[str, Any]) -> dict[str, Checkpoint]:
    record, stages, retries = stage_definition(directory, name)
    if digest(record) != saved['identity']:
        raise ValueError('Stage declaration conflicts with controller checkpoint.')
    checkpoints = {}
    prior_raw = dict(saved['raw'])
    if name != 'screening':
        filename = 'eligibility' if name == 'checks' else name
        evidence_path = directory / (filename + '-results.json')
        if evidence_path.exists():
            exported = read_envelope(evidence_path, 'identity')
            binding = 'check_identity' if name == 'checks' else 'confirmation_identity'
            if (name == 'league' and exported['stage'] != record) or (name != 'league' and exported[binding] != digest(record)):
                raise ValueError('Foreign exported stage evidence.')
            # Both controller and child-result exports are rollback guards.
            for key, raw in exported['raw'].items():
                if key not in prior_raw or len(raw.get('attempts', [])) >= len(prior_raw[key].get('attempts', [])):
                    prior_raw[key] = raw
    for stage in stages:
        for member in stage['members']:
            for r in member['plans']:
                plan = ExperimentPlan.from_record(r)
                verify_versions(plan)
                child = directory / plan.identity
                prior = prior_raw.get(plan.identity)
                if prior and not (child / 'checkpoint.json').exists():
                    raise ValueError('Missing authoritative child checkpoint.')
                if not (child / 'checkpoint.json').exists():
                    # Only a manifest may survive initialization before the first durable attempt.
                    if child.exists() and any(child.glob('*.json')):
                        if {p.name for p in child.glob('*.json')} != {'manifest.json'} or ExperimentPlan.load(child / 'manifest.json').identity != plan.identity:
                            raise ValueError('Conflicting incomplete child initialization.')
                    resume = False
                else:
                    resume = True
                child.mkdir(exist_ok=True)
                with owner(child):
                    cp = Checkpoint(plan, child, resume, retries)
                    if not cp.data['segments']:
                        cp.data['segments'].append({'id': uuid4().hex,
                            'conditions': execution_conditions(1, 'not dispatched'),
                            'changed_conditions': [], 'stop_reason': 'not dispatched'})
                        cp.flush()
                if prior:
                    retained = {a['attempt_id']: a for a in cp.data['attempts']}
                    for attempt in prior.get('attempts', []):
                        current = retained.get(attempt['attempt_id'])
                        if current is None or any(current.get(k) != v for k, v in attempt.items() if k not in ('state', 'reason')) or (attempt['state'] != 'running' and current != attempt):
                            raise ValueError('Prior attempt lost or changed.')
                    segments = {s['id']: s['conditions'] for s in cp.data['segments']}
                    if any(segments.get(s['id']) != s['conditions'] for s in prior.get('segments', [])):
                        raise ValueError('Prior execution conditions lost.')
                checkpoints[plan.identity] = cp
    return checkpoints


def collect_stage(directory: Path, name: str, checkpoints: dict[str, Checkpoint]) -> tuple[dict[str, Any], dict[str, Any], bool]:
    record, stages, _ = stage_definition(directory, name)
    raw = {key: cp.report() for key, cp in checkpoints.items()}
    vetoed = vetoed_plans(stages)
    complete = not any(cp.retryable(j) for key, cp in checkpoints.items() if key not in vetoed for j in cp.jobs)
    evidence: dict[str, Any] | None
    if name == 'screening':
        report = screening.assess(directory, raw)
        evidence = None
    elif name == 'league':
        report = league.assess(directory, raw)
        evidence = {'stage': record, 'raw': raw}
    elif name == 'confirmation':
        report = confirmation.assess(directory, raw)
        evidence = {'confirmation_identity': digest(record), 'raw': raw}
    else:
        report = promotion.assess(directory, raw)
        evidence = {'check_identity': digest(record), 'raw': raw}
    if evidence is not None:
        filename = 'eligibility' if name == 'checks' else name
        atomic_json(directory / (filename + '-results.json'), {'identity': digest(evidence), 'data': evidence})
    atomic_json(directory / (('eligibility' if name == 'checks' else name) + '-report.json'), report)
    return raw, report, complete


def vetoed_plans(stages: list[dict[str, Any]]) -> set[str]:
    return {p['identity'] for stage in stages for member in stage['members']
            if any(g['status'] == 'fail' for g in member['gates']) for p in member['plans']}


def execute_stage(output: Path, directory: Path, name: str, saved: dict[str, Any], state: dict[str, Any],
                  budget: Invocation, *, workers: int, contention: str, conditions: dict[str, Any] | None) -> None:
    cps = stage_checkpoints(directory, name, saved)
    record, stages, retries = stage_definition(directory, name)
    vetoed = vetoed_plans(stages)
    official_ids = {p['identity'] for m in record['official']['members'] for p in m['plans']} if name == 'checks' else set()
    try:
        for key, cp in cps.items():
            if key in vetoed:
                continue
            if not any(cp.retryable(j) for j in cp.jobs):
                continue
            if budget.stopped():
                break
            if key in official_ids:
                if conditions is None:
                    budget.reason = 'official conditions required'
                    break
                promotion.check_conditions(conditions)
            before = len(cp.data['attempts'])
            try:
                run_experiment(cp.plan, output=cp.output, resume=True,
                    max_jobs=budget.games - budget.dispatched, max_seconds=budget.remaining(),
                    stop_requested=budget.stop, workers=1 if key in official_ids else workers,
                    contention=canonical(conditions) if key in official_ids else contention,
                    infrastructure_retries=retries, progress=budget.progress)
            finally:
                with owner(cp.output):
                    cps[key] = Checkpoint(cp.plan, cp.output, True, retries)
                budget.dispatched += len(cps[key].data['attempts']) - before
                # Commit authoritative attempts promptly. Assess the whole barrier once,
                # rather than repeatedly rescoring every member after each child plan.
                saved['raw'][key] = cps[key].report()
                write_state(output, state)
            reason = cps[key].data['segments'][-1].get('stop_reason')
            if reason in ('keyboard interrupt', 'graceful stop', 'batch time bound'):
                budget.reason = reason
                break
    finally:
        saved['raw'], saved['report'], saved['complete'] = collect_stage(directory, name, cps)
        write_state(output, state)


def run(output: Path, *, max_games: int, max_seconds: float, max_rounds: int | None = None,
        workers: int | None = None, stop_requested: Callable[[], bool] | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
        contention: str = 'external contention uncontrolled', conditions: dict[str, Any] | None = None,
        interrupt: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Continue pending work or automatically create successive immutable rounds."""
    budget = Invocation(max_games, max_seconds, stop_requested, progress)
    if max_rounds is not None and (type(max_rounds) is not int or max_rounds < 0):
        raise ValueError('Round bound must be a nonnegative integer.')
    if conditions is not None:
        promotion.check_conditions(conditions)
    with owner(output):
        basis = read_envelope(output / 'evolution.json', 'identity')
        state = read_envelope(output / 'evolution-checkpoint.json', 'sha256')
        status(output)
        p = basis['policy']
        if p['proposal']['runtime'] != sys.version:
            raise ValueError('Incompatible runtime; initialize a new run.')
        worker_count = p['workers'] if workers is None else workers
        if type(worker_count) is not int or not 1 <= worker_count <= 64 or not contention.strip():
            raise ValueError('Invalid worker/contention declaration.')
        if source_snapshot(ROOT, ('omok', 'offline')) != basis['sources'] or source_snapshot(ROOT, SUITE) != basis['tactical_suite']['sources']:
            raise ValueError('Incompatible source/tactical suite; initialize a new run.')
        ProposalPolicy(canonical(p['proposal']))
        store = ChampionStore(output / 'champions')
        # Validate ALL saved children before dispatch, including earlier eliminated candidates.
        for i, r in enumerate(state['rounds']):
            if r['index'] != i:
                raise ValueError('Round sequence mismatch.')
            root = output / 'rounds' / str(i)
            if r['stage'] == 'committed' and 'review_identity' in r:
                if digest(json.loads((root / 'review.json').read_text())) != r['review_identity']:
                    raise ValueError('Committed review changed.')
            if 'population' in r and json.loads((root / 'population/proposals.json').read_text()) != r['population']:
                raise ValueError('Immutable population changed.')
            for name, saved in r['stages'].items():
                cps = stage_checkpoints(root / name, name, saved)
                raw, report, complete = collect_stage(root / name, name, cps)
                if saved['complete'] and (not complete or report != saved['report']):
                    raise ValueError('Committed stage decision changed.')
                saved.update(raw=raw, report=report, complete=complete)
        if state['rounds'] and state['rounds'][-1]['stage'] == 'committed':
            current = store.load()
            store.export(output / 'exports' / (current['current'] + '.json'))
        segment: dict[str, Any] = {'conditions': execution_conditions(worker_count, contention), 'official_conditions': conditions,
                   'max_games': max_games, 'max_seconds': max_seconds, 'max_rounds': max_rounds,
                   'attempts': 0, 'stop_reason': None}
        state['segments'].append(segment)
        start = monotonic()
        completed = 0

        def commit(event: str) -> None:
            write_state(output, state)
            if progress:
                progress({'round': len(state['rounds']) - 1, 'event': event, 'attempts': budget.dispatched,
                          'checkpoint': str(output / 'evolution-checkpoint.json')})
            if interrupt:
                interrupt(event)

        def stage(r: dict[str, Any], name: str, build: Callable[[Path], Any]) -> dict[str, Any]:
            directory = output / 'rounds' / str(r['index']) / name
            if name not in r['stages']:
                publish_directory(directory, build)
                record, _, _ = stage_definition(directory, name)
                r['stages'][name] = {'identity': digest(record), 'raw': {}, 'report': {}, 'complete': False}
                r['stage'] = name
                commit(name + ' prepared')
            saved = r['stages'][name]
            if not saved['complete']:
                execute_stage(output, directory, name, saved, state, budget, workers=worker_count,
                              contention=contention, conditions=conditions)
                if saved['complete']:
                    commit(name + ' complete')
            return saved

        try:
            while not state['stopped']:
                if max_rounds is not None and completed >= max_rounds:
                    budget.reason = 'round bound'
                    break
                if budget.stopped():
                    break
                if not state['rounds'] or state['rounds'][-1]['stage'] == 'committed':
                    rng = random.Random()
                    rng_state = state['rng_state']
                    rng.setstate((rng_state[0], tuple(rng_state[1]), rng_state[2]))
                    seed = rng.getrandbits(128)
                    current = store.load()
                    incumbent = current['versions'][current['current']]['bundle']['entry']
                    r = {'index': len(state['rounds']), 'seed': seed, 'parents': state['parents'],
                         'incumbent': incumbent, 'history': store.history(), 'stage': 'proposal',
                         'stages': {}, 'gates': {}, 'decision': None}
                    state['rng_state'] = rng.getstate()
                    state['rounds'].append(r)
                    commit('round created')
                r = state['rounds'][-1]
                root = output / 'rounds' / str(r['index'])
                root.mkdir(parents=True, exist_ok=True)
                incumbent = Entry.from_record(r['incumbent'])
                snapshot = PoolSnapshot.from_record(basis['snapshot'])
                proposal_path = output / 'proposal-policy.json'
                if not proposal_path.exists():
                    ProposalPolicy(canonical(p['proposal'])).save(proposal_path)
                elif ProposalPolicy.load(proposal_path).data != p['proposal']:
                    raise ValueError('Conflicting proposal policy.')
                if 'population' not in r:
                    publish_directory(root / 'population', lambda path: generate(proposal_path,
                        [Entry.from_record(e) for e in r['parents']], seed=r['seed'],
                        count=p['population_size'], output=path))
                    r['population'] = json.loads((root / 'population/proposals.json').read_text())
                    commit('proposal persisted')
                candidates = [Entry.from_record(c['entry']) for c in r['population']['candidates']]
                if not candidates:
                    r['decision'] = {'reason': 'proposal exhaustion', 'parents': [incumbent.record()], 'promotion': False}
                    review: dict[str, Any] = {'format': 'omok-batch-review-v1', 'retained_incumbent': incumbent.identity,
                        'strongest_verified': incumbent.identity, 'strongest_screened': None,
                        'promotion': {'performed': False, 'status': 'retain incumbent: proposal exhaustion'},
                        'candidates': {}, 'resources': [], 'failures': [],
                        'next_bounded_experiment': {'action': 'initialize another predeclared proposal policy',
                            'max_failures': 0, 'max_positions': 0, 'proposed_max_new_games': 0},
                        'source': {'kind': 'proposal', 'stage_identity': digest(r['population']),
                            'raw_identity': digest({}), 'attribution': 'AI-written OpenAI Codex; no games dispatched'},
                        'limitations': 'Bounded proposal exhaustion; prior incumbent retained without new strength evidence.'}
                    atomic_json(root / 'review.json', review)
                    r['review_identity'] = digest(review)
                    r['stage'] = 'committed'
                    state['parents'] = r['decision']['parents']
                    state['stopped'] = 'proposal exhaustion'
                    commit('round committed')
                    break
                for entry in [incumbent] + candidates:
                    snapshot.validate_optimizer_candidate(entry)
                    if entry.identity not in r['gates']:
                        if budget.stopped():
                            break
                        try:
                            evidence = gates.evaluate(entry, basis['tactical_suite']['identity'],
                                timeout=min(p['gate_timeout_seconds'], budget.remaining()))
                        except subprocess.TimeoutExpired:
                            if budget.remaining() == 0:
                                budget.reason = 'time bound'
                                break
                            evidence = [dict(check=c, status='fail', samples=1,
                                suite_identity=basis['tactical_suite']['identity'], evidence={'failure': 'gate timeout'})
                                for c in screening.GATES]
                        r['gates'][entry.identity] = evidence
                        commit('gate persisted')
                if budget.stopped():
                    break
                # Each stage policy is saved before its plans. Preparation is atomic as a directory.
                def screen_build(path: Path) -> None:
                    path.mkdir()
                    policy_path = path / 'policy.json'
                    screening.ScreeningPolicy(canonical(p['screening'] | {'seed': p['screening']['seed'] + r['index']})).save(policy_path)
                    record = screening.build_stage(screening.ScreeningPolicy.load(policy_path), incumbent,
                        candidates, snapshot, openings=p['screening_openings'], gates=r['gates'])
                    save_new_json(path / 'stage.json', {'identity': digest(record), 'stage': record})
                screened = stage(r, 'screening', screen_build)
                if not screened['complete']:
                    break
                def league_build(path: Path) -> None:
                    lp = dict(p['league'])
                    counts = dict(lp['screening']['opponents'])
                    weights = dict(lp['screening']['opponent_weights'])
                    families = dict(lp['screening']['family_weights'])
                    for entry, count in [(incumbent, p['incumbent_games'])] + [
                            (Entry.from_record(b['entry']), p['historical_games']) for b in r['history']['champions']]:
                        counts[entry.data['logical_id']] = count
                        weights[entry.data['logical_id']] = 1
                        families[entry.data['family']] = 1
                    lp.update(history_period=r['history']['history_period'], history_slots=r['history']['history_slots'],
                              screening=lp['screening'] | {'opponents': counts, 'opponent_weights': weights, 'family_weights': families})
                    policy_path = root / 'league-policy.json'
                    if not policy_path.exists():
                        league.LeaguePolicy(canonical(lp)).save(policy_path)
                    elif json.loads(policy_path.read_text())['policy'] != lp:
                        raise ValueError('Conflicting resolved league policy.')
                    league.prepare(policy_path, incumbent, snapshot, history=r['history'],
                        rungs=[(root / 'screening', screened['raw'])], output=path, round_index=r['index'],
                        previous_rounds=[output / 'rounds' / str(i) / 'league' for i in range(r['index'])],
                        openings=p['league_openings'], gates=r['gates'])
                broader = stage(r, 'league', league_build)
                if not broader['complete']:
                    break
                confirmed = None
                if broader['report']['advanced']:
                    def confirmation_build(path: Path) -> None:
                        policy_path = root / 'confirmation-policy.json'
                        cp = p['confirmation'] | {'screening': p['confirmation']['screening'] | {
                            'seed': p['confirmation']['screening']['seed'] + r['index']}}
                        if not policy_path.exists():
                            confirmation.ConfirmationPolicy(canonical(cp)).save(policy_path)
                        elif confirmation.ConfirmationPolicy.load(policy_path).data != cp:
                            raise ValueError('Conflicting resolved confirmation policy.')
                        confirmation.prepare(policy_path, selection=root / 'league', selection_raw=broader['raw'],
                                             output=path, openings=p['confirmation_openings'])
                    confirmed = stage(r, 'confirmation', confirmation_build)
                    if not confirmed['complete']:
                        break
                finalists = bool(confirmed and confirmed['report']['advanced'])
                checks = None
                if finalists or (r['index'] + 1) % p['validation_every'] == 0:
                    def checks_build(path: Path) -> None:
                        policy_path = root / 'promotion-policy.json'
                        pp = p['promotion'] | {'seed': p['promotion']['seed'] + r['index']}
                        if not policy_path.exists():
                            promotion.PromotionPolicy(canonical(pp)).save(policy_path)
                        elif promotion.PromotionPolicy.load(policy_path).data != pp:
                            raise ValueError('Conflicting resolved promotion policy.')
                        confirmed_record = confirmation.load(root / 'confirmation') if finalists else None
                        pool = PoolSnapshot.from_record(confirmed_record['stage']['pool_snapshot']) if confirmed_record else snapshot
                        promotion.prepare(policy_path, incumbent, pool, output=path,
                            confirmation=root / 'confirmation' if finalists else None,
                            confirmation_raw=confirmed['raw'] if finalists and confirmed else None,
                            prior_exposures=p['prior_exposures'], gates=r['gates'], openings=p['validation_openings'],
                            previous_checks=[output / 'rounds' / str(old['index']) / 'checks' for old in state['rounds'][:-1]
                                             if 'checks' in old['stages']])
                    checks = stage(r, 'checks', checks_build)
                    if not checks['complete']:
                        break
                transaction = store.promote(root / 'checks') if checks else None
                if transaction:
                    commit('promotion committed')
                current = store.load()
                elite = current['versions'][current['current']]['bundle']['entry']
                # Training barrier determines parents; validation values never enter this ranking.
                rank = broader['report']['candidates']
                ranked = sorted(broader['report']['advanced'], key=lambda i: (-rank[i]['fitness'], i))
                records = {c['entry']['identity']: c['entry'] for c in r['population']['candidates']}
                parents = [elite] + [records[i] for i in ranked if i != elite['identity']][:p['parent_count'] - 1]
                r['decision'] = {'parents': parents, 'training_advanced': ranked,
                    'screening': {i: {'status': c['status'], 'reasons': c['reasons']} for i, c in screened['report']['candidates'].items()},
                    'confirmation_advanced': confirmed['report']['advanced'] if confirmed else [],
                    'promotion': transaction, 'retained_incumbent': elite['identity'],
                    'reason': 'training barrier complete; retain incumbent when no eligible improvement',
                    'historical_gaps': broader['report']['historical_gaps'] + [
                        {'round_index': r['index'], 'identity': i} for i, c in broader['report']['history_coverage'].items()
                        if c['due'] and not c['complete']]}
                review = review_batch(screening.load_stage(root / 'screening'), screened['raw'], max_failures=1)
                review['retained_incumbent'] = elite['identity']
                review['strongest_verified'] = elite['identity']
                review['promotion'] = {'performed': bool(transaction and transaction['winner']),
                    'status': 'promoted' if transaction and transaction['winner'] else 'retain incumbent',
                    'decision': transaction or {}}
                atomic_json(root / 'review.json', review)
                r['review_identity'] = digest(review)
                state['parents'] = parents
                r['stage'] = 'committed'
                if r['decision']['historical_gaps']:
                    state['stopped'] = 'unresolved historical obligations'
                commit('round committed')
                store.export(output / 'exports' / (current['current'] + '.json'))
                completed += 1
        except KeyboardInterrupt:
            budget.reason = 'keyboard interrupt'
        finally:
            segment.update(attempts=budget.dispatched, wall_seconds=monotonic() - start,
                           stop_reason=state['stopped'] or budget.reason or 'pending stage')
            write_state(output, state)
        return status(output)
