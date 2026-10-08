# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #3.
"""Owned, immutable positions and copy-based Omok++ transitions."""
from dataclasses import dataclass
from operator import index
from collections.abc import Sequence
from typing import SupportsIndex
from typing import Literal

SIZE = 19
EMPTY = -1
BLACK = 0
WHITE = 1
AXES = ((0, 1), (1, 0), (1, 1), (1, -1))
DIRECTIONS = AXES + tuple((-dr, -dc) for dr, dc in AXES)
Coordinate = tuple[int, int]
Board = tuple[tuple[int, ...], ...]
Outcome = Literal['ongoing', 'black_win', 'white_win', 'draw']
Reason = Literal['exact_five', 'simultaneous_wins', 'full_board']


def _integer(value: SupportsIndex) -> int:
    if isinstance(value, bool):
        raise ValueError('Boolean values are not board integers.')
    try:
        return index(value)
    except TypeError as error:
        raise ValueError('Expected an integer supporting __index__.') from error


@dataclass(frozen=True, slots=True)
class CapturedCell:
    cell: Coordinate
    prior_value: int


@dataclass(frozen=True, slots=True, init=False)
class Position:
    board: Board
    side_to_move: int
    outcome: Outcome
    reason: Reason | None

    def __init__(self, board: Sequence[Sequence[SupportsIndex]], side_to_move: SupportsIndex) -> None:
        try:
            if len(board) != SIZE or any(len(row) != SIZE for row in board):
                raise ValueError('Board must have 19 rows of 19 cells.')
            owned_board = tuple(tuple(_integer(cell) for cell in row) for row in board)
            if any(cell not in (EMPTY, BLACK, WHITE) for row in owned_board for cell in row):
                raise ValueError('Board cells must be -1, 0, or 1.')
            color = _integer(side_to_move)
            if color not in (BLACK, WHITE):
                raise ValueError('Side to move must be 0 or 1.')
        except TypeError as error:
            raise ValueError('Expected a rectangular board and integer color.') from error
        object.__setattr__(self, 'board', owned_board)
        object.__setattr__(self, 'side_to_move', color)
        outcome, reason = _terminal(owned_board)
        object.__setattr__(self, 'outcome', outcome)
        object.__setattr__(self, 'reason', reason)

    @classmethod
    def _owned(cls, board: Board, side_to_move: int) -> 'Position':
        position = object.__new__(cls)
        object.__setattr__(position, 'board', board)
        object.__setattr__(position, 'side_to_move', side_to_move)
        outcome, reason = _terminal(board)
        object.__setattr__(position, 'outcome', outcome)
        object.__setattr__(position, 'reason', reason)
        return position

    @classmethod
    def empty(cls) -> 'Position':
        return cls(tuple((EMPTY,) * SIZE for _ in range(SIZE)), BLACK)

    def play(self, move: Sequence[SupportsIndex]) -> 'Transition':
        if self.outcome != 'ongoing':
            raise ValueError('Cannot play on a terminal position.')
        try:
            row_value, col_value = move
            row, col = _integer(row_value), _integer(col_value)
        except (TypeError, ValueError) as error:
            raise ValueError('Move must be a pair of integers.') from error
        if not (0 <= row < SIZE and 0 <= col < SIZE):
            raise ValueError('Move is outside the board.')
        if self.board[row][col] != EMPTY:
            raise ValueError('Move must target an empty cell.')
        board = [list(values) for values in self.board]
        board[row][col] = self.side_to_move
        captured: set[Coordinate] = set()
        for dr, dc in DIRECTIONS:
            end_row, end_col = row + 3 * dr, col + 3 * dc
            if not (0 <= end_row < SIZE and 0 <= end_col < SIZE):
                continue
            first = (row + dr, col + dc)
            second = (row + 2 * dr, col + 2 * dc)
            if (board[first[0]][first[1]] == 1 - self.side_to_move
                    and board[second[0]][second[1]] == 1 - self.side_to_move
                    and board[end_row][end_col] == self.side_to_move):
                captured.update((first, second))
        prior = tuple(CapturedCell(cell, board[cell[0]][cell[1]]) for cell in sorted(captured))
        for captured_row, captured_col in captured:
            board[captured_row][captured_col] = EMPTY
        child = Position._owned(tuple(tuple(values) for values in board), 1 - self.side_to_move)
        if child.outcome != 'ongoing':
            object.__setattr__(child, 'side_to_move', self.side_to_move)
        return Transition(child, (row, col), self.side_to_move, prior)


@dataclass(frozen=True, slots=True)
class Transition:
    position: Position
    move: Coordinate
    color: int
    captured: tuple[CapturedCell, ...]


def _terminal(board: Board) -> tuple[Outcome, Reason | None]:
    winners: set[int] = set()
    has_empty = False
    for row in range(SIZE):
        for col in range(SIZE):
            color = board[row][col]
            if color == EMPTY:
                has_empty = True
                continue
            for dr, dc in AXES:
                previous_row, previous_col = row - dr, col - dc
                if (0 <= previous_row < SIZE and 0 <= previous_col < SIZE
                        and board[previous_row][previous_col] == color):
                    continue
                length = 0
                r, c = row, col
                while 0 <= r < SIZE and 0 <= c < SIZE and board[r][c] == color:
                    length += 1
                    r += dr
                    c += dc
                if length == 5:
                    winners.add(color)
    if len(winners) == 2:
        return 'draw', 'simultaneous_wins'
    if BLACK in winners:
        return 'black_win', 'exact_five'
    if WHITE in winners:
        return 'white_win', 'exact_five'
    if not has_empty:
        return 'draw', 'full_board'
    return 'ongoing', None
