# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
"""Trusted, post-return timed games. Hard call termination is deferred."""
from collections.abc import Callable
from math import floor, isfinite
from time import monotonic
from typing import Any

from omok.player import DevelopmentPlayer
from omok.simulator import Position, Transition

FORMAT = 'omok-game-v1'


def state(position: Position) -> dict[str, Any]:
    return {'board': [list(row) for row in position.board],
            'side_to_move': position.side_to_move,
            'outcome': position.outcome, 'reason': position.reason}


def captured_cells(transition: Transition) -> list[dict[str, Any]]:
    return [{'cell': list(c.cell), 'prior_value': c.prior_value} for c in transition.captured]


def rules_winner(position: Position) -> int | None:
    return 0 if position.outcome == 'black_win' else 1 if position.outcome == 'white_win' else None


def unchanged(snapshot: list[list[int]], position: Position) -> bool:
    return (type(snapshot) is list and len(snapshot) == 19
            and all(type(row) is list and len(row) == 19
                    and all(type(cell) is int for cell in row) for row in snapshot)
            and snapshot == [list(row) for row in position.board])


def run_game(black: DevelopmentPlayer, white: DevelopmentPlayer, *,
             initial: Position | None = None,
             budgets_ms: tuple[float | None, float | None] = (60000, 60000),
             move_cap: int = 1000, clock: Callable[[], float] = monotonic,
             config: dict[str, Any] | None = None) -> dict[str, Any]:
    if black is white or (black.color, white.color) != (0, 1):
        raise ValueError('Independent players must be assigned black=0 and white=1.')
    if type(move_cap) is not int or move_cap < 0:
        raise ValueError('Move cap must be a nonnegative integer.')
    if len(budgets_ms) != 2 or any(b is not None and
            (isinstance(b, bool) or not isfinite(b) or b < 0) for b in budgets_ms):
        raise ValueError('Budgets must be finite nonnegative milliseconds or None.')
    position = Position.empty() if initial is None else initial
    players = (black, white)
    remaining = list(budgets_ms)
    trace: dict[str, Any] = {
        'format': FORMAT, 'initial': state(position),
        'players': [{'color': p.color, 'identifier': type(p).__name__} for p in players],
        'budgets_ms': list(budgets_ms), 'move_cap': move_cap, 'config': config or {},
        'moves': [], 'failure': None,
    }
    status = 'completed'
    reason: str | None = position.reason
    while position.outcome == 'ongoing':
        if len(trace['moves']) >= move_cap:
            status, reason = 'capped', 'move_cap'
            break
        color = position.side_to_move
        budget = remaining[color]
        if budget is not None and budget <= 0:
            status, reason = 'failed', 'timeout'
            trace['failure'] = {'color': color, 'player': trace['players'][color]['identifier'],
                                'reason': reason, 'violations': [reason], 'called': False,
                                'elapsed_ms': 0, 'returned': None, 'exception': None}
            break
        snapshot = [list(row) for row in position.board]
        returned: Any = None
        exception = None
        start = clock()
        try:
            returned = players[color].take_turn(snapshot, -1 if budget is None else floor(budget))
        except Exception as error:
            exception = {'type': type(error).__name__, 'message': str(error)}
        elapsed = (clock() - start) * 1000
        if not isfinite(elapsed) or elapsed < 0:
            raise ValueError('Clock must be finite and monotonic.')
        if budget is not None:
            remaining[color] = max(0.0, budget - elapsed)
        violations = []
        if exception is not None:
            violations.append('exception')
        if not unchanged(snapshot, position):
            violations.append('mutation')
        if budget is not None and elapsed > budget:
            violations.append('timeout')
        transition = None
        if not violations:
            try:
                transition = position.play(returned)
            except ValueError:
                violations.append('invalid_move')
        if violations:
            status, reason = 'failed', violations[0]
            trace['failure'] = {'color': color, 'player': trace['players'][color]['identifier'],
                                'reason': reason, 'violations': violations, 'called': True,
                                'elapsed_ms': elapsed, 'returned': repr(returned),
                                'exception': exception}
            break
        assert transition is not None
        position = transition.position
        trace['moves'].append({'color': color, 'move': list(transition.move),
                               'captured': captured_cells(transition),
                               'elapsed_ms': elapsed, 'remaining_ms': remaining[color]})
        reason = position.reason
    trace.update(status=status, reason=reason, final=state(position),
                 remaining_ms=remaining,
                 winner=rules_winner(position))
    return trace
