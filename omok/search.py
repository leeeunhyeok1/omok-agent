# AI-written by OpenAI Codex, for issues #10–#13; issue #21 measurement additions.
"""Fixed-depth and committed iterative search over immutable positions."""
from dataclasses import dataclass, replace, field
from collections.abc import Callable, Iterable, Iterator
from math import isfinite
from time import monotonic
from typing import TYPE_CHECKING, Hashable, Any

from omok.measurement import EvaluationProfile

if TYPE_CHECKING:
    from omok.evaluation import EvaluationConfig
    from omok.tactics import TacticalPolicy, TacticalResult

from omok.simulator import Coordinate, EMPTY, Position, SIZE
from omok.transposition import Bound, TableEntry, TranspositionTable

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


def fallback_move(position: Position) -> Coordinate:
    """Cheap legal default: nearby stones, then the center, then coordinates.

    This bounded board scan needs no search budget or evaluator. Tactical and
    evaluated choices replace it as soon as the search has useful evidence.
    """
    from omok.tactics import static_rank
    return min(legal_moves(position), key=lambda move: (-static_rank(
        position, move, lambda: None), move))


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
    table_probes: int = 0
    table_hits: int = 0
    table_value_cutoffs: int = 0
    evaluation_calls: int = 0
    evaluation_completed: int = 0
    evaluation_cancelled: int = 0
    evaluation_cache_hits: int = 0
    evaluation_profile: dict[str, Any] | None = None
    fallback_source: str | None = None


@dataclass(slots=True)
class _Traversal:
    limits: SearchLimits
    clock: Callable[[], float]
    nodes: int = 0
    cutoffs: int = 0
    table_probes: int = 0
    table_hits: int = 0
    table_value_cutoffs: int = 0
    evaluation_calls: int = 0
    evaluation_completed: int = 0
    evaluation_cancelled: int = 0
    evaluation_cache_hits: int = 0
    profile: EvaluationProfile | None = None
    compatibility: Hashable = None
    use_table: bool = True
    root: Position | None = None
    root_tactics: 'TacticalResult | None' = None
    root_candidate_count: int = 0
    root_ordered_move: Coordinate | None = None
    partial_root_move: Coordinate | None = None
    pv_moves: dict[Position, Coordinate] = field(default_factory=dict)

    def report(self, result: SearchResult) -> SearchResult:
        return replace(result, nodes=self.nodes, cutoffs=self.cutoffs,
                       table_probes=self.table_probes, table_hits=self.table_hits,
                       table_value_cutoffs=self.table_value_cutoffs,
                       evaluation_calls=self.evaluation_calls,
                       evaluation_completed=self.evaluation_completed,
                       evaluation_cancelled=self.evaluation_cancelled,
                       evaluation_cache_hits=self.evaluation_cache_hits,
                       evaluation_profile=None if self.profile is None else self.profile.snapshot())

    def check(self) -> None:
        self.limits.check(self.clock)

    def visit(self) -> None:
        self.check()
        if self.limits.max_nodes is not None and self.nodes >= self.limits.max_nodes:
            raise SearchCancelled('node_limit')
        self.nodes += 1

    def fallback(self, initial: Coordinate) -> tuple[Coordinate, str]:
        report = self.root_tactics
        if report is not None and report.wins:
            return report.wins[0], 'verified_win'
        if self.partial_root_move is not None:
            return self.partial_root_move, 'partial_depth_one'
        # Each recorded defense has already survived the complete immediate
        # reply check, even if enumeration of other defenses was interrupted.
        if report is not None and report.defenses:
            if self.root_ordered_move in report.defenses:
                return self.root_ordered_move, 'verified_defense'
            return report.defenses[0], 'verified_defense'
        if self.root_ordered_move is not None:
            return self.root_ordered_move, 'root_ordering'
        return initial, 'static_ordering'


@dataclass(frozen=True, slots=True, eq=False)
class _Identity:
    value: object

    def __hash__(self) -> int:
        return id(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Identity) and self.value is other.value


class FixedDepthSearch:
    def __init__(self, *, candidates: CandidateSource = legal_moves,
                 evaluator: Evaluator = material_evaluation,
                 clock: Callable[[], float] = monotonic,
                 cooperative_candidates: Callable[[Position, Callable[[], None]], Iterable[Coordinate]] | None = None,
                 cooperative_evaluator: Callable[[Position, Callable[[], None]], int] | None = None,
                 tactics: 'TacticalPolicy | None' = None,
                 ordering: Callable[[Position, Coordinate, Callable[[], None]], int] | None = None,
                 table: TranspositionTable | None = None,
                 compatibility: Hashable = None,
                 evaluation_config: 'EvaluationConfig | None' = None,
                 profile_every: int = 0) -> None:
        if type(profile_every) is not int or profile_every < 0:
            raise ValueError('Profile interval must be a nonnegative integer.')
        self.profile_every = profile_every
        self.candidates = candidates
        self.evaluator = evaluator
        self.clock = clock
        self.cooperative_candidates = cooperative_candidates
        self.cooperative_evaluator = cooperative_evaluator
        self.ordering = ordering
        self.tactics = tactics
        self.table = table
        self.compatibility = compatibility
        self._cache_namespace = object()
        if evaluation_config is not None:
            self.set_evaluation_config(evaluation_config)

    def set_evaluation_config(self, config: 'EvaluationConfig') -> None:
        """Validate before mutation, then release all old scores and hints."""
        from omok.evaluation import ConfiguredEvaluator
        evaluator = ConfiguredEvaluator(config)
        self.evaluator = evaluator
        self.cooperative_evaluator = evaluator
        if self.table is not None:
            self.table.clear()

    def cache_compatibility(self) -> Hashable:
        """Snapshot policy identity; bump compatibility for in-place callback changes."""
        signature = (self._cache_namespace, self.compatibility,
                     *(_Identity(value) for value in (
                         self.candidates, self.evaluator, self.cooperative_candidates,
                         self.cooperative_evaluator, self.tactics, self.ordering)),
                     WIN_SCORE, EVALUATION_LIMIT, 'no-extensions-v1')
        hash(signature)
        return signature

    def _store(self, position: Position, depth: int, value: int,
               bound: Bound, line: tuple[Coordinate, ...], traversal: _Traversal) -> None:
        traversal.check()
        if self.table is not None:
            self.table.store(position, traversal.compatibility,
                             TableEntry(depth, value, bound,
                                        line[0] if line else None, line))

    def score(self, position: Position, perspective: int, *,
              check: Callable[[], None] = lambda: None,
              profile: EvaluationProfile | None = None) -> int:
        if type(perspective) is not int or perspective not in (0, 1):
            raise ValueError('Perspective must be 0 or 1.')
        if position.outcome == 'draw':
            return 0
        if position.outcome != 'ongoing':
            winner = 0 if position.outcome == 'black_win' else 1
            return WIN_SCORE if perspective == winner else -WIN_SCORE
        if profile is not None:
            from omok.evaluation import ConfiguredEvaluator
        if profile is not None and isinstance(self.cooperative_evaluator, ConfiguredEvaluator):
            value = self.cooperative_evaluator(position, check, profile=profile)
        elif self.cooperative_evaluator is not None:
            value = self.cooperative_evaluator(position, check)
        elif self.evaluator is material_evaluation:
            value = material_evaluation(position, check=check)
        else:
            value = self.evaluator(position)
        if type(value) is not int or abs(value) > EVALUATION_LIMIT:
            raise ValueError('Evaluator must return a bounded black-centric integer.')
        return value if perspective == 0 else -value

    def _moves(self, position: Position, traversal: _Traversal,
               hint: Coordinate | None = None) -> tuple[Coordinate, ...]:
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
        if hint is None and self.table is not None and traversal.use_table:
            hint = self.table.hint(position, traversal.compatibility)
        if not self._valid_hint(hint, moves):
            hint = None
        if self.ordering is None and self.tactics is None and not traversal.pv_moves and hint not in moves:
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
            ranked.append(((priority, move == traversal.pv_moves.get(position) or move == hint, value), move))
        traversal.check()
        from omok.tactics import checked_sorted
        ranked = checked_sorted(ranked, lambda item: tuple(-v for v in item[0]), traversal.check)
        traversal.check()
        return tuple(move for _, move in ranked)

    @staticmethod
    def _valid_hint(hint: Coordinate | None, moves: Iterable[Coordinate]) -> bool:
        return (type(hint) is tuple and len(hint) == 2
                and all(type(cell) is int for cell in hint) and hint in moves)

    def search(self, position: Position, depth: int, *,
               reference: bool = False, limits: SearchLimits | None = None) -> SearchResult:
        if type(depth) is not int or depth < 0:
            raise ValueError('Depth must be a nonnegative integer.')
        if position.outcome != 'ongoing':
            return SearchResult(None, self.score(position, position.side_to_move), True)
        fallback = fallback_move(position)
        traversal = _Traversal(SearchLimits() if limits is None else limits, self.clock,
                               compatibility=self.cache_compatibility(), use_table=not reference,
                               root=position,
                               profile=EvaluationProfile(self.profile_every) if self.profile_every else None)
        try:
            return traversal.report(replace(self._root(position, depth, reference, traversal),
                           completed_depth=depth, attempted_depth=depth, pv_status='complete',
                           tactics=traversal.root_tactics, root_candidate_count=traversal.root_candidate_count))
        except SearchCancelled as error:
            fallback, source = traversal.fallback(fallback)
            return traversal.report(SearchResult(fallback, None, False, tactics=traversal.root_tactics,
                                root_candidate_count=traversal.root_candidate_count, nodes=traversal.nodes,
                                cutoffs=traversal.cutoffs, cancellation=str(error), attempted_depth=depth,
                                fallback_source=source))

    def _leaf(self, position: Position, perspective: int, traversal: _Traversal) -> int:
        traversal.check()
        if position.outcome != 'ongoing':
            value = self.score(position, perspective, check=traversal.check)
            traversal.check()
            return value
        traversal.evaluation_calls += 1
        try:
            profile = traversal.profile
            if profile is not None and (traversal.evaluation_calls - 1) % profile.every == 0:
                profile.sampled_calls += 1
                value = profile.measure('evaluator_total', lambda: self.score(
                    position, perspective, check=traversal.check, profile=profile))
            else:
                value = self.score(position, perspective, check=traversal.check)
        except SearchCancelled:
            traversal.evaluation_cancelled += 1
            raise
        traversal.evaluation_completed += 1
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
        moves = self._moves(position, traversal)
        traversal.root_ordered_move = moves[0]
        for move in moves:
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
            if depth == 1:
                # Every finished child has the same one-ply horizon. Retain
                # its useful move only; a partial root has no committed score
                # or PV and must never be cached as an exact root result.
                traversal.partial_root_move = optimal[0]
        traversal.check()
        if not reference:
            self._store(position, depth, best, 'exact', best_line, traversal)
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
        # Terminal side_to_move retains the mover: score by explicit perspective.
        if position.outcome != 'ongoing':
            return self._leaf(position, perspective, traversal), ()
        entry = None
        if self.table is not None:
            traversal.table_probes += 1
            entry = self.table.probe(position, traversal.compatibility, depth)
            if entry is not None:
                traversal.table_hits += 1
        if depth == 0:
            if entry is not None and entry.bound == 'exact':
                traversal.evaluation_cache_hits += 1
                traversal.table_value_cutoffs += 1
                return entry.score, ()
            value = self._leaf(position, perspective, traversal)
            self._store(position, depth, value, 'exact', (), traversal)
            return value, ()
        moves = self._moves(position, traversal, None if entry is None else entry.best_move)
        # A malformed or no-longer-selected move cannot provide a usable value/PV.
        if (entry is not None and self._valid_hint(entry.best_move, moves)
                and entry.principal_variation and entry.principal_variation[0] == entry.best_move):
            if entry.bound == 'exact':
                traversal.table_value_cutoffs += 1
                return entry.score, entry.principal_variation
            if entry.bound == 'lower':
                alpha = max(alpha, entry.score)
            else:
                beta = min(beta, entry.score)
            if alpha >= beta:
                traversal.cutoffs += 1
                traversal.table_value_cutoffs += 1
                return entry.score, entry.principal_variation
        # Classify against the effective window, AFTER any cached tightening.
        start_alpha, start_beta = alpha, beta
        best = -FULL_WINDOW
        best_line: tuple[Coordinate, ...] = ()
        for move in moves:
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
        bound: Bound = 'upper' if best <= start_alpha else 'lower' if best >= start_beta else 'exact'
        self._store(position, depth, best, bound, best_line, traversal)
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
        committed = SearchResult(fallback_move(position), None, False,
                                 fallback_source='static_ordering')
        traversal = _Traversal(SearchLimits() if limits is None else limits, self.clock,
                               compatibility=self.cache_compatibility(), root=position,
                               profile=EvaluationProfile(self.profile_every) if self.profile_every else None)
        attempted = 0
        try:
            for depth in range(1, max_depth + 1):
                if soft_deadline is not None and self.clock() >= soft_deadline:
                    return traversal.report(replace(committed, cancellation='soft_stop'))
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
            if committed.completed_depth == 0:
                assert committed.move is not None
                fallback, source = traversal.fallback(committed.move)
                committed = replace(committed, move=fallback, tactics=traversal.root_tactics,
                                    root_candidate_count=traversal.root_candidate_count,
                                    fallback_source=source)
            return traversal.report(replace(
                committed, tactics=traversal.root_tactics,
                root_candidate_count=traversal.root_candidate_count,
                attempted_depth=attempted, cancellation=str(error)))
        return traversal.report(committed)
