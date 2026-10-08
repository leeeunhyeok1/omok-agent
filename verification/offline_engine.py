# AI-written by OpenAI Codex, for issue #8.
"""Run core operations with offline imports blocked; use Python -I -S.

For OS-level network denial on macOS, run under sandbox-exec as documented in
the Phase 01 acceptance report. This script also denies Python socket operations.
"""
import importlib.abc
import json
from pathlib import Path
import sys


class EngineImportsOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.partition('.')[0]
        if root != 'omok' and root not in sys.stdlib_module_names:
            raise ImportError(f'Non-engine dependency blocked: {fullname}')
        return None


def deny_network(event: str, args: tuple[object, ...]) -> None:
    if event.startswith('socket.'):
        raise PermissionError(f'Network operation blocked: {event}')


def main() -> None:
    sys.addaudithook(deny_network)
    sys.meta_path.insert(0, EngineImportsOnly())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from omok.player import LegalBaseline
    from omok.simulator import Position

    moves = []
    for color in (0, 1):
        position = Position([[-1] * 19 for _ in range(19)], color)
        board = [list(row) for row in position.board]
        move = LegalBaseline(color).take_turn(board, 60000)
        transition = position.play(move)
        if board != [list(row) for row in position.board]:
            raise AssertionError('Caller board mutated.')
        if transition.position.board[move[0]][move[1]] != color:
            raise AssertionError('Placement failed.')
        moves.append({'color': color, 'move': move, 'outcome': transition.position.outcome})
    print(json.dumps({'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site,
                      'network': 'Python socket operations denied',
                      'imports': 'engine and standard library only', 'moves': moves}))


if __name__ == '__main__':
    main()
