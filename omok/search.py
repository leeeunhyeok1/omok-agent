# AI-written by OpenAI Codex, for issues #10, #11 and #12.
"""Fixed-depth and committed iterative search over immutable positions."""
from dataclasses import dataclass, replace, field
from collections.abc import Callable, Iterable, Iterator
from math import isfinite
from time import monotonic
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omok.tactics import TacticalPolicy, TacticalResult

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

    def check(self, clock: Callable[[], float] = monotonic) -> None:
        """Shared cooperative checkpoint, also available to tactical callbacks."""
        if self.cancelled is not None and self.cancelled():
            raise SearchCancelled('requested')
        if self.deadline is not None and clock() >= self.deadline:
            raise SearchCancelled('deadline')

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


def material_evaluation(position: Position, *,
                        check: Callable[[], None] = lambda: None) -> int:
    """Untuned black-centric material difference; range [-361, 361]."""
    value = 0
    for row in position.board:
        check()
        value += sum(1 if cell == 0 else -1 if cell == 1 else 0 for cell in row)
    return value


@dataclass(frozen=True, slots=True)
class SearchResult:
    move: Coordinate | None
    score: int | None
    completed: bool
    optimal_moves: tuple[Coordinate, ...] | None = None
    nodes: int = 0
    cutoffs: int = 0
    cancellation: str | None = None
    completed_depth: int = 0
    attempted_depth: int = 0
    principal_variation: tuple[Coordinate, ...] = ()
    pv_status: str = 'unavailable'
    tactics: 'TacticalResult | None' = None
    root_candidate_count: int = 0


@dataclass(slots=True)
class _Traversal:
    limits: SearchLimits
    clock: Callable[[], float]
    nodes: int = 0
    cutoffs: int = 0
    root: Position | None = None
    root_tactics: 'TacticalResult | None' = None
    root_candidate_count: int = 0
    pv_moves: dict[Position, Coordinate] = field(default_factory=dict)

    def check(self) -> None:
        self.limits.check(self.clock)

    def visit(self) -> None:
        self.check()
        if self.limits.max_nodes is not None and self.nodes >= self.limits.max_nodes:
            raise SearchCancelled('node_limit')
        self.nodes += 1


class FixedDepthSearch:
    def __init__(self, *, candidates: CandidateSource = legal_moves,
                 evaluator: Evaluator = material_evaluation,
                 clock: Callable[[], float] = monotonic,
                 cooperative_candidates: Callable[[Position, Callable[[], None]], Iterable[Coordinate]] | None = None,
                 cooperative_evaluator: Callable[[Position, Callable[[], None]], int] | None = None,
                 tactics: 'TacticalPolicy | None' = None,
                 ordering: Callable[[Position, Coordinate, Callable[[], None]], int] | None = None) -> None:
        self.candidates = candidates
        self.evaluator = evaluator
        self.clock = clock
        self.cooperative_candidates = cooperative_candidates
        self.cooperative_evaluator = cooperative_evaluator
        self.ordering = ordering
        self.tactics = tactics

    def score(self, position: Position, perspective: int, *,
              check: Callable[[], None] = lambda: None) -> int:
        if type(perspective) is not int or perspective not in (0, 1):
            raise ValueError('Perspective must be 0 or 1.')
        if position.outcome == 'draw':
            return 0
        if position.outcome != 'ongoing':
            winner = 0 if position.outcome == 'black_win' else 1
            return WIN_SCORE if perspective == winner else -WIN_SCORE
        if self.cooperative_evaluator is not None:
            value = self.cooperative_evaluator(position, check)
        elif self.evaluator is material_evaluation:
            value = material_evaluation(position, check=check)
        else:
            value = self.evaluator(position)
        if type(value) is not int or abs(value) > EVALUATION_LIMIT:
            raise ValueError('Evaluator must return a bounded black-centric integer.')
        return value if perspective == 0 else -value

    def _moves(self, position: Position, traversal: _Traversal) -> tuple[Coordinate, ...]:
        moves: dict[Coordinate, None] = {}
        traversal.check()
        report = None
        source: Iterable[Coordinate]
        if self.tactics is not None:
            report = self.tactics.analyze(position, traversal.check)
            if position == traversal.root:
                traversal.root_tactics = report
                traversal.root_candidate_count = len(report.candidates)
            source = report.candidates
        else:
            source = (self.candidates(position) if self.cooperative_candidates is None else
                      self.cooperative_candidates(position, traversal.check))
        for move in source:
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
        if position == traversal.root:
            traversal.root_candidate_count = len(moves)
        if self.ordering is None and self.tactics is None and not traversal.pv_moves:
            return tuple(moves)
        ranked = []
        for move in moves:
            traversal.check()
            if self.ordering is not None:
                value = self.ordering(position, move, traversal.check)
            elif self.tactics is not None:
                value = self.tactics.ordinary_rank(position, move, traversal.check)
            else:
                value = 0
            priority = 2 if report is not None and move in report.wins else (
                1 if report is not None and move in report.defenses else 0)
            ranked.append(((priority, move == traversal.pv_moves.get(position), value), move))
        traversal.check()
        from omok.tactics import checked_sorted
        ranked = checked_sorted(ranked, lambda item: tuple(-v for v in item[0]), traversal.check)
        traversal.check()
        return tuple(move for _, move in ranked)

    def search(self, position: Position, depth: int, *,
               reference: bool = False, limits: SearchLimits | None = None) -> SearchResult:
        if type(depth) is not int or depth < 0:
            raise ValueError('Depth must be a nonnegative integer.')
        if position.outcome != 'ongoing':
            return SearchResult(None, self.score(position, position.side_to_move), True)
        fallback = next(legal_moves(position))
        traversal = _Traversal(SearchLimits() if limits is None else limits, self.clock, root=position)
        try:
            return replace(self._root(position, depth, reference, traversal),
                           completed_depth=depth, attempted_depth=depth, pv_status='complete',
                           tactics=traversal.root_tactics, root_candidate_count=traversal.root_candidate_count)
        except SearchCancelled as error:
            if traversal.root_tactics is not None and traversal.root_tactics.wins:
                fallback = traversal.root_tactics.wins[0]
            return SearchResult(fallback, None, False, tactics=traversal.root_tactics,
                                root_candidate_count=traversal.root_candidate_count, nodes=traversal.nodes,
                                cutoffs=traversal.cutoffs, cancellation=str(error), attempted_depth=depth)

    def _leaf(self, position: Position, perspective: int, traversal: _Traversal) -> int:
        traversal.check()
        value = self.score(position, perspective, check=traversal.check)
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
        best_line: tuple[Coordinate, ...] = ()
        for move in self._moves(position, traversal):
            traversal.check()
            child = position.play(move).position
            if reference:
                child_value, line = self._unpruned(child, depth - 1, 1 - position.side_to_move, traversal)
            else:
                child_value, line = self._alpha_beta(child, depth - 1, 1 - position.side_to_move,
                                          -FULL_WINDOW, -best, traversal)
            value = -child_value
            if value > best:
                best, optimal = value, [move]
                best_line = (move,) + line
            elif value == best:
                optimal.append(move)
        traversal.check()
        return SearchResult(optimal[0], best, True, tuple(optimal) if reference else None,
                            traversal.nodes, traversal.cutoffs, principal_variation=best_line)

    def _unpruned(self, position: Position, depth: int, perspective: int,
                  traversal: _Traversal) -> tuple[int, tuple[Coordinate, ...]]:
        traversal.visit()
        if position.outcome != 'ongoing' or depth == 0:
            return self._leaf(position, perspective, traversal), ()
        best = -FULL_WINDOW
        best_line: tuple[Coordinate, ...] = ()
        for move in self._moves(position, traversal):
            traversal.check()
            value, line = self._unpruned(position.play(move).position, depth - 1,
                                         1 - perspective, traversal)
            if -value > best:
                best, best_line = -value, (move,) + line
        return best, best_line

    def _alpha_beta(self, position: Position, depth: int, perspective: int,
                    alpha: int, beta: int, traversal: _Traversal
                    ) -> tuple[int, tuple[Coordinate, ...]]:
        """Fail-soft: return the best observed value even beyond the window."""
        traversal.visit()
        if position.outcome != 'ongoing' or depth == 0:
            return self._leaf(position, perspective, traversal), ()
        best = -FULL_WINDOW
        best_line: tuple[Coordinate, ...] = ()
        for move in self._moves(position, traversal):
            traversal.check()
            child = position.play(move).position
            value, line = self._alpha_beta(child, depth - 1, 1 - perspective,
                                           -beta, -alpha, traversal)
            if -value > best:
                best, best_line = -value, (move,) + line
            alpha = max(alpha, best)
            if alpha >= beta:
                traversal.cutoffs += 1
                break
        return best, best_line

    def iterative(self, position: Position, max_depth: int, *,
                  limits: SearchLimits | None = None,
                  soft_deadline: float | None = None) -> SearchResult:
        """Commit only complete iterations under one shared traversal budget."""
        if type(max_depth) is not int or max_depth < 1:
            raise ValueError('Maximum depth must be a positive integer.')
        if soft_deadline is not None and not isfinite(soft_deadline):
            raise ValueError('Soft deadline must be finite or None.')
        if position.outcome != 'ongoing':
            return SearchResult(None, self.score(position, position.side_to_move), True,
                                pv_status='complete')
        committed = SearchResult(next(legal_moves(position)), None, False)
        traversal = _Traversal(SearchLimits() if limits is None else limits, self.clock, root=position)
        attempted = 0
        try:
            for depth in range(1, max_depth + 1):
                if soft_deadline is not None and self.clock() >= soft_deadline:
                    return replace(committed, nodes=traversal.nodes, cutoffs=traversal.cutoffs,
                                   cancellation='soft_stop')
                attempted = depth
                traversal.check()
                result = self._root(position, depth, False, traversal)
                committed = replace(result, completed_depth=depth, attempted_depth=depth,
                                    pv_status='complete', tactics=traversal.root_tactics,
                                    root_candidate_count=traversal.root_candidate_count)
                leaf = position
                traversal.pv_moves.clear()
                for move in committed.principal_variation:
                    traversal.check()
                    traversal.pv_moves[leaf] = move
                    leaf = leaf.play(move).position
        except SearchCancelled as error:
            if committed.completed_depth == 0 and traversal.root_tactics is not None:
                fallback = (traversal.root_tactics.wins[0] if traversal.root_tactics.wins
                            else committed.move)
                committed = replace(committed, move=fallback, tactics=traversal.root_tactics,
                                    root_candidate_count=traversal.root_candidate_count)
            return replace(committed, nodes=traversal.nodes, cutoffs=traversal.cutoffs,
                           tactics=traversal.root_tactics, root_candidate_count=traversal.root_candidate_count,
                           attempted_depth=attempted, cancellation=str(error))
        return committed
