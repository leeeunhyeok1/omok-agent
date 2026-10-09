# AI-written by OpenAI Codex, for issue #25.
"""Private worker entry point; imports and player construction happen here."""
from importlib import import_module
import random
import socket
import sys
from time import monotonic
from typing import Any

from offline.runner import player_source, returned_move, unchanged
from offline.worker_protocol import receive, send
from omok.simulator import Position


def exception_data(error: BaseException) -> dict[str, str]:
    return {'type': type(error).__name__, 'message': str(error)[:2048]}


def main() -> None:
    connection = socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=5)
    send(connection, {'token': sys.argv[2]}, monotonic() + 5)
    spec = receive(connection, monotonic() + 10)
    try:
        random.seed(spec['seed'])
        factory: Any = import_module(spec['module'])
        for part in spec['factory'].split('.'):
            factory = getattr(factory, part)
        player = factory(spec['color'], **spec['options'])
        if type(player.color) is not int or player.color != spec['color']:
            raise ValueError('Factory must assign the requested explicit color.')
        send(connection, {'kind': 'ready', 'identifier': type(player).__name__,
                          'source': player_source(player)}, monotonic() + 5)
    except BaseException as error:
        send(connection, {'kind': 'setup_failure', 'exception': exception_data(error)}, monotonic() + 5)
        return
    while True:
        # Idle waiting consumes neither clock; the supervisor bounds process lifetime.
        request = receive(connection, monotonic() + 86400)
        if request['kind'] == 'stop':
            return
        board = request['board']
        position = Position(board, spec['color'])
        start = monotonic()
        error_data = None
        move = None
        try:
            value = player.take_turn(board, request['time'])
            # Do not serialize arbitrary player objects or call their repr hooks.
            move = returned_move(value)
            if move is not None and any(abs(n) > 10**9 for n in move):
                move = None
        except BaseException as error:
            error_data = exception_data(error)
        elapsed = (monotonic() - start) * 1000
        report: dict[str, Any] = {'kind': 'reply', 'sequence': request['sequence'],
            'move': move, 'mutated': not unchanged(board, position),
            'exception': error_data, 'call_elapsed_ms': elapsed}
        if request['diagnostics']:
            try:
                import json
                diagnostics = getattr(player, 'diagnostics', lambda: None)()
                encoded = json.dumps(diagnostics, allow_nan=False)
                if diagnostics is not None and (not isinstance(diagnostics, dict) or len(encoded) > 16384):
                    raise ValueError('Diagnostics exceed object/size bounds.')
                if diagnostics is not None:
                    report['search'] = diagnostics
            except BaseException as error:
                report['diagnostics_error'] = type(error).__name__
        send(connection, report, monotonic() + 5)


if __name__ == '__main__':
    main()
