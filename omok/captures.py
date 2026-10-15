# AI-written by OpenAI Codex, for issue #19.
"""Legal one-move captures and geometric risk, recomputed on immutable boards."""
from collections.abc import Callable
from typing import Any

from omok.simulator import Coordinate, DIRECTIONS, EMPTY, Position, SIZE
from omok.tactics import classify

CAPTURE_FEATURES = ('capture_move', 'capture_pair', 'multi_pair_move', 'vulnerable_pair')
Pair = tuple[Coordinate, ...]


def capture_features(position: Position, check: Callable[[], None], *,
                     inspection: bool = False) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for color in (0, 1):
        moves = []
        pairs: set[Pair] = set()
        cells: set[Coordinate] = set()
        if position.outcome == 'ongoing':
            check()
            # Every capture has an existing own stone at the far endpoint.
            # Enumerate those anchors rather than all empty cells on the board;
            # group rays by placement so simultaneous captures remain one move.
            placements: dict[Coordinate, set[Pair]] = {}
            for row in range(SIZE):
                check()
                for col in range(SIZE):
                    if position.board[row][col] != color:
                        continue
                    for dr, dc in DIRECTIONS:
                        check()
                        end_row, end_col = row + 3 * dr, col + 3 * dc
                        if not (0 <= end_row < SIZE and 0 <= end_col < SIZE):
                            continue
                        first, second = (row + dr, col + dc), (row + 2 * dr, col + 2 * dc)
                        if (position.board[first[0]][first[1]] == 1 - color
                                and position.board[second[0]][second[1]] == 1 - color
                                and position.board[end_row][end_col] == EMPTY):
                            placements.setdefault((end_row, end_col), set()).add(
                                tuple(sorted((first, second))))
            own = Position(position.board, color) if placements else None
            for move, captured in sorted(placements.items()):
                check()
                assert own is not None
                transition = own.play(move)
                check()  # Cancellation after hypothetical removal publishes nothing.
                removed = [item.cell for item in transition.captured]
                record: dict[str, Any] = {'move': move, 'pair_count': len(captured),
                          'cell_count': len(removed)}
                if inspection:
                    record.update(pairs=sorted(captured), cells=removed,
                                  outcome=transition.position.outcome,
                                  classification=classify(transition.position, color))
                moves.append(record)
                pairs.update(captured)
                cells.update(removed)
        reports.append({'capture_move': len(moves), 'capture_pair': len(pairs),
                        'multi_pair_move': sum(move['pair_count'] > 1 for move in moves),
                        'moves': moves, 'captured_pairs': sorted(pairs),
                        'captured_cells': sorted(cells)})
    for color in (0, 1):
        opposing = reports[1 - color]
        reports[color].update(vulnerable_pair=opposing['capture_pair'],
                              vulnerable_pairs=opposing['captured_pairs'],
                              vulnerable_cells=opposing['captured_cells'])
    check()
    return {'black': reports[0], 'white': reports[1]}
