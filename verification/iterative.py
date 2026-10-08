# AI-written by OpenAI Codex, for issue #11.
"""Actual public-turn timing, with independent legality and input checks."""
import json
import platform
from time import monotonic

from omok.player import IterativePlayer
from verification.reference import ReferencePosition


def probe(player, board, remaining, fixture, mode):
    before = [row[:] for row in board]
    failures = []
    start = monotonic()
    move = player.take_turn(board, remaining)
    elapsed = (monotonic() - start) * 1000
    oracle = ReferencePosition(before, player.color).play(move).position
    if board != before:
        failures.append('input_mutation')
    result = player.last_result
    assert result is not None
    return {'fixture': fixture, 'mode': mode, 'color': player.color,
            'remaining_ms': remaining, 'elapsed_ms': elapsed,
            'allocation_ms': player.last_allocation_ms, 'move': move,
            'completed_depth': result.completed_depth, 'attempted_depth': result.attempted_depth,
            'fallback': result.completed_depth == 0, 'cancellation': result.cancellation,
            'nodes': result.nodes, 'pv_status': result.pv_status,
            'exceeds_incoming_clock': remaining > 0 and elapsed > remaining,
            'failures': failures}, oracle


def main():
    empty = [[-1] * 19 for _ in range(19)]
    sparse = [row[:] for row in empty]
    sparse[9][10:13] = [1, 1, 0]
    tactical = [row[:] for row in empty]
    tactical[9][5:9] = [0] * 4
    dense = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
    dense[0][0] = -1
    records = []
    for name, board in (('empty', empty), ('sparse', sparse), ('tactical', tactical), ('dense', dense)):
        for color in (0, 1):
            player = IterativePlayer(color)
            for remaining in (-2, 0, 0.001, 0.1, 1, 3, 5, 20, 200, 60000, -1):
                for repeat in range(3):
                    record, _ = probe(player, board, remaining, name, 'independent_probe')
                    record['repeat'] = repeat
                    records.append(record)
            # Reuse the actual decreasing clock and updated board, without resetting each call.
            remaining = 40.0
            current = [row[:] for row in board]
            for turn in range(12):
                if ReferencePosition(current, color).outcome != 'ongoing' or remaining <= 0:
                    break
                record, oracle = probe(player, current, remaining, name, 'cumulative_clock')
                record['turn'] = turn
                records.append(record)
                remaining -= record['elapsed_ms']
                if oracle.outcome != 'ongoing':
                    break
                opponent_move = next((r, c) for r in range(19) for c in range(19)
                                     if oracle.board[r][c] == -1)
                current = [list(row) for row in oracle.play(opponent_move).position.board]
    print(json.dumps({'python': platform.python_version(), 'platform': platform.platform(),
                      'workers': 1, 'max_depth': 8, 'max_nodes': 10000,
                      'notes': 'Cooperative cancellation cannot preempt conversion, transitions, '
                               'sorting, blocking callbacks or scheduling delays. Tiny clocks may '
                               'be exceeded by mandatory validation and fallback alone.',
                      'probes': records}, indent=2))


if __name__ == '__main__':
    main()
