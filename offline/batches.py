# AI-written by OpenAI Codex, for issue #29.
"""Single-owner, checksummed atomic checkpoints at completed-game boundaries."""
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from threading import Event
from time import monotonic, process_time
from typing import Any, Iterator
from uuid import uuid4

from offline.experiments import ExperimentPlan, execute_job, execution_conditions
from offline.registry import Entry, ROOT, checkpoint_archive, digest, source_snapshot


class BatchStopped(BaseException):
    """Cancellation unwinds player supervision without becoming a player failure."""


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    """Flush a complete file before atomic replacement on the same filesystem."""
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                prefix='.pending-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != 'nt':
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def owner(output: Path | None) -> Iterator[None]:
    if output is None:
        yield
        return
    with (output / '.owner').open('a+b') as stream:
        stream.write(b'0')
        stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                getattr(fcntl, 'flock')(stream.fileno(), getattr(fcntl, 'LOCK_EX') | getattr(fcntl, 'LOCK_NB'))
        except OSError as error:
            raise ValueError('Batch already has an authoritative owner.') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                getattr(fcntl, 'flock')(stream.fileno(), getattr(fcntl, 'LOCK_UN'))


def verify_versions(plan: ExperimentPlan) -> None:
    """Verify metadata/source bytes without importing or calling competitors."""
    entries = [plan.data['candidate']] + [j['opponent'] for j in plan.data['jobs']]
    for record in {r['identity']: r for r in entries}.values():
        data = Entry.from_record(record).data
        if data['runtime'] != sys.version or data['adapter_sources'] != source_snapshot(ROOT, ('offline',)):
            raise ValueError('Registered runtime or adapter version changed.')
        loader = data['loader']
        if loader['kind'] == 'checkpoint':
            # Frozen Git content is addressed by a full immutable commit.
            checkpoint_archive(loader['commit'], tuple(loader['paths']))
        else:
            root = ROOT / loader['root']
            if source_snapshot(root, tuple(data['source_paths'])) != data['sources']:
                raise ValueError('Registered source/configuration changed or missing.')


class Checkpoint:
    def __init__(self, plan: ExperimentPlan, output: Path | None, resume: bool,
                 retries: int | None):
        self.plan, self.output = plan, output
        self.jobs = {j['game_id']: j for j in plan.data['jobs']}
        if resume:
            assert output is not None
            if ExperimentPlan.load(output / 'manifest.json').identity != plan.identity:
                raise ValueError('Resume manifest/configuration/policy mismatch.')
            try:
                envelope = json.loads((output / 'checkpoint.json').read_text(encoding='utf-8'))
                self.data = envelope['data']
                if envelope['sha256'] != digest(self.data):
                    raise ValueError('Checkpoint digest mismatch.')
                self.validate()
                for game_id, record in self.data['results'].items():
                    path = output / (game_id + '.json')
                    if path.exists():
                        saved = json.loads(path.read_text(encoding='utf-8'))
                        if not any(a.get('result') == saved for a in self.data['attempts']
                                   if a['game_id'] == game_id):
                            raise ValueError('Conflicting exported result.')
            except (KeyError, TypeError, OSError, ValueError) as error:
                raise ValueError('Invalid or truncated authoritative checkpoint.') from error
            if retries is not None and retries != self.data['policy']['infrastructure_retries']:
                raise ValueError('Resume retry policy changed.')
            verify_versions(plan)
            for attempt in self.data['attempts']:
                if attempt['state'] == 'running':
                    attempt.update(state='interrupted', reason='uncommitted at resume')
        else:
            self.data = {'format': 'omok-batch-checkpoint-v1', 'manifest_identity': plan.identity,
                'policy': {'infrastructure_retries': retries or 0,
                           'interruption': 'restart uncommitted game with new attempt ID'},
                'attempts': [], 'results': {}, 'segments': []}
            if output is not None:
                atomic_json(output / 'manifest.json', plan.record())
        self.flush()

    def validate(self) -> None:
        data = self.data
        if data['format'] != 'omok-batch-checkpoint-v1' or data['manifest_identity'] != self.plan.identity:
            raise ValueError('Foreign checkpoint.')
        retries = data['policy']['infrastructure_retries']
        if type(retries) is not int or retries < 0:
            raise ValueError('Invalid retry policy.')
        ids = set()
        latest = {}
        for attempt in data['attempts']:
            if (attempt['game_id'] not in self.jobs or attempt['attempt_id'] in ids or
                    attempt['state'] not in ('running', 'interrupted', 'committed')):
                raise ValueError('Invalid attempt identity/state.')
            ids.add(attempt['attempt_id'])
            if attempt['state'] == 'committed':
                self.validate_result(attempt['game_id'], attempt['result'])
                if attempt['result']['attempt_id'] != attempt['attempt_id']:
                    raise ValueError('Attempt/result mismatch.')
                latest[attempt['game_id']] = attempt['result']
        if latest != data['results']:
            raise ValueError('Committed attempts are missing from authoritative results.')
        for game_id, record in data['results'].items():
            self.validate_result(game_id, record)
            matching = [a for a in data['attempts'] if a['game_id'] == game_id and a['state'] == 'committed']
            if not matching or matching[-1]['result'] != record:
                raise ValueError('Authoritative result disagrees with attempts.')

    def validate_result(self, game_id: str, record: dict[str, Any]) -> None:
        from offline.matches import game_score
        if game_id not in self.jobs or record['game_id'] != game_id:
            raise ValueError('Foreign result.')
        if not all(k in record for k in ('trace', 'error', 'status', 'preflight', 'exposure')):
            raise ValueError('Truncated result.')
        job = self.jobs[game_id]
        if any(record[k] != job[k] for k in ('match_id', 'slot', 'candidate_color')):
            raise ValueError('Result assignment changed.')
        score = game_score(job, record, self.plan.record())
        if 'validation_error' in score or record['status'] not in (
                'completed', 'failed', 'capped', 'setup_failed', 'supervisor_error'):
            raise ValueError('Invalid/truncated result trace.')

    def flush(self) -> None:
        if self.output is not None:
            atomic_json(self.output / 'checkpoint.json', {'data': self.data, 'sha256': digest(self.data)})

    def begin(self, game_id: str, segment: str) -> dict[str, Any]:
        attempt = {'game_id': game_id, 'attempt_id': uuid4().hex, 'segment': segment, 'state': 'running'}
        self.data['attempts'].append(attempt)
        self.flush()
        return attempt

    def commit(self, attempt: dict[str, Any], record: dict[str, Any]) -> None:
        if not any(attempt is saved for saved in self.data['attempts']):
            raise ValueError('Late result from foreign checkpoint owner.')
        if any(a is not attempt and a['game_id'] == attempt['game_id']
               for a in self.data['attempts'][self.data['attempts'].index(attempt) + 1:]):
            raise ValueError('Late result from superseded attempt.')
        self.validate_result(attempt['game_id'], record)
        record = {**record, 'attempt_id': attempt['attempt_id'], 'segment': attempt['segment']}
        if attempt['state'] == 'committed':
            if attempt['result'] != record:
                raise ValueError('Conflicting duplicate result.')
            return
        if attempt['state'] != 'running':
            raise ValueError('Late result for interrupted attempt.')
        attempt.update(state='committed', result=record)
        self.data['results'][attempt['game_id']] = record
        self.flush()

    def retryable(self, game_id: str) -> bool:
        record = self.data['results'].get(game_id)
        if record is None:
            return True
        # A cleanup error can retain a genuine player failure: never retry it away.
        trace = record['trace']
        if trace and (trace.get('prior_result', {}).get('status') == 'failed'):
            return False
        if record['status'] not in ('setup_failed', 'supervisor_error'):
            return False
        failures = sum(a['game_id'] == game_id and a['state'] == 'committed'
                       for a in self.data['attempts'])
        return failures <= self.data['policy']['infrastructure_retries']

    def reconcile_shutdown(self, attempt: dict[str, Any], reason: str,
                           evidence: dict[str, Any]) -> None:
        """Preserve a completed commit or interrupt an uncommitted attempt after cleanup."""
        if attempt['state'] == 'committed':
            # Ctrl+C can interrupt commit between attempt and result mutations.
            self.data['results'][attempt['game_id']] = attempt['result']
        else:
            attempt.update(state='interrupted', reason=reason, **evidence)

    def report(self) -> dict[str, Any]:
        from offline.matches import score_experiment
        records = [self.data['results'][j] for j in self.jobs if j in self.data['results']]
        counts = {key: 0 for key in ('completed', 'failed', 'capped', 'infrastructure_failed')}
        for record in records:
            bucket = record['status'] if record['status'] in counts else 'infrastructure_failed'
            counts[bucket] += 1
        counts.update(planned=len(self.jobs), pending=len(self.jobs) - len(records))
        result = {'format': 'omok-experiment-results-v1', 'manifest_identity': self.plan.identity,
            'conditions': self.data['segments'][-1]['conditions'], 'counts': counts, 'results': records,
            'attempts': self.data['attempts'], 'segments': self.data['segments']}
        result['match_scores'] = score_experiment(self.plan, result)
        if self.output is not None:
            for record in records:
                path = self.output / (record['game_id'] + '.json')
                if not path.exists() or json.loads(path.read_text(encoding='utf-8')) != record:
                    atomic_json(path, record)
            atomic_json(self.output / 'results.json', result)
            atomic_json(self.output / 'match-scores.json', result['match_scores'])
        return result


def run_batch(plan: ExperimentPlan, *, output: Path | None, resume: bool,
        max_jobs: int | None, max_seconds: float | None, stop_requested: Callable[[], bool] | None,
        progress: Callable[[dict[str, Any]], None] | None, infrastructure_retries: int | None,
        workers: int = 1, contention: str = 'external contention uncontrolled') -> dict[str, Any]:
    from math import isfinite
    for value, name in ((max_jobs, 'Job bound'), (infrastructure_retries, 'Retries')):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(name + ' must be a nonnegative integer.')
    if max_seconds is not None and (isinstance(max_seconds, bool) or not isfinite(max_seconds) or max_seconds < 0):
        raise ValueError('Batch seconds must be finite and nonnegative.')
    if resume and output is None:
        raise ValueError('Resume requires a saved output directory.')
    if type(workers) is not int or not 1 <= workers <= 64:
        raise ValueError('Workers must be an integer in 1..64.')
    if not isinstance(contention, str) or not contention.strip():
        raise ValueError('Describe execution contention.')
    plan = ExperimentPlan.from_record(plan.record())
    if output is not None:
        if resume:
            if not output.is_dir():
                raise ValueError('Missing batch directory.')
        else:
            output.mkdir(parents=True, exist_ok=False)
    with owner(output):
        checkpoint = Checkpoint(plan, output, resume, infrastructure_retries)
        observed = execution_conditions(workers, contention)
        previous = checkpoint.data['segments'][-1]['conditions'] if checkpoint.data['segments'] else None
        changes = [key for key in ('cpu', 'cpu_count', 'ram_bytes', 'machine', 'platform', 'python',
                   'implementation', 'affinity', 'workers', 'contention', 'start_method')
                   if previous is not None and previous.get(key) != observed.get(key)]
        segment: dict[str, Any] = {'id': uuid4().hex, 'conditions': observed, 'stop_reason': None,
                   'max_jobs': max_jobs, 'max_seconds': max_seconds, 'changed_conditions': changes,
                   'completion_order': [], 'peak_active_games': 0}
        checkpoint.data['segments'].append(segment)
        checkpoint.flush()
        start, cpu_start = monotonic(), process_time()
        deadline = None if max_seconds is None else start + max_seconds
        cancelled = Event()

        def check_stop() -> None:
            if stop_requested and stop_requested():
                raise BatchStopped('graceful stop')
            if deadline is not None and monotonic() >= deadline:
                raise BatchStopped('batch time bound')

        def worker_stop() -> None:
            if cancelled.is_set():
                raise BatchStopped('segment cancelled')
            if deadline is not None and monotonic() >= deadline:
                raise BatchStopped('batch time bound')

        def execute(job: dict[str, Any], queued: float) -> dict[str, Any]:
            started = monotonic()
            timing = {'queue_ms': (started - queued) * 1000}
            try:
                return_record = execute_job(plan, job, worker_stop)
            except Exception as error:
                # A supervisor defect is infrastructure evidence, never a player forfeit.
                return_record = {k: job[k] for k in ('game_id', 'match_id', 'slot', 'candidate_color')}
                return_record.update(status='supervisor_error', trace=None, preflight=[], exposure={
                    'kind': 'unknown-supervisor-failure', 'pool': job['pool']},
                    error={'type': type(error).__name__, 'message': str(error)})
                return_record['infrastructure_evidence'] = {key: getattr(error, key)
                    for key in ('interrupted_trace', 'interrupted_preflight') if hasattr(error, key)}
            except BaseException as error:
                timing['execution_ms'] = (monotonic() - started) * 1000
                setattr(error, 'scheduling', timing)
                raise
            timing['execution_ms'] = (monotonic() - started) * 1000
            return {**return_record, 'scheduling': timing}

        dispatched = 0
        active: dict[Future[dict[str, Any]], dict[str, Any]] = {}
        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='omok-game')
        try:
            while True:
                check_stop()
                busy = {a['game_id'] for a in active.values()}
                for job in plan.data['jobs']:
                    if len(active) >= workers or (max_jobs is not None and dispatched >= max_jobs):
                        break
                    if job['game_id'] in busy or not checkpoint.retryable(job['game_id']):
                        continue
                    check_stop()
                    attempt = checkpoint.begin(job['game_id'], segment['id'])
                    future = executor.submit(execute, job, start)
                    active[future] = attempt
                    busy.add(job['game_id'])
                    dispatched += 1
                    segment['peak_active_games'] = max(segment['peak_active_games'], len(active))
                if not active:
                    if max_jobs is not None and dispatched >= max_jobs:
                        segment['stop_reason'] = 'batch job bound'
                    break
                ready, _ = wait(active, timeout=0.05, return_when=FIRST_COMPLETED)
                for future in ready:
                    check_stop()
                    record = future.result()
                    attempt = active[future]
                    checkpoint.commit(attempt, record)
                    segment['completion_order'].append(attempt['game_id'])
                    del active[future]
                    report = checkpoint.report()
                    if progress:
                        progress(dict(report['counts']))
        except (BatchStopped, KeyboardInterrupt) as error:
            segment['stop_reason'] = str(error) or 'keyboard interrupt'
        finally:
            cancelled.set()
            executor.shutdown(wait=True, cancel_futures=True)
            for future, attempt in active.items():
                evidence = {}
                if not future.cancelled():
                    failure = future.exception()
                    if failure is None:
                        # A stop ends dispatch, not ownership of already verified evidence.
                        checkpoint.commit(attempt, future.result())
                        if attempt['game_id'] not in segment['completion_order']:
                            segment['completion_order'].append(attempt['game_id'])
                    else:
                        for key in ('interrupted_trace', 'interrupted_preflight', 'scheduling'):
                            if hasattr(failure, key):
                                evidence[key] = getattr(failure, key)
                checkpoint.reconcile_shutdown(attempt, segment['stop_reason'] or 'owner failure', evidence)
            segment.update(wall_seconds=monotonic() - start,
                           owner_cpu_seconds=process_time() - cpu_start)
            checkpoint.flush()
        report = checkpoint.report()
        if progress:
            progress(dict(report['counts']))
        return report
