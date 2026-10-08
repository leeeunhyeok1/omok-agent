# AI-written by OpenAI Codex, for issue #10.
"""Reproducible public-turn timing probes; no strength or hard-deadline claim."""
import json
import platform
from time import monotonic

from omok.player import FixedDepthPlayer
from omok.simulator import Position


def main() -> None:
    empty = [[-1] * 19 for _ in range(19)]
    capture = [row[:] for row in empty]
    capture[9][10:13] = [1, 1, 0]
    win = [row[:] for row in empty]
    win[9][5:9] = [0] * 4
    dense = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
    dense[0][0] = -1
    records = []
    for name, board in (('empty', empty), ('capture', capture), ('win', win), ('dense', dense)):
        for color in (0, 1):
            root = Position(board, color)
            for depth in (1, 2):
                player = FixedDepthPlayer(color, depth=depth)
                for remaining in (-1, 60000, 3, 0.5):
                    start = monotonic()
                    move = player.take_turn(board, remaining)
                    elapsed_ms = (monotonic() - start) * 1000
                    root.play(move)
                    if board != [list(row) for row in root.board]:
                        raise AssertionError('Caller input mutated.')
                    result = player.last_result
                    assert result is not None
                    records.append({'fixture': name, 'color': color, 'depth': depth,
                                    'remaining_ms': remaining, 'elapsed_ms': elapsed_ms,
                                    'move': move, 'score': result.score,
                                    'completed': result.completed, 'nodes': result.nodes,
                                    'cutoffs': result.cutoffs, 'cancellation': result.cancellation})
    print(json.dumps({'python': platform.python_version(), 'platform': platform.platform(),
                      'max_nodes': 10000, 'max_time_ms': 100, 'probes': records}, indent=2))


if __name__ == '__main__':
    main()
