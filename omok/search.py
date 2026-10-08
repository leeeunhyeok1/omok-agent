# AI-written by OpenAI Codex, for issue #10.
"""Deterministic fixed-depth search over immutable simulator positions."""
from dataclasses import dataclass
from collections.abc import Callable, Iterable, Iterator
from math import isfinite
from time import monotonic

from omok.simulator import Coordinate, EMPTY, Position, SIZE

WIN_SCORE = 10000
EVALUATION_LIMIT = 4000
FULL_WINDOW = WIN_SCORE + 1
CandidateSource = Callable[[Position], Iterable[Coordinate]]
Evaluator = Callable[[Position], int]


class SearchCancelled(Exception):
    """Intentional control signal; other exceptions propagate unchanged."""


@dataclass(frozen=True, slots=True)
class SearchLimits:
    max_nodes: int | None = None
    deadline: float | None = None
    cancelled: Callable[[], bool] | None = None

    def __post_init__(self) -> None:
        if self.max_nodes is not None and (type(self.max_nodes) is not int or self.max_nodes < 0):
            raise ValueError('Node limit must be a nonnegative integer or None.')
        if self.deadline is not None and not isfinite(self.deadline):
            raise ValueError('Deadline must be finite or None.')


def legal_moves(position: Position) -> Iterator[Coordinate]:
    for row in range(SIZE):
        for col in range(SIZE):
            if position.board[row][col] == EMPTY:
                yield row, col


def material_evaluation(position: Position) -> int:
    """Untuned black-centric material difference; range [-361, 361]."""
    return sum(1 if cell == 0 else -1 if cell == 1 else 0
               for row in position.board for cell in row)


@dataclass(frozen=True, slots=True)
class SearchResult:
    move: Coordinate | None
    score: int | None
    completed: bool
    optimal_moves: tuple[Coordinate, ...] | None = None
    nodes: int = 0
    cutoffs: int = 0
    cancellation: str | None = None


@dataclass(slots=True)
class _Traversal:
    limits: SearchLimits
    clock: Callable[[], float]
    nodes: int = 0
    cutoffs: int = 0

    def check(self) -> None:
        if self.limits.cancelled is not None and self.limits.cancelled():
            raise SearchCancelled('requested')
        if self.limits.deadline is not None and self.clock() >= self.limits.deadline:
            raise SearchCancelled('deadline')

    def visit(self) -> None:
        self.check()
        if self.limits.max_nodes is not None and self.nodes >= self.limits.max_nodes:
            raise SearchCancelled('node_limit')
        self.nodes += 1


class FixedDepthSearch:
    def __init__(self, *, candidates: CandidateSource = legal_moves,
                 evaluator: Evaluator = material_evaluation,
                 clock: Callable[[], float] = monotonic) -> None:
        self.candidates = candidates
        self.evaluator = evaluator
        self.clock = clock

    def score(self, position: Position, perspective: int) -> int:
        if type(perspective) is not int or perspective not in (0, 1):
            raise ValueError('Perspective must be 0 or 1.')
        if position.outcome == 'draw':
            return 0
        if position.outcome != 'ongoing':
            winner = 0 if position.outcome == 'black_win' else 1
            return WIN_SCORE if perspective == winner else -WIN_SCORE
        value = self.evaluator(position)
        if type(value) is not int or abs(value) > EVALUATION_LIMIT:
            raise ValueError('Evaluator must return a bounded black-centric integer.')
        return value if perspective == 0 else -value

    def _moves(self, position: Position, traversal: _Traversal) -> tuple[Coordinate, ...]:
        moves: dict[Coordinate, None] = {}
        for move in self.candidates(position):
            traversal.check()
            row, col = move
            if (type(row) is not int or type(col) is not int
                    or not (0 <= row < SIZE and 0 <= col < SIZE)
                    or position.board[row][col] != EMPTY):
                raise ValueError('Candidates must be legal integer coordinates.')
            moves[(row, col)] = None
        if not moves:
            for move in legal_moves(position):
                traversal.check()
                moves[move] = None
        traversal.check()
        return tuple(moves)

    def search(self, position: Position, depth: int, *,
               reference: bool = False, limits: SearchLimits | None = None) -> SearchResult:
        if type(depth) is not int or depth < 0:
            raise ValueError('Depth must be a nonnegative integer.')
        if position.outcome != 'ongoing':
            return SearchResult(None, self.score(position, position.side_to_move), True)
        fallback = next(legal_moves(position))
        traversal = _Traversal(SearchLimits() if limits is None else limits, self.clock)
        try:
            return self._root(position, depth, reference, traversal)
        except SearchCancelled as error:
            return SearchResult(fallback, None, False, nodes=traversal.nodes,
                                cutoffs=traversal.cutoffs, cancellation=str(error))

    def _leaf(self, position: Position, perspective: int, traversal: _Traversal) -> int:
        traversal.check()
        value = self.score(position, perspective)
        traversal.check()
        return value

    def _root(self, position: Position, depth: int, reference: bool,
              traversal: _Traversal) -> SearchResult:
        traversal.visit()
        if depth == 0:
            return SearchResult(None, self._leaf(position, position.side_to_move, traversal),
                                True, nodes=traversal.nodes)
        best = -FULL_WINDOW
        optimal: list[Coordinate] = []
        for move in self._moves(position, traversal):
            traversal.check()
            child = position.play(move).position
            if reference:
                value = -self._unpruned(child, depth - 1, 1 - position.side_to_move, traversal)
            else:
                value = -self._alpha_beta(child, depth - 1, 1 - position.side_to_move,
                                          -FULL_WINDOW, -best, traversal)
            if value > best:
                best, optimal = value, [move]
            elif value == best:
                optimal.append(move)
        traversal.check()
        return SearchResult(optimal[0], best, True, tuple(optimal) if reference else None,
                            traversal.nodes, traversal.cutoffs)

    def _unpruned(self, position: Position, depth: int, perspective: int,
                  traversal: _Traversal) -> int:
        traversal.visit()
        if position.outcome != 'ongoing' or depth == 0:
            return self._leaf(position, perspective, traversal)
        return max(-self._unpruned(position.play(move).position, depth - 1, 1 - perspective, traversal)
                   for move in self._moves(position, traversal))

    def _alpha_beta(self, position: Position, depth: int, perspective: int,
                    alpha: int, beta: int, traversal: _Traversal) -> int:
        """Fail-soft: return the best observed value even beyond the window."""
        traversal.visit()
        if position.outcome != 'ongoing' or depth == 0:
            return self._leaf(position, perspective, traversal)
        best = -FULL_WINDOW
        for move in self._moves(position, traversal):
            traversal.check()
            child = position.play(move).position
            value = -self._alpha_beta(child, depth - 1, 1 - perspective,
                                      -beta, -alpha, traversal)
            best = max(best, value)
            alpha = max(alpha, best)
            if alpha >= beta:
                traversal.cutoffs += 1
                break
        return best
