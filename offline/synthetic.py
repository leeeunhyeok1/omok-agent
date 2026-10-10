# AI-written by OpenAI Codex, for issue #30.
"""Offline authored strategies; only rules are shared with the candidate."""
from collections.abc import Callable
from functools import partial
from random import Random

from omok.simulator import AXES, Coordinate, EMPTY, Position, SIZE


def nearby(position: Position) -> list[Coordinate]:
    occupied = [(r, c) for r in range(SIZE) for c in range(SIZE)
                if position.board[r][c] != EMPTY]
    if not occupied:
        return [(9, 9)]
    return sorted({(r + dr, c + dc) for r, c in occupied
                   for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                   if 0 <= r + dr < SIZE and 0 <= c + dc < SIZE
                   and position.board[r + dr][c + dc] == EMPTY})


def central(move: Coordinate) -> int:
    return -abs(move[0] - 9) - abs(move[1] - 9)


def local(position: Position, random: Random) -> Coordinate:
    def density(move: Coordinate) -> tuple[int, int]:
        r, c = move
        count = sum(position.board[x][y] == position.side_to_move
                    for x in range(max(0, r - 1), min(SIZE, r + 2))
                    for y in range(max(0, c - 1), min(SIZE, c + 2)))
        return count, central(move)
    return max(nearby(position), key=density)


def runs(position: Position, color: int) -> list[int]:
    lengths = []
    for r in range(SIZE):
        for c in range(SIZE):
            if position.board[r][c] != color:
                continue
            for dr, dc in AXES:
                x, y = r - dr, c - dc
                if 0 <= x < SIZE and 0 <= y < SIZE and position.board[x][y] == color:
                    continue
                length = 0
                x, y = r, c
                while 0 <= x < SIZE and 0 <= y < SIZE and position.board[x][y] == color:
                    length += 1
                    x, y = x + dr, y + dc
                lengths.append(length)
    return lengths


def result(position: Position, color: int) -> int:
    if position.outcome == ('black_win' if color == 0 else 'white_win'):
        return 1
    if position.outcome in ('black_win', 'white_win'):
        return -1
    return 0


def aggressive(position: Position, random: Random) -> Coordinate:
    def attack(move: Coordinate) -> tuple[int, int, int]:
        child = position.play(move).position
        # Overlines are not winning runs and are deliberately unattractive.
        length = max((n for n in runs(child, position.side_to_move) if n <= 5), default=0)
        return result(child, position.side_to_move), length, central(move)
    return max(nearby(position), key=attack)


def defensive(position: Position, random: Random) -> Coordinate:
    color = position.side_to_move
    def safety(move: Coordinate) -> tuple[int, int, int, int]:
        child = position.play(move).position
        if child.outcome != 'ongoing':
            return result(child, color), 0, 0, central(move)
        replies = nearby(child)
        wins = sum(result(child.play(reply).position, 1 - color) == 1 for reply in replies)
        pressure = sum(n * n for n in runs(child, 1 - color) if n < 5)
        return 0, -wins, -pressure, central(move)
    return max(nearby(position), key=safety)


def capture(position: Position, random: Random) -> Coordinate:
    def collection(move: Coordinate) -> tuple[int, int, int]:
        transition = position.play(move)
        return result(transition.position, position.side_to_move), len(transition.captured), central(move)
    return max(nearby(position), key=collection)


def windows(position: Position, color: int) -> tuple[int, int]:
    """Unblocked five-cell windows, including gaps; not claims of forced wins."""
    fours = threes = 0
    for r in range(SIZE):
        for c in range(SIZE):
            for dr, dc in AXES:
                if not (0 <= r + 4 * dr < SIZE and 0 <= c + 4 * dc < SIZE):
                    continue
                cells = [position.board[r + i * dr][c + i * dc] for i in range(5)]
                if 1 - color in cells:
                    continue
                count = cells.count(color)
                fours += count == 4
                threes += count == 3
    return fours, threes


def pattern(position: Position, random: Random) -> Coordinate:
    def threats(move: Coordinate) -> tuple[int, int, int, int]:
        child = position.play(move).position
        fours, threes = windows(child, position.side_to_move)
        return result(child, position.side_to_move), fours, threes, central(move)
    return max(nearby(position), key=threats)


def static(position: Position, color: int) -> int:
    if position.outcome != 'ongoing':
        return 1000000 * result(position, color)
    return (sum(n ** 3 for n in runs(position, color) if n < 5)
            - sum(n ** 3 for n in runs(position, 1 - color) if n < 5))


def search_moves(position: Position) -> list[Coordinate]:
    moves = nearby(position)
    other = Position(position.board, 1 - position.side_to_move)
    children = {m: position.play(m).position for m in moves}
    forcing = {m for m in moves if result(children[m], position.side_to_move) == 1
               or result(other.play(m).position, other.side_to_move) == 1}
    ranked = sorted(moves, key=lambda m: (static(children[m], position.side_to_move), central(m)), reverse=True)
    return sorted(forcing | set(ranked[:8]))


def shallow(position: Position, random: Random, *, depth: int) -> Coordinate:
    """Independent bounded minimax, not the candidate's Negamax/evaluator."""
    color = position.side_to_move
    def score(move: Coordinate) -> tuple[int, int]:
        child = position.play(move).position
        value = static(child, color)
        if depth == 2 and child.outcome == 'ongoing':
            value = min(static(child.play(reply).position, color) for reply in search_moves(child))
        return value, central(move)
    return max(search_moves(position), key=score)


def frontier_random(position: Position, random: Random) -> Coordinate:
    return random.choice(nearby(position))


def space(position: Position, random: Random) -> Coordinate:
    """Reserved space-filling design: avoid the existing occupied frontier."""
    occupied = [(r, c) for r in range(SIZE) for c in range(SIZE) if position.board[r][c] != EMPTY]
    legal = [(r, c) for r in range(SIZE) for c in range(SIZE) if position.board[r][c] == EMPTY]
    def separation(move: Coordinate) -> tuple[int, int]:
        distance = min((max(abs(move[0] - r), abs(move[1] - c)) for r, c in occupied), default=0)
        return distance, central(move)
    return max(legal, key=separation)


STRATEGIES: dict[str, Callable[[Position, Random], Coordinate]] = {
    'local': local, 'aggressive': aggressive, 'defensive': defensive,
    'capture': capture, 'pattern': pattern,
    'search1': partial(shallow, depth=1), 'search2': partial(shallow, depth=2),
    'random': frontier_random, 'space': space,
}


class SyntheticPlayer:
    def __init__(self, color: int, *, strategy: str, seed: int = 0) -> None:
        if type(color) is not int or color not in (0, 1):
            raise ValueError('Color must be 0 or 1.')
        self.choose = STRATEGIES[strategy]
        self.color = color
        self.random = Random(seed)

    def take_turn(self, board: list[list[int]], time: float) -> Coordinate:
        position = Position(board, self.color)
        if position.outcome != 'ongoing':
            raise ValueError('No move on terminal position.')
        return self.choose(position, self.random)


def create(color: int, *, strategy: str, seed: int = 0) -> SyntheticPlayer:
    return SyntheticPlayer(color, strategy=strategy, seed=seed)
