# AI-written by OpenAI Codex, for issue #17.
"""Full recomputation of canonical fours and unique completion coordinates."""
from collections.abc import Callable
from typing import Any

from omok.simulator import AXES, EMPTY, SIZE, Position
from omok.tactics import immediate_wins

LINE_FEATURES = ('open_four', 'closed_four', 'broken_four',
                 'geometric_completion', 'verified_win', 'overline_trap')


def line_features(position: Position, check: Callable[[], None]) -> dict[str, Any]:
    reports = []
    for color in (0, 1):
        report: dict[str, Any] = dict.fromkeys(LINE_FEATURES, 0)
        completions = set()
        traps = set()
        # Each axis traverses each maximal board line once, in its canonical direction.
        for dr, dc in AXES:
            for row in range(SIZE):
                check()
                for col in range(SIZE):
                    if 0 <= row - dr < SIZE and 0 <= col - dc < SIZE:
                        continue
                    cells = []
                    r, c = row, col
                    while 0 <= r < SIZE and 0 <= c < SIZE:
                        cells.append((r, c))
                        r, c = r + dr, c + dc
                    values = [position.board[r][c] for r, c in cells]
                    start = 0
                    while start < len(values):
                        check()
                        end = start
                        while end < len(values) and values[end] == color:
                            end += 1
                        if end - start == 4:
                            openings = sum(0 <= i < len(values) and values[i] == EMPTY
                                           for i in (start - 1, end))
                            if openings:
                                report['open_four' if openings == 2 else 'closed_four'] += 1
                        start = max(start + 1, end)
                    for i, value in enumerate(values):
                        check()
                        if value != EMPTY:
                            continue
                        left, right = i - 1, i + 1
                        while left >= 0 and values[left] == color:
                            left -= 1
                        while right < len(values) and values[right] == color:
                            right += 1
                        length = right - left - 1
                        if length >= 6:
                            traps.add(cells[i])
                        elif length == 5:
                            completions.add(cells[i])
                            if left < i - 1 and right > i + 1:
                                report['broken_four'] += 1
        check()
        # The established tactical detector resolves captures and both-color outcomes.
        # Terminal input has no legal continuations; static geometry remains inspectable.
        wins = (immediate_wins(Position(position.board, color), check)
                if position.outcome == 'ongoing' else ())
        check()
        report.update(geometric_completion=len(completions), verified_win=len(wins),
                      overline_trap=len(traps), geometric_completions=sorted(completions),
                      verified_wins=list(wins), overline_traps=sorted(traps))
        reports.append(report)
    return {'black': reports[0], 'white': reports[1]}
