# AI-written by OpenAI Codex, for issues #17, #18 and #20.
"""Full recomputation of canonical fours and unique completion coordinates."""
from collections.abc import Callable
from typing import Any

from omok.simulator import AXES, EMPTY, SIZE, Position
from omok.tactics import immediate_wins

POTENTIAL_FEATURES = ('open_three', 'broken_three', 'two_stone')

LINE_FEATURES = ('open_four', 'closed_four', 'broken_four',
                 'geometric_completion', 'verified_win', 'overline_trap')


def line_features(position: Position, check: Callable[[], None], *,
                  fours: bool = True, potential: bool = False) -> dict[str, Any]:
    reports = []
    potentials = []
    for color in (0, 1):
        report: dict[str, Any] = dict.fromkeys(LINE_FEATURES, 0)
        units: dict[str, set[tuple[tuple[int, int], ...]]] = {
            name: set() for name in POTENTIAL_FEATURES}
        four_units: dict[str, set[tuple[tuple[int, int], ...]]] = {
            name: set() for name in ('open_four', 'closed_four', 'broken_four')}
        exact_fives = set()
        overlines = set()
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
                    if potential:
                        # Develop to a contiguous four with two exact-five endpoints.
                        # Empty endpoints must exist; outer own stones would make
                        # one completion an overline, so reject that development.
                        for start in range(1, len(values) - 4):
                            check()
                            end = start + 4
                            if values[start - 1] != EMPTY or values[end] != EMPTY:
                                continue
                            if ((start >= 2 and values[start - 2] == color)
                                    or (end + 1 < len(values) and values[end + 1] == color)):
                                continue
                            window = values[start:end]
                            if any(value not in (EMPTY, color) for value in window):
                                continue
                            stones = tuple(cells[i] for i in range(start, end)
                                           if values[i] == color)
                            if len(stones) == 3:
                                indices = [i for i in range(start, end) if values[i] == color]
                                name = ('open_three' if indices[-1] - indices[0] == 2
                                        else 'broken_three')
                                units[name].add(stones)
                            elif len(stones) == 2:
                                units['two_stone'].add(stones)
                    if not fours:
                        continue
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
                                name = 'open_four' if openings == 2 else 'closed_four'
                                report[name] += 1
                                four_units[name].add(tuple(cells[start:end]))
                        if end - start == 5:
                            exact_fives.add(tuple(cells[start:end]))
                        elif end - start >= 6:
                            overlines.add(tuple(cells[start:end]))
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
                                four_units['broken_four'].add(tuple(cells[j] for j in range(left + 1, right) if j != i))
        check()
        # The established tactical detector resolves captures and both-color outcomes.
        # Terminal input has no legal continuations; static geometry remains inspectable.
        wins = (immediate_wins(Position(position.board, color), check)
                if fours and position.outcome == 'ongoing' else ())
        check()
        report.update(geometric_completion=len(completions), verified_win=len(wins),
                      overline_trap=len(traps), geometric_completions=sorted(completions),
                      verified_wins=list(wins), overline_traps=sorted(traps),
                      units={name: sorted(items) for name, items in four_units.items()},
                      exact_fives=sorted(exact_fives), overlines=sorted(overlines))
        reports.append(report)
        potentials.append({**{name: len(units[name]) for name in POTENTIAL_FEATURES},
                           'units': {name: sorted(units[name]) for name in POTENTIAL_FEATURES}})
    result = {'black': reports[0], 'white': reports[1]}
    if potential:
        result['potential'] = {'black': potentials[0], 'white': potentials[1]}
    return result
