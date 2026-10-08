# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
"""Development move-selection boundary; official Player inheritance is pending."""
from collections.abc import Sequence
from time import monotonic
from typing import Protocol, SupportsIndex

from omok.simulator import Coordinate, EMPTY, Position, SIZE


class DevelopmentPlayer(Protocol):
    color: int

    def take_turn(self, board: list[list[int]], time: float) -> Coordinate: ...


class LegalBaseline:
    """Explicit color and a legal fallback, with bounded one-ply improvement."""

    def __init__(self, color: int) -> None:
        if type(color) is not int or color not in (0, 1):
            raise ValueError('Color must be 0 or 1.')
        self.color = color

    def take_turn(self, board: Sequence[Sequence[SupportsIndex]], time: float) -> Coordinate:
        # Own and validate the input before optional work. Never infer color.
        start = monotonic()
        position = Position(board, self.color)
        if position.outcome != 'ongoing':
            raise ValueError('take_turn requires a live position.')
        fallback = next((r, c) for r in range(SIZE) for c in range(SIZE)
                        if position.board[r][c] == EMPTY)
        if time != -1 and time <= 2:
            return fallback
        return self._choose_move(position, fallback, start, time)

    def _choose_move(self, position: Position, fallback: Coordinate,
                     start: float, time: float) -> Coordinate:
        allowance_ms = 100.0 if time == -1 else min(100.0, max(0.0, (time - 2) * 0.1))
        deadline = start + allowance_ms / 1000
        candidates = [(r, c) for r in range(SIZE) for c in range(SIZE)
                      if position.board[r][c] == EMPTY]

        def priority(move: Coordinate) -> tuple[int, int, int, int]:
            r, c = move
            neighbors = sum(position.board[nr][nc] == self.color
                            for nr in range(max(0, r - 1), min(SIZE, r + 2))
                            for nc in range(max(0, c - 1), min(SIZE, c + 2)))
            return (-neighbors, abs(r - 9) + abs(c - 9), r, c)

        candidates.sort(key=priority)
        best = fallback
        found_safe = False
        win = 'black_win' if self.color == 0 else 'white_win'
        loss = 'white_win' if self.color == 0 else 'black_win'
        for move in candidates:
            if monotonic() >= deadline:
                break
            child = position.play(move).position
            if child.outcome == win:
                return move
            if child.outcome != loss and not found_safe:
                best, found_safe = move, True
        return best
