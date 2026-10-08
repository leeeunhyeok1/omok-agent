# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
"""Independent local smoke fixture, unrelated to supplied RandomPlayer."""
from random import Random
from omok.simulator import Coordinate, EMPTY, SIZE


class SeededSmokePlayer:
    def __init__(self, color: int, seed: int) -> None:
        if type(color) is not int or color not in (0, 1):
            raise ValueError('Color must be 0 or 1.')
        self.color = color
        self.random = Random(seed)

    def take_turn(self, board: list[list[int]], time: float) -> Coordinate:
        legal = [(r, c) for r in range(SIZE) for c in range(SIZE) if board[r][c] == EMPTY]
        if not legal:
            raise ValueError('No legal move.')
        return self.random.choice(legal)
