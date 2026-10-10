# AI-written by OpenAI Codex, for issue #25.
"""Portable, persistent per-player subprocesses with bounded game execution."""
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
import json
import os
from math import floor, isfinite
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from threading import Lock, Thread
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any, IO

from offline.runner import captured_cells, rules_winner, state
from offline.worker_protocol import ProtocolError, receive, send
from omok.simulator import Position

FORMAT = 'omok-game-v4'
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PlayerSpec:
    """Importable factory called as factory(color, **options) inside the worker."""
    module: str
    factory: str
    options: dict[str, Any] = field(default_factory=dict)
    seed: int = 0


@dataclass(frozen=True)
class Supervision:
    startup_ms: float = 5000
    cleanup_ms: float = 500
    unlimited_call_ms: float = 1000
    output_bytes: int = 16384

    def __post_init__(self) -> None:
        for value in (self.startup_ms, self.cleanup_ms, self.unlimited_call_ms):
            if isinstance(value, bool) or not isfinite(value) or value <= 0:
                raise ValueError('Supervision time limits must be positive and finite.')
        if type(self.output_bytes) is not int or not 0 <= self.output_bytes <= 1048576:
            raise ValueError('Output storage must be 0..1048576 bytes per stream.')


class _Capture:
    def __init__(self, stream: IO[bytes], limit: int):
        self.stream, self.limit = stream, limit
        self.data = bytearray()
        self.total = 0
        self.lock = Lock()
        self.thread = Thread(target=self._drain, daemon=True)
        self.thread.start()

    def _drain(self) -> None:
        try:
            while chunk := self.stream.read(4096):
                with self.lock:
                    self.total += len(chunk)
                    self.data.extend(chunk[:max(0, self.limit - len(self.data))])
        except (OSError, ValueError):
            pass
        finally:
            self.stream.close()

    def report(self) -> dict[str, Any]:
        with self.lock:
            return {'text': self.data.decode('utf-8', errors='replace'),
                    'bytes_seen': self.total, 'truncated': self.total > len(self.data)}


class _Worker:
    def __init__(self, spec: PlayerSpec, color: int, policy: Supervision,
                 check_stop: Callable[[], None] | None = None):
        self.spec, self.color, self.policy = spec, color, policy
        self.check_stop = check_stop
        self.process: subprocess.Popen[bytes] | None = None
        self.connection: socket.socket | None = None
        self.captures: list[_Capture] = []
        self.workspace: TemporaryDirectory[str] | None = None
        self.report: dict[str, Any] = {'color': color, 'pid': None, 'startup_ms': None,
                                      'cleanup_ms': None, 'reaped': False}

    def start(self) -> dict[str, Any]:
        if self.check_stop:
            self.check_stop()
        start = monotonic()
        deadline = start + self.policy.startup_ms / 1000
        token = secrets.token_hex(32)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(self.policy.startup_ms / 1000)
            self.workspace = TemporaryDirectory(prefix='omok-worker-')
            self.process = subprocess.Popen([sys.executable, '-u', '-m', 'offline.worker',
                str(listener.getsockname()[1]), token], cwd=ROOT,
                env={**os.environ, 'OMOK_WORKER_SNAPSHOTS': self.workspace.name}, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.report['pid'] = self.process.pid
            assert self.process.stdout is not None and self.process.stderr is not None
            self.captures = [_Capture(stream, self.policy.output_bytes)
                             for stream in (self.process.stdout, self.process.stderr)]
            listener.settimeout(max(0.000001, deadline - monotonic()))
            while True:
                if self.check_stop:
                    self.check_stop()
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError('Worker startup deadline expired.')
                listener.settimeout(min(remaining, 0.05) if self.check_stop else remaining)
                try:
                    self.connection, _ = listener.accept()
                    break
                except TimeoutError:
                    continue
        if receive(self.connection, deadline, self.check_stop) != {'token': token}:
            raise ProtocolError('Worker authentication failed.')
        send(self.connection, {**asdict(self.spec), 'color': self.color}, deadline)
        try:
            return receive(self.connection, deadline, self.check_stop)
        finally:
            self.report['startup_ms'] = (monotonic() - start) * 1000

    def call(self, board: list[list[int]], budget: float | None, sequence: int,
             diagnostics: bool, clock: Callable[[], float]) -> tuple[dict[str, Any], float]:
        assert self.connection is not None
        start = clock()
        real_start = monotonic()
        limit = self.policy.unlimited_call_ms if budget is None else budget
        # Injected accounting clocks are verification-only; retain a real watchdog.
        watchdog = limit if clock is monotonic else max(limit, self.policy.unlimited_call_ms)
        deadline = real_start + watchdog / 1000
        try:
            send(self.connection, {'kind': 'turn', 'board': board, 'sequence': sequence,
                'time': -1 if budget is None else floor(budget), 'diagnostics': diagnostics}, deadline)
            response = receive(self.connection, deadline, self.check_stop)
            if response.get('kind') != 'reply' or response.get('sequence') != sequence:
                raise ProtocolError('Unexpected worker response.')
            if (type(response.get('mutated')) is not bool
                    or type(response.get('call_elapsed_ms')) not in (int, float)
                    or not isfinite(response['call_elapsed_ms']) or response['call_elapsed_ms'] < 0):
                raise ProtocolError('Malformed worker timing/mutation report.')
        except TimeoutError:
            response = {'transport_failure': 'timeout' if budget is not None else 'unlimited_call_cap'}
        except (EOFError, ConnectionResetError, BrokenPipeError):
            response = {'transport_failure': 'player_exit'}
        except ProtocolError as error:
            response = {'transport_failure': 'protocol_error', 'detail': str(error)}
        elapsed = (clock() - start) * 1000
        if not isfinite(elapsed) or elapsed < 0:
            raise ValueError('Clock must be finite and monotonic.')
        if elapsed > limit:
            response['transport_failure'] = 'timeout' if budget is not None else 'unlimited_call_cap'
        return response, elapsed

    def close(self) -> None:
        start = monotonic()
        process = self.process
        if self.connection is not None:
            self.connection.close()
        if process is not None:
            errors = []
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError as error:
                    errors.append(str(error))
            try:
                process.wait(timeout=self.policy.cleanup_ms / 1000)
            except (subprocess.TimeoutExpired, OSError) as error:
                if isinstance(error, OSError):
                    errors.append(str(error))
                try:
                    process.kill()
                    process.wait(timeout=self.policy.cleanup_ms / 1000)
                except (subprocess.TimeoutExpired, OSError) as error:
                    errors.append(str(error))
            self.report.update(reaped=process.poll() is not None, exitcode=process.poll())
            if errors:
                self.report['cleanup_error'] = '; '.join(errors)[:2048]
        else:
            self.report['reaped'] = True
        deadline = monotonic() + self.policy.cleanup_ms / 1000
        for capture in self.captures:
            capture.thread.join(timeout=max(0, deadline - monotonic()))
        if self.captures:
            self.report.update(stdout=self.captures[0].report(), stderr=self.captures[1].report(),
                output_drained=all(not c.thread.is_alive() for c in self.captures))
        if self.workspace is not None and self.report['reaped']:
            try:
                self.workspace.cleanup()
            except OSError as error:
                self.report['cleanup_error'] = str(error)[:2048]
        self.report['cleanup_ms'] = (monotonic() - start) * 1000


def run_supervised_game(black: PlayerSpec, white: PlayerSpec, *, initial: Position | None = None,
        budgets_ms: tuple[float | None, float | None] = (60000, 60000), move_cap: int = 1000,
        supervision: Supervision | None = None, config: dict[str, Any] | None = None,
        diagnostics: bool = False, clock: Callable[[], float] = monotonic,
        check_stop: Callable[[], None] | None = None) -> dict[str, Any]:
    """Run fresh workers, preserve valid state, and always attempt bounded cleanup."""
    if type(move_cap) is not int or move_cap < 0:
        raise ValueError('Move cap must be a nonnegative integer.')
    if len(budgets_ms) != 2 or any(b is not None and
            (isinstance(b, bool) or not isfinite(b) or b < 0) for b in budgets_ms):
        raise ValueError('Budgets must be finite nonnegative milliseconds or None.')
    policy = supervision or Supervision()
    specs = json.loads(json.dumps([asdict(black), asdict(white)], allow_nan=False))
    configuration = json.loads(json.dumps({} if config is None else config, allow_nan=False))
    if not isinstance(configuration, dict):
        raise ValueError('Configuration must be a JSON object.')
    position = initial or Position.empty()
    remaining = list(budgets_ms)
    workers = [_Worker(spec, color, policy, check_stop) for color, spec in enumerate((black, white))]
    trace: dict[str, Any] = {'format': FORMAT, 'initial': state(position),
        'players': [{'color': c, 'identifier': spec.factory, 'source': {
            'module': spec.module, 'qualname': spec.factory, 'sha256': None}, 'spec': specs[c]}
            for c, spec in enumerate((black, white))], 'budgets_ms': list(budgets_ms),
        'move_cap': move_cap, 'config': configuration, 'moves': [], 'events': [], 'failure': None,
        'supervision': {**asdict(policy), 'clock_policy': 'dispatch-through-response',
                        'start_method': 'fresh-python-subprocess'}, 'workers': []}
    status = 'completed'
    reason: str | None = position.reason

    def fail(category: str, why: str, color: int | None, *, elapsed: float = 0,
             called: bool = False, response: dict[str, Any] | None = None) -> None:
        nonlocal status, reason
        status, reason = category, why
        response = response or {}
        trace['failure'] = {'color': color, 'player': trace['players'][color]['identifier']
            if color is not None else None, 'reason': why, 'violations': [why],
            'called': called, 'elapsed_ms': elapsed,
            'returned': repr(response.get('move')) if called else None,
            'exception': response.get('exception'), 'detail': response.get('detail')}
        trace['events'].append({'type': 'failure', **trace['failure'],
            'remaining_ms': remaining[color] if color is not None else None})

    try:
        if position.outcome == 'ongoing' and move_cap > 0:
            for color, worker in enumerate(workers):
                setup_start = monotonic()
                try:
                    ready = worker.start()
                except TimeoutError:
                    fail('setup_failed', 'startup_timeout', color)
                    break
                except (EOFError, ProtocolError) as error:
                    fail('setup_failed', 'setup_protocol_error', color,
                         response={'detail': str(error)})
                    break
                finally:
                    worker.report['startup_ms'] = (monotonic() - setup_start) * 1000
                if ready.get('kind') == 'setup_failure':
                    fail('setup_failed', 'player_setup', color, response=ready)
                    break
                if ready.get('kind') != 'ready':
                    fail('setup_failed', 'setup_protocol_error', color)
                    break
                trace['players'][color].update(identifier=ready['identifier'], source=ready['source'])
        while position.outcome == 'ongoing' and trace['failure'] is None:
            if check_stop:
                check_stop()
            if len(trace['moves']) >= move_cap:
                status, reason = 'capped', 'move_cap'
                break
            color = position.side_to_move
            budget = remaining[color]
            if budget is not None and budget <= 0:
                fail('failed', 'timeout', color)
                break
            response, elapsed = workers[color].call([list(r) for r in position.board], budget,
                                                    len(trace['moves']), diagnostics, clock)
            if budget is not None:
                remaining[color] = max(0.0, budget - elapsed)
            event = {'type': 'returned', 'color': color, 'returned': repr(response.get('move')),
                     'move': response.get('move'), 'elapsed_ms': elapsed,
                     'remaining_ms': remaining[color], 'call_elapsed_ms': response.get('call_elapsed_ms'),
                     'overhead_ms': max(0, elapsed - response['call_elapsed_ms'])
                     if 'call_elapsed_ms' in response else None}
            for key in ('search', 'diagnostics_error'):
                if key in response:
                    event[key] = response[key]
            trace['events'].append(event)
            why = response.get('transport_failure')
            if why is None and response.get('exception') is not None:
                why = 'exception'
            if why is None and response.get('mutated'):
                why = 'mutation'
            transition = None
            if why is None:
                try:
                    transition = position.play(response['move'])
                except ValueError:
                    why = 'invalid_move'
            if why is not None:
                fail('capped' if why == 'unlimited_call_cap' else 'failed', why, color,
                     elapsed=elapsed, called=True, response=response)
                break
            assert transition is not None
            position = transition.position
            entry = {'color': color, 'move': list(transition.move),
                'captured': captured_cells(transition), 'elapsed_ms': elapsed,
                'remaining_ms': remaining[color]}
            trace['moves'].append(entry)
            trace['events'].append({'type': 'applied', **entry, 'state': state(position)})
            reason = position.reason
    except (OSError, ValueError, KeyError, TypeError, AssertionError) as error:
        fail('supervisor_error', 'supervisor_error', None,
             response={'exception': {'type': type(error).__name__, 'message': str(error)[:2048]}})
    except BaseException as interruption:
        # Keep partial game facts and cleanup reports with cancellation evidence.
        status, reason = 'interrupted', 'batch_interruption'
        setattr(interruption, 'interrupted_trace', trace)
        raise
    finally:
        for worker in workers:
            try:
                worker.close()
            except OSError as error:
                worker.report['cleanup_error'] = str(error)
            trace['workers'].append(worker.report)
        if any(not w['reaped'] or w.get('cleanup_error') for w in trace['workers']):
            trace['prior_result'] = {'status': status, 'reason': reason, 'failure': trace['failure']}
            fail('supervisor_error', 'cleanup_error', None)
        trace.update(status=status, reason=reason, final=state(position),
                     remaining_ms=remaining, winner=rules_winner(position))
    return trace


# AI-written by OpenAI Codex, for issue #26.
def preflight_player(spec: PlayerSpec, color: int, policy: Supervision,
                     check_stop: Callable[[], None] | None = None) -> dict[str, Any]:
    """Bound imports/construction and check explicit color without competitive calls."""
    worker = _Worker(spec, color, policy, check_stop)
    result: dict[str, Any] = {'ready': False, 'detail': None}
    try:
        ready = worker.start()
        result['ready'] = ready.get('kind') == 'ready'
        if not result['ready']:
            result['detail'] = ready.get('exception', ready)
    except (OSError, EOFError, ProtocolError) as error:
        result['detail'] = {'type': type(error).__name__, 'message': str(error)}
    except BaseException as interruption:
        setattr(interruption, 'interrupted_preflight', result)
        result['worker'] = worker.report
        raise
    finally:
        worker.close()
    result['worker'] = worker.report
    if not worker.report['reaped'] or worker.report.get('cleanup_error'):
        result.update(ready=False, detail='Preflight cleanup failed.')
    return result
