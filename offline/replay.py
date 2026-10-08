# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
"""Validate recorded games by applying moves without calling players."""
from math import isclose, isfinite
from typing import Any

from offline.runner import FORMAT, captured_cells, rules_winner, state
from omok.simulator import Position


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError('Malformed or inconsistent omok-game-v1 trace.')


def _milliseconds(value: Any) -> float:
    _require(type(value) in (int, float) and isfinite(value) and value >= 0)
    return float(value)


def replay(trace: dict[str, Any]) -> Position:
    """Reject incomplete, malformed, or rules/accounting-inconsistent records."""
    try:
        return _replay(trace)
    except (KeyError, TypeError, IndexError, OverflowError) as error:
        raise ValueError('Malformed or truncated omok-game-v1 trace.') from error


def _replay(trace: dict[str, Any]) -> Position:
    _require(trace['format'] == FORMAT and isinstance(trace['config'], dict))
    _require(len(trace['players']) == 2)
    for color, player in enumerate(trace['players']):
        _require(type(player['color']) is int and player['color'] == color
                 and isinstance(player['identifier'], str) and bool(player['identifier']))
    initial = trace['initial']
    position = Position(initial['board'], initial['side_to_move'])
    _require(state(position) == initial)
    _require(type(trace['move_cap']) is int and trace['move_cap'] >= 0)
    _require(len(trace['budgets_ms']) == 2 and len(trace['remaining_ms']) == 2)
    remaining = [None if b is None else _milliseconds(b) for b in trace['budgets_ms']]
    _require(isinstance(trace['moves'], list) and len(trace['moves']) <= trace['move_cap'])
    for entry in trace['moves']:
        color = position.side_to_move
        _require(type(entry['color']) is int and entry['color'] == color)
        elapsed = _milliseconds(entry['elapsed_ms'])
        budget = remaining[color]
        if budget is not None:
            _require(budget > 0 and elapsed <= budget)
            remaining[color] = max(0.0, budget - elapsed)
        _compare_clock(entry['remaining_ms'], remaining[color])
        transition = position.play(entry['move'])
        _require(isinstance(entry['captured'], list))
        for captured in entry['captured']:
            _require(type(captured['prior_value']) is int
                     and isinstance(captured['cell'], list) and len(captured['cell']) == 2
                     and all(type(n) is int for n in captured['cell']))
        _require(entry['captured'] == captured_cells(transition))
        position = transition.position
    final = trace['final']
    # Validate types before comparison: bool equality must not conceal corruption.
    validated_final = Position(final['board'], final['side_to_move'])
    _require(state(validated_final) == final and state(position) == final)
    _require((trace['winner'] is None or type(trace['winner']) is int)
             and trace['winner'] == rules_winner(position))
    status, reason, failure = trace['status'], trace['reason'], trace['failure']
    if status == 'completed':
        _require(position.outcome != 'ongoing' and reason == position.reason and failure is None)
    elif status == 'capped':
        _require(position.outcome == 'ongoing' and reason == 'move_cap' and failure is None
                 and len(trace['moves']) == trace['move_cap'])
    elif status == 'failed':
        _require(position.outcome == 'ongoing' and len(trace['moves']) < trace['move_cap'])
        color = position.side_to_move
        _require(type(failure['color']) is int and failure['color'] == color
                 and failure['player'] == trace['players'][color]['identifier'])
        _require(isinstance(failure['violations'], list) and bool(failure['violations'])
                 and all(v in ('exception', 'invalid_move', 'mutation', 'timeout')
                         for v in failure['violations'])
                 and reason == failure['reason'] == failure['violations'][0])
        elapsed = _milliseconds(failure['elapsed_ms'])
        budget = remaining[color]
        _require(type(failure['called']) is bool)
        if not failure['called']:
            _require(budget == 0 and elapsed == 0 and failure['violations'] == ['timeout']
                     and failure['returned'] is None and failure['exception'] is None)
        else:
            _require(budget is None or budget > 0)
            _require(isinstance(failure['returned'], str))
            if 'exception' in failure['violations']:
                _require(isinstance(failure['exception']['type'], str)
                         and isinstance(failure['exception']['message'], str))
            else:
                _require(failure['exception'] is None)
            _require(('timeout' in failure['violations']) == (budget is not None and elapsed > budget))
            if budget is not None:
                remaining[color] = max(0.0, budget - elapsed)
    else:
        raise ValueError('Unknown game status.')
    for actual, expected_clock in zip(trace['remaining_ms'], remaining):
        _compare_clock(actual, expected_clock)
    return position


def _compare_clock(actual: Any, expected: float | None) -> None:
    if expected is None:
        _require(actual is None)
    else:
        _require(isclose(_milliseconds(actual), expected, rel_tol=1e-12, abs_tol=1e-9))
