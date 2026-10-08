# AI-written by OpenAI Codex, for issue #12.
"""Complete immediate tactics, conservative interruption and local membership."""
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cmp_to_key
from typing import Literal, TypeVar

from omok.search import SearchCancelled, legal_moves
from omok.simulator import AXES, Coordinate, EMPTY, Position, SIZE

Check = Callable[[], None]
MoveKind = Literal['win', 'draw', 'opponent_win', 'continuation']
T = TypeVar('T')


def classify(position: Position, mover: int) -> MoveKind:
    """Classify an already resolved simulator outcome using explicit mover color."""
    if position.outcome == 'ongoing':
        return 'continuation'
    if position.outcome == 'draw':
        return 'draw'
    return 'win' if position.outcome == ('black_win' if mover == 0 else 'white_win') else 'opponent_win'


def checked_sorted(items: Iterable[T], key: Callable[[T], tuple], check: Check) -> list[T]:
    """Check both key generation and comparisons inside Python's sort."""
    ranked = []
    for item in items:
        check()
        ranked.append((key(item), item))
    def compare(left: tuple, right: tuple) -> int:
        check()
        return (left[0] > right[0]) - (left[0] < right[0])
    ranked.sort(key=cmp_to_key(compare))
    check()
    return [item for _, item in ranked]


def _five_cells(position: Position, color: int, check: Check) -> Iterable[Coordinate]:
    """Necessary exact-five placements; final truth always comes from play().

    On a live board own stones cannot be removed by one's move. A new own five
    must pass through the placement, even after captures. All axes and both rays
    are counted to maximal length, so this filter is complete for strict wins.
    """
    board = position.board
    for row, col in legal_moves(position):
        check()
        for dr, dc in AXES:
            length = 1
            for sign in (-1, 1):
                r, c = row + sign * dr, col + sign * dc
                while 0 <= r < SIZE and 0 <= c < SIZE and board[r][c] == color:
                    check()
                    length += 1
                    r, c = r + sign * dr, c + sign * dc
            if length == 5:
                yield row, col
                break


def _verified_wins(position: Position, check: Check) -> Iterable[Coordinate]:
    for move in _five_cells(position, position.side_to_move, check):
        check()
        if classify(position.play(move).position, position.side_to_move) == 'win':
            yield move
    check()


def immediate_wins(position: Position, check: Check) -> tuple[Coordinate, ...]:
    return tuple(_verified_wins(position, check))


def static_rank(position: Position, move: Coordinate, check: Check) -> int:
    """Untuned ordering only: adjacent stones, then distance from board center."""
    row, col = move
    neighbors = 0
    for r in range(max(0, row - 1), min(SIZE, row + 2)):
        check()
        for c in range(max(0, col - 1), min(SIZE, col + 2)):
            neighbors += position.board[r][c] != EMPTY
    return neighbors * SIZE - abs(row - SIZE // 2) - abs(col - SIZE // 2)


@dataclass(frozen=True, slots=True)
class TacticalResult:
    candidates: tuple[Coordinate, ...]
    wins: tuple[Coordinate, ...] = ()
    threats: tuple[Coordinate, ...] = ()
    defenses: tuple[Coordinate, ...] = ()
    complete: bool = False
    wins_complete: bool = False
    threats_complete: bool = False
    defenses_complete: bool = False
    cancellation: str | None = None


@dataclass(frozen=True, slots=True)
class TacticalPolicy:
    radius: int = 2
    cap: int = 24
    full_width: bool = False
    ordinary_rank: Callable[[Position, Coordinate, Check], int] = static_rank

    def __post_init__(self) -> None:
        if type(self.radius) is not int or not 0 <= self.radius < SIZE:
            raise ValueError('Radius must be an integer from 0 to 18.')
        if type(self.cap) is not int or self.cap < 1:
            raise ValueError('Ordinary cap must be a positive integer.')
        if type(self.full_width) is not bool:
            raise ValueError('Full-width setting must be boolean.')

    def analyze(self, position: Position, check: Check = lambda: None) -> TacticalResult:
        if position.outcome != 'ongoing':
            return TacticalResult((), complete=True, wins_complete=True,
                                  threats_complete=True, defenses_complete=True)
        # Bounded 361-cell snapshot retained even if the very first check expires.
        legal = tuple(legal_moves(position))
        wins: list[Coordinate] = []
        threats: tuple[Coordinate, ...] = ()
        defenses: list[Coordinate] = []
        wins_complete = threats_complete = defenses_complete = False
        try:
            for move in _verified_wins(position, check):
                wins.append(move)
            wins_complete = True
            check()
            opponent = Position(position.board, 1 - position.side_to_move)
            threats = immediate_wins(opponent, check)
            threats_complete = True
            if threats:
                for move in legal:
                    check()
                    child = position.play(move).position
                    kind = classify(child, position.side_to_move)
                    if kind in ('win', 'draw'):
                        defenses.append(move)
                    elif kind == 'continuation':
                        refuted = False
                        for reply in threats:
                            check()
                            if (child.board[reply[0]][reply[1]] == EMPTY
                                    and classify(child.play(reply).position, 1 - position.side_to_move) == 'win'):
                                refuted = True
                                break
                        if not refuted and not immediate_wins(child, check):
                            # Surviving old threats is insufficient: scan new ones too.
                            defenses.append(move)
            defenses_complete = True
            ordinary = self.local_moves(position, check)
            ranked = checked_sorted(ordinary, lambda m: (-self.ordinary_rank(position, m, check), m), check)
            if self.full_width:
                members = legal
            elif threats and defenses:
                # Safe against the current one-ply threat, not a forced game win.
                members = tuple(checked_sorted(set(defenses) | set(wins), lambda m: m, check))
            else:
                members = tuple(checked_sorted(set(ranked[:self.cap]) | set(wins), lambda m: m, check))
            check()
            return TacticalResult(members, tuple(wins), threats, tuple(defenses),
                                  complete=True, wins_complete=True,
                                  threats_complete=True, defenses_complete=True)
        except SearchCancelled as error:
            return TacticalResult(legal, tuple(wins), threats, tuple(defenses),
                                  wins_complete=wins_complete, threats_complete=threats_complete,
                                  defenses_complete=defenses_complete, cancellation=str(error))

    def local_moves(self, position: Position, check: Check) -> tuple[Coordinate, ...]:
        cells: set[Coordinate] = set()
        occupied = False
        for row in range(SIZE):
            check()
            for col in range(SIZE):
                if position.board[row][col] == EMPTY:
                    continue
                occupied = True
                for r in range(max(0, row - self.radius), min(SIZE, row + self.radius + 1)):
                    check()
                    for c in range(max(0, col - self.radius), min(SIZE, col + self.radius + 1)):
                        if position.board[r][c] == EMPTY:
                            cells.add((r, c))
        if not occupied:
            return ((SIZE // 2, SIZE // 2),)
        if not cells:
            return tuple(legal_moves(position))
        return tuple(cells)
