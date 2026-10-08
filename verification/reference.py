# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #3.
"""Offline oracle: enumerate four-cell windows and group entire board lines.

Shares only encoding and result vocabulary with the engine, never rule helpers.
"""
from dataclasses import dataclass
from itertools import groupby
from operator import index
from collections.abc import Sequence
from typing import SupportsIndex

from omok.simulator import SIZE, EMPTY, Coordinate, Outcome, Reason, Board, CapturedCell


@dataclass(frozen=True, init=False)
class ReferencePosition:
    board: Board
    side_to_move: int
    outcome: Outcome
    reason: Reason | None

    def __init__(self, board: Sequence[Sequence[SupportsIndex]],
                 side_to_move: SupportsIndex) -> None:
        try:
            if len(board) != SIZE or any(len(row) != SIZE for row in board):
                raise ValueError('Expected 19 by 19 board.')
            copied = []
            for row in board:
                values = []
                for value in row:
                    if isinstance(value, bool):
                        raise ValueError('Boolean cell.')
                    cell = index(value)
                    if cell not in (-1, 0, 1):
                        raise ValueError('Invalid cell.')
                    values.append(cell)
                copied.append(values)
            if isinstance(side_to_move, bool) or index(side_to_move) not in (0, 1):
                raise ValueError('Invalid color.')
        except TypeError as error:
            raise ValueError('Expected integer cells and color.') from error
        outcome, reason = terminal(copied)
        object.__setattr__(self, 'board', tuple(tuple(row) for row in copied))
        object.__setattr__(self, 'side_to_move', index(side_to_move))
        object.__setattr__(self, 'outcome', outcome)
        object.__setattr__(self, 'reason', reason)

    @classmethod
    def empty(cls) -> 'ReferencePosition':
        return cls([[EMPTY] * SIZE for _ in range(SIZE)], 0)

    def play(self, move: Sequence[SupportsIndex]) -> 'ReferenceTransition':
        if self.outcome != 'ongoing':
            raise ValueError('Terminal position.')
        try:
            first, second = move
            if isinstance(first, bool) or isinstance(second, bool):
                raise ValueError('Boolean coordinate.')
            row, col = index(first), index(second)
        except (TypeError, ValueError) as error:
            raise ValueError('Expected integer coordinate pair.') from error
        if not (0 <= row < SIZE and 0 <= col < SIZE) or self.board[row][col] != EMPTY:
            raise ValueError('Illegal move.')
        board = [list(values) for values in self.board]
        board[row][col] = self.side_to_move
        captured: dict[Coordinate, int] = {}
        # Enumerate every undirected length-four window. The move must be an endpoint.
        for r in range(SIZE):
            for c in range(SIZE):
                for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                    cells = [(r + n * dr, c + n * dc) for n in range(4)]
                    if (row, col) not in (cells[0], cells[-1]):
                        continue
                    if not all(0 <= x < SIZE and 0 <= y < SIZE for x, y in cells):
                        continue
                    values = [board[x][y] for x, y in cells]
                    if values == [self.side_to_move, 1 - self.side_to_move,
                                  1 - self.side_to_move, self.side_to_move]:
                        for x, y in cells[1:3]:
                            captured[x, y] = board[x][y]
        for x, y in captured:
            board[x][y] = EMPTY
        outcome, reason = terminal(board)
        side = 1 - self.side_to_move if outcome == 'ongoing' else self.side_to_move
        return ReferenceTransition(ReferencePosition(board, side),
                                   tuple(CapturedCell(cell, value) for cell, value in sorted(captured.items())),
                                   (row, col), self.side_to_move)


@dataclass
class ReferenceTransition:
    position: ReferencePosition
    captured: tuple[CapturedCell, ...]
    move: Coordinate
    color: int


def terminal(board: Sequence[Sequence[int]]) -> tuple[Outcome, Reason | None]:
    """Group rows, columns, and diagonals, rather than walking from run starts."""
    lines = [list(row) for row in board]
    lines.extend([board[r][c] for r in range(SIZE)] for c in range(SIZE))
    for offset in range(-SIZE + 1, SIZE):
        lines.append([board[r][r - offset] for r in range(SIZE) if 0 <= r - offset < SIZE])
    for total in range(2 * SIZE - 1):
        lines.append([board[r][total - r] for r in range(SIZE) if 0 <= total - r < SIZE])
    winners = set()
    for line in lines:
        for color, group in groupby(line):
            if color != EMPTY and len(list(group)) == 5:
                winners.add(color)
    if winners == {0, 1}:
        return 'draw', 'simultaneous_wins'
    if winners == {0}:
        return 'black_win', 'exact_five'
    if winners == {1}:
        return 'white_win', 'exact_five'
    if all(EMPTY not in row for row in board):
        return 'draw', 'full_board'
    return 'ongoing', None
