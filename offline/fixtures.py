# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
"""Explicit live starts for demonstration; historical reachability is not required."""
from omok.simulator import Position

NAMES = ('empty', 'mover-win', 'opponent-win', 'simultaneous', 'dense')


def fixture(name: str) -> Position:
    board = [[-1] * 19 for _ in range(19)]
    if name == 'empty':
        return Position.empty()
    if name == 'dense':
        board = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
        board[0][0] = -1
        return Position(board, 1)
    if name in ('opponent-win', 'simultaneous'):
        board[9][5:11] = [1] * 6
        board[10][10], board[11][10] = 1, 0
    if name in ('mover-win', 'simultaneous'):
        board[8][6:10] = [0] * 4
    if name not in NAMES:
        raise ValueError('Unknown fixture.')
    return Position(board, 0)
