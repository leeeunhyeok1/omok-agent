# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #4.
"""Validate recorded games by applying moves without calling players."""
from math import isclose, isfinite
import json
from pathlib import Path
from typing import Any

from offline.runner import FORMAT, captured_cells, rules_winner, state
from omok.simulator import Position

# Issue #6 validation additions are AI-written by OpenAI Codex.

def _require(condition: bool) -> None:
    if not condition:
        raise ValueError('Malformed or inconsistent game trace.')


def _milliseconds(value: Any) -> float:
    _require(type(value) in (int, float) and isfinite(value) and value >= 0)
    return float(value)


def replay(trace: dict[str, Any]) -> Position:
    """Reject incomplete, malformed, or rules/accounting-inconsistent records."""
    try:
        return _replay(trace)
    except (KeyError, TypeError, IndexError, OverflowError, AttributeError, ValueError) as error:
        raise ValueError(f'Malformed, truncated, or inconsistent game trace: {error}') from error


def load_trace(path: Path) -> dict[str, Any]:
    """Read strict JSON, rejecting duplicate keys and nonfinite extensions."""
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate key in game trace: {key}')
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ValueError(f'Nonfinite value in game trace: {value}')

    def finite_float(value: str) -> float:
        number = float(value)
        if not isfinite(number):
            invalid_constant(value)
        return number

    data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=object_pairs,
                      parse_constant=invalid_constant, parse_float=finite_float)
    _require(isinstance(data, dict))
    return data


def _replay(trace: dict[str, Any]) -> Position:
    _require(isinstance(trace, dict))
    _require(trace['format'] in ('omok-game-v1', FORMAT) and isinstance(trace['config'], dict))
    json.dumps(trace, allow_nan=False)
    versioned_events = trace['format'] == FORMAT
    _require(isinstance(trace['players'], list) and len(trace['players']) == 2)
    for color, player in enumerate(trace['players']):
        _require(type(player['color']) is int and player['color'] == color
                 and isinstance(player['identifier'], str) and bool(player['identifier']))
        if versioned_events:
            source = player['source']
            _require(isinstance(source['module'], str) and bool(source['module'])
                     and isinstance(source['qualname'], str) and bool(source['qualname']))
            digest = source['sha256']
            _require(digest is None or (isinstance(digest, str) and len(digest) == 64
                                       and all(c in '0123456789abcdef' for c in digest)))
    events = trace['events'] if versioned_events else []
    _require(isinstance(events, list))
    event_index = 0
    initial = trace['initial']
    position = Position(initial['board'], initial['side_to_move'])
    _require(state(position) == initial)
    _require(type(trace['move_cap']) is int and trace['move_cap'] >= 0)
    _require(isinstance(trace['budgets_ms'], list) and len(trace['budgets_ms']) == 2
             and isinstance(trace['remaining_ms'], list) and len(trace['remaining_ms']) == 2)
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
        _coordinate(entry['move'])
        transition = position.play(entry['move'])
        _require(_captures(entry['captured']) == _captures(captured_cells(transition)))
        position = transition.position
        if versioned_events:
            returned, applied = events[event_index:event_index + 2]
            _returned(returned, color, elapsed, remaining[color])
            _require(returned['move'] == entry['move'])
            _require(_captures(applied['captured']) == _captures(entry['captured']))
            _require(_same(applied, {'type': 'applied', **entry,
                                    'captured': applied['captured'], 'state': state(position)}))
            event_index += 2
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
        _require(failure['violations'] == [v for v in
                 ('exception', 'mutation', 'timeout', 'invalid_move') if v in failure['violations']]
                 and ('invalid_move' not in failure['violations'] or failure['violations'] == ['invalid_move']))
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
        if versioned_events:
            if failure['called']:
                returned = events[event_index]
                _returned(returned, color, elapsed, remaining[color])
                _require(returned['returned'] == failure['returned'])
                if failure['violations'] == ['invalid_move'] and returned['move'] is not None:
                    try:
                        position.play(returned['move'])
                    except ValueError:
                        pass
                    else:
                        _require(False)
                event_index += 1
            _require(_same(events[event_index], {'type': 'failure', **failure,
                                                'remaining_ms': remaining[color]}))
            event_index += 1
    else:
        raise ValueError('Unknown game status in trace.')
    _require(event_index == len(events))
    for actual, expected_clock in zip(trace['remaining_ms'], remaining):
        _compare_clock(actual, expected_clock)
    return position


def _coordinate(move: Any) -> None:
    _require(isinstance(move, list) and len(move) == 2 and all(type(n) is int for n in move))


def _captures(captures: Any) -> set[tuple[int, int, int]]:
    _require(isinstance(captures, list))
    result = set()
    for captured in captures:
        _coordinate(captured['cell'])
        _require(type(captured['prior_value']) is int)
        result.add((*captured['cell'], captured['prior_value']))
    _require(len(result) == len(captures))
    return result


def _same(actual: Any, expected: Any) -> bool:
    """Compare JSON values, keeping booleans distinct from numeric values."""
    if isinstance(expected, dict):
        return (isinstance(actual, dict) and actual.keys() == expected.keys()
                and all(_same(actual[key], value) for key, value in expected.items()))
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(_same(a, b) for a, b in zip(actual, expected)))
    if type(expected) is float:
        return type(actual) in (int, float) and actual == expected
    return type(actual) is type(expected) and actual == expected


def _returned(event: Any, color: int, elapsed: float, remaining: float | None) -> None:
    _require(event['type'] == 'returned' and type(event['color']) is int
             and event['color'] == color and isinstance(event['returned'], str))
    if event['move'] is not None:
        _coordinate(event['move'])
    _require(_milliseconds(event['elapsed_ms']) == elapsed)
    _compare_clock(event['remaining_ms'], remaining)


def _compare_clock(actual: Any, expected: float | None) -> None:
    if expected is None:
        _require(actual is None)
    else:
        _require(isclose(_milliseconds(actual), expected, rel_tol=1e-12, abs_tol=1e-9))
