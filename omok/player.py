# AI-written by OpenAI Codex, for issues #4 and #5.
"""Development move-selection boundary; official Player inheritance is pending."""
from dataclasses import dataclass
from collections.abc import Sequence
from math import isfinite
from time import monotonic
from typing import Protocol, SupportsIndex

from omok.simulator import Coordinate, EMPTY, Position, SIZE, Transition
from omok.search import FixedDepthSearch, SearchLimits, SearchResult, legal_moves


class DevelopmentPlayer(Protocol):
    color: int

    def take_turn(self, board: list[list[int]], time: float) -> Coordinate: ...


# AI-written by OpenAI Codex, for issue #10. LegalBaseline below stays available.
class FixedDepthPlayer:
    """Bounded fixed-depth development player; iteration/tactics are later work."""

    def __init__(self, color: int, *, depth: int = 1, max_nodes: int = 10000,
                 max_time_ms: float = 100.0, search: FixedDepthSearch | None = None) -> None:
        if type(color) is not int or color not in (0, 1):
            raise ValueError('Color must be 0 or 1.')
        if type(depth) is not int or depth < 1:
            raise ValueError('Player depth must be a positive integer.')
        if type(max_nodes) is not int or max_nodes < 0:
            raise ValueError('Node limit must be a nonnegative integer.')
        if isinstance(max_time_ms, bool) or not isfinite(max_time_ms) or max_time_ms < 0:
            raise ValueError('Time bound must be finite and nonnegative.')
        self.color = color
        self.depth = depth
        self.max_nodes = max_nodes
        self.max_time_ms = max_time_ms
        self.search = FixedDepthSearch() if search is None else search
        self.last_result: SearchResult | None = None

    def take_turn(self, board: Sequence[Sequence[SupportsIndex]], time: float) -> Coordinate:
        self.last_result = None
        start = self.search.clock()
        if isinstance(time, bool) or not isfinite(time):
            raise ValueError('Remaining time must be finite milliseconds.')
        position = Position(board, self.color)
        if position.outcome != 'ongoing':
            raise ValueError('take_turn requires a live position.')
        fallback = next(legal_moves(position))
        if time != -1 and time <= 2:
            self.last_result = SearchResult(fallback, None, False, cancellation='low_time')
            return fallback
        allowance = self.max_time_ms if time == -1 else min(
            self.max_time_ms, max(0.0, (time - 2) * 0.1))
        self.last_result = self.search.search(
            position, self.depth,
            limits=SearchLimits(max_nodes=self.max_nodes, deadline=start + allowance / 1000))
        if self.last_result.move is None:
            raise RuntimeError('Positive-depth live search returned no move.')
        return self.last_result.move


# AI-written by OpenAI Codex, for issues #11 and #12.
@dataclass(frozen=True, slots=True)
class TimePolicy:
    max_time_ms: float = 100.0
    return_margin_ms: float = 2.0
    reserve_fraction: float = 0.5
    turn_fraction: float = 0.1
    soft_fraction: float = 0.8

    def __post_init__(self) -> None:
        for value in (self.max_time_ms, self.return_margin_ms):
            if isinstance(value, bool) or not isfinite(value) or value < 0:
                raise ValueError('Time bounds must be finite and nonnegative.')
        for value in (self.reserve_fraction, self.turn_fraction, self.soft_fraction):
            if isinstance(value, bool) or not isfinite(value) or not 0 < value < 1:
                raise ValueError('Time fractions must be finite and strictly between 0 and 1.')

    def allowance(self, remaining_ms: float) -> float:
        if isinstance(remaining_ms, bool) or not isfinite(remaining_ms):
            raise ValueError('Remaining time must be finite milliseconds.')
        if remaining_ms == -1:
            return self.max_time_ms  # Bounded local convention; official semantics unresolved.
        spendable = max(0.0, remaining_ms - self.return_margin_ms)
        return min(self.max_time_ms, spendable * (1 - self.reserve_fraction) * self.turn_fraction)


class IterativePlayer:
    """Development public boundary with a remaining-total-clock allocation."""

    def __init__(self, color: int, *, max_depth: int = 8, max_nodes: int = 10000,
                 policy: TimePolicy | None = None, search: FixedDepthSearch | None = None) -> None:
        if type(color) is not int or color not in (0, 1):
            raise ValueError('Color must be 0 or 1.')
        if type(max_depth) is not int or max_depth < 1:
            raise ValueError('Maximum depth must be a positive integer.')
        if type(max_nodes) is not int or max_nodes < 0:
            raise ValueError('Node limit must be a nonnegative integer.')
        self.color, self.max_depth, self.max_nodes = color, max_depth, max_nodes
        self.policy = TimePolicy() if policy is None else policy
        from omok.tactics import TacticalPolicy
        self.search = FixedDepthSearch(tactics=TacticalPolicy()) if search is None else search
        self.last_result: SearchResult | None = None
        self.last_elapsed_ms: float | None = None
        self.last_allocation_ms: float | None = None

    def take_turn(self, board: Sequence[Sequence[SupportsIndex]], time: float) -> Coordinate:
        start = self.search.clock()
        self.last_result = None
        self.last_elapsed_ms = None
        self.last_allocation_ms = None
        allowance = self.policy.allowance(time)
        self.last_allocation_ms = allowance
        position = Position(board, self.color)
        if position.outcome != 'ongoing':
            raise ValueError('take_turn requires a live position.')
        fallback = next(legal_moves(position))
        if allowance == 0:
            result = SearchResult(fallback, None, False, cancellation='low_time')
        else:
            result = self.search.iterative(
                position, self.max_depth,
                limits=SearchLimits(max_nodes=self.max_nodes, deadline=start + allowance / 1000),
                soft_deadline=start + allowance * self.policy.soft_fraction / 1000)
        if result.move is None:
            raise RuntimeError('Positive-depth live search returned no move.')
        self.last_result = result
        self.last_elapsed_ms = (self.search.clock() - start) * 1000
        return result.move


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
        if monotonic() >= deadline:
            return fallback
        candidates = [(r, c) for r in range(SIZE) for c in range(SIZE)
                      if position.board[r][c] == EMPTY]

        def priority(move: Coordinate) -> tuple[int, int, int, int]:
            r, c = move
            neighbors = self._own_neighbors(position, move)
            return (-neighbors, abs(r - 9) + abs(c - 9), r, c)

        candidates.sort(key=priority)
        best = fallback
        found_safe = False
        best_score: int | None = None
        win = 'black_win' if self.color == 0 else 'white_win'
        loss = 'white_win' if self.color == 0 else 'black_win'
        for move in candidates:
            if monotonic() >= deadline:
                break
            transition = position.play(move)
            child = transition.position
            if child.outcome == win:
                return move
            if child.outcome == loss:
                continue
            if not found_safe:
                best, found_safe = move, True
            if monotonic() >= deadline:
                break
            try:
                score = self._score(transition)
            except Exception:
                # Optional evaluation cannot invalidate the known legal choice.
                # Immutable child copies keep the parent and siblings untouched.
                continue
            if best_score is None or score > best_score:
                best, best_score = move, score
        return best

    def _score(self, transition: Transition) -> int:
        # Temporary, untuned baseline weights: 4 per captured stone, 1 per
        # adjacent own stone. Candidate order breaks equal scores deterministically.
        return (4 * len(transition.captured)
                + self._own_neighbors(transition.position, transition.move))

    def _own_neighbors(self, position: Position, move: Coordinate) -> int:
        r, c = move
        return sum(position.board[nr][nc] == self.color
                   for nr in range(max(0, r - 1), min(SIZE, r + 2))
                   for nc in range(max(0, c - 1), min(SIZE, c + 2))
                   if (nr, nc) != (r, c))
