# AI-written by OpenAI Codex, for issue #12.
"""Independent complete small-board tactical enumeration and public timing."""
import json
import platform
from time import monotonic

from omok.player import IterativePlayer
from omok.search import legal_moves
from omok.simulator import Position
from omok.tactics import TacticalPolicy
from verification.reference import ReferencePosition


def reference_tactics(position: ReferencePosition) -> dict:
    """Exhaustive rules-reference placements/replies; no engine pattern filter."""
    color = position.side_to_move
    own_win = 'black_win' if color == 0 else 'white_win'
    other_win = 'white_win' if color == 0 else 'black_win'
    opponent = ReferencePosition(position.board, 1 - color)
    threats = tuple(m for m in legal_moves(opponent) if opponent.play(m).position.outcome == other_win)
    wins, draws, losses, defenses = [], [], [], []
    for move in legal_moves(position):
        child = position.play(move).position
        if child.outcome == own_win:
            wins.append(move)
        elif child.outcome == 'draw':
            draws.append(move)
        elif child.outcome == other_win:
            losses.append(move)
        if threats:
            if child.outcome in (own_win, 'draw'):
                defenses.append(move)
            elif child.outcome == 'ongoing':
                replies = tuple(child.play(reply).position.outcome for reply in legal_moves(child))
                if other_win not in replies:
                    defenses.append(move)
    return {'wins': tuple(wins), 'draws': tuple(draws), 'losses': tuple(losses),
            'threats': threats, 'defenses': tuple(defenses)}


def small_fixture(color: int) -> list[list[int]]:
    board = [[((r + 2 * c) % 4 // 2) ^ color for c in range(19)] for r in range(19)]
    board[0][:4] = [1 - color] * 4
    board[0][5] = color
    for row, col in ((0, 4), (0, 10), (0, 14)):
        board[row][col] = -1
    return board


def main() -> None:
    validation = []
    for color in (0, 1):
        board = small_fixture(color)
        expected = reference_tactics(ReferencePosition(board, color))
        report = TacticalPolicy(full_width=True).analyze(Position(board, color))
        assert report.complete
        for name in ('wins', 'threats', 'defenses'):
            assert getattr(report, name) == expected[name]
        validation.append({'color': color, 'reference': expected})
    records = []
    for color in (0, 1):
        empty = [[-1] * 19 for _ in range(19)]
        win = [row[:] for row in empty]
        win[9][5:9] = [color] * 4
        capture = [row[:] for row in empty]
        for row, col in ((9, 6), (9, 7), (9, 8), (9, 9), (8, 7)):
            capture[row][col] = 1 - color
        capture[10][7] = color
        for name, board in (('empty', empty), ('win', win), ('capture-defense', capture),
                            ('dense', small_fixture(color))):
            player = IterativePlayer(color)
            for remaining in (1, 3, 20, 200, 60000, -1):
                before = [row[:] for row in board]
                start = monotonic()
                move = player.take_turn(board, remaining)
                elapsed = (monotonic() - start) * 1000
                ReferencePosition(before, color).play(move)
                assert board == before
                result = player.last_result
                assert result is not None
                report = result.tactics
                records.append({'fixture': name, 'color': color, 'remaining_ms': remaining,
                                'elapsed_ms': elapsed, 'allocation_ms': player.last_allocation_ms,
                                'move': move, 'depth': result.completed_depth,
                                'attempted_depth': result.attempted_depth, 'score': result.score,
                                'candidate_count': result.root_candidate_count,
                                'cancellation': result.cancellation,
                                'tactics_complete': report.complete if report else None,
                                'defenses_complete': report.defenses_complete if report else None,
                                'exceeds_incoming': remaining > 0 and elapsed > remaining})
        # Six actual board-updating turns against first-legal replies, one 40 ms clock.
        remaining = 40.0
        board = [row[:] for row in empty]
        for turn in range(6):
            if remaining <= 0:
                break
            before = [row[:] for row in board]
            start = monotonic()
            move = player.take_turn(board, remaining)
            elapsed = (monotonic() - start) * 1000
            oracle = ReferencePosition(before, color).play(move).position
            assert board == before
            records.append({'fixture': 'cumulative', 'color': color, 'turn': turn,
                            'remaining_ms': remaining, 'elapsed_ms': elapsed, 'move': move,
                            'exceeds_incoming': elapsed > remaining})
            remaining -= elapsed
            if oracle.outcome != 'ongoing':
                break
            oracle = oracle.play(next(legal_moves(oracle))).position
            if oracle.outcome != 'ongoing':
                break
            board = [list(row) for row in oracle.board]
    print(json.dumps({'python': platform.python_version(), 'platform': platform.platform(),
                      'workers': 1, 'radius': 2, 'cap': 24, 'max_depth': 8,
                      'max_nodes': 10000, 'max_time_ms': 100,
                      'reference_enumeration': validation, 'probes': records}, indent=2))


if __name__ == '__main__':
    main()
