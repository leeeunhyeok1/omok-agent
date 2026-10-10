# AI-written by OpenAI Codex, for issue #31.
"""Bounded, agent-free loss inspection and independently checked rule fixtures."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from offline.replay import load_trace, replay
from offline.runner import state
from omok.simulator import Position


def inspect_loss(trace: dict[str, Any], *, color: int | None = None,
                 plies: list[int] | None = None, max_positions: int = 8,
                 history_limit: int = 12) -> dict[str, Any]:
    """Select preceding turns; tags suggest investigation, never a best move."""
    final = replay(trace)
    if type(max_positions) is not int or not 1 <= max_positions <= 100:
        raise ValueError('Position limit must be 1..100.')
    if type(history_limit) is not int or not 0 <= history_limit <= 1000:
        raise ValueError('History limit must be 0..1000.')
    failure = trace['failure']
    execution_status = trace['status']
    if trace['reason'] == 'cleanup_error':
        failure = trace['prior_result']['failure']
        execution_status = trace['prior_result']['status']
    if color is None:
        color = failure['color'] if failure else (1 - trace['winner'] if trace['winner'] is not None else None)
    if color is not None and (type(color) is not int or color not in (0, 1)):
        raise ValueError('Color must be black=0 or white=1.')
    count = len(trace['moves'])
    available = [i for i, move in enumerate(trace['moves']) if move['color'] == color]
    if (color is not None and failure and failure['color'] == color
            and execution_status in ('failed', 'capped')):
        available.append(count)
    selected = available[-max_positions:] if plies is None else plies
    if (len(selected) > max_positions or len(set(selected)) != len(selected)
            or any(type(i) is not int or i not in available for i in selected)):
        raise ValueError('Select distinct recorded turns of the inspected color within the limit.')
    position = Position(trace['initial']['board'], trace['initial']['side_to_move'])
    clocks = list(trace['budgets_ms'])
    returned = [event for event in trace.get('events', []) if event['type'] == 'returned']
    records = []
    for ply in range(count + 1):
        if ply in selected:
            assert color is not None
            entry = trace['moves'][ply] if ply < count else None
            event = returned[ply] if ply < len(returned) else {}
            tags = []
            if entry and entry['captured']:
                tags.append('exact-five interaction' if trace['winner'] != color else 'pair vulnerability')
            if not entry and failure:
                tags.append('time management' if failure['reason'] == 'timeout' else 'execution failure')
            if not tags:
                tags.append('unclassified loss')
            records.append({'ply': ply, 'color': color, 'position': state(position),
                'player': trace['players'][color], 'opponent': trace['players'][1 - color],
                'configuration': trace['config'], 'clocks_before_ms': clocks[:],
                'chosen_move': entry['move'] if entry else event.get('move'),
                'turn_evidence': event, 'execution': failure if not entry else None,
                'preceding_moves': trace['moves'][max(0, ply - history_limit):ply],
                'history_start_ply': max(0, ply - history_limit),
                'tags': [{'category': tag, 'status': 'hypothesis'} for tag in tags]})
        if ply < count:
            entry = trace['moves'][ply]
            position = position.play(entry['move']).position
            clocks[entry['color']] = entry['remaining_ms']
    encoded = json.dumps(trace, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return deepcopy({'format': 'omok-loss-inspection-v1', 'trace_sha256': sha256(encoded.encode()).hexdigest(),
        'trace_format': trace['format'], 'board_outcome': final.outcome,
        'execution_status': trace['status'], 'execution_reason': trace['reason'],
        'color': color, 'positions': records, 'selection': {'available': len(available),
        'exported': len(records), 'max_positions': max_positions, 'history_limit': history_limit},
        'alternative_analysis': None})


def checked_fixture(trace: dict[str, Any], *, ply: int, color: int,
                    expected_outcome: str, expected_reason: str | None) -> dict[str, Any]:
    """Confirm one recorded move's rule result with the independent oracle.

    This asserts the observed result of a specific move, never optimality.
    Execution-only failures cannot become board-rule assertions.
    """
    record = inspect_loss(trace, color=color, plies=[ply])['positions'][0]
    move = record['chosen_move']
    if record['execution'] is not None or move is None:
        raise ValueError('Execution failure has no checked board-move expectation.')
    fixture = {'format': 'omok-checked-rule-fixture-v1', 'position': record['position'],
        'move': move, 'expected': {'outcome': expected_outcome, 'reason': expected_reason},
        'assertion': 'recorded-move-rule-result', 'source': record}
    verify_fixture(fixture)
    return fixture


def verify_fixture(fixture: dict[str, Any]) -> None:
    from verification.reference import ReferencePosition
    if (fixture['format'] != 'omok-checked-rule-fixture-v1'
            or fixture['assertion'] != 'recorded-move-rule-result'):
        raise ValueError('Unsupported tactical fixture assertion.')
    initial = fixture['position']
    position = Position(initial['board'], initial['side_to_move'])
    if state(position) != initial:
        raise ValueError('Inconsistent tactical fixture position.')
    child = position.play(fixture['move']).position
    oracle = ReferencePosition(position.board, position.side_to_move).play(fixture['move']).position
    expected = fixture['expected']
    if ((child.outcome, child.reason) != (expected['outcome'], expected['reason'])
            or (oracle.outcome, oracle.reason, oracle.board) != (child.outcome, child.reason, child.board)):
        raise ValueError('Tactical fixture expectation is not independently confirmed.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--color', type=int, choices=(0, 1))
    parser.add_argument('--ply', type=int, action='append')
    parser.add_argument('--max-positions', type=int, default=8)
    parser.add_argument('--history-limit', type=int, default=12)
    parser.add_argument('--verify-fixture', action='store_true')
    parser.add_argument('--confirm-outcome', choices=('ongoing', 'black_win', 'white_win', 'draw'))
    parser.add_argument('--confirm-reason')
    args = parser.parse_args()
    try:
        trace = load_trace(args.trace)
        if args.verify_fixture:
            verify_fixture(trace)
            result = {'verified': True}
        elif args.confirm_outcome:
            if args.color is None or not args.ply or len(args.ply) != 1:
                raise ValueError('Confirmation requires one --ply and explicit --color.')
            result = checked_fixture(trace, ply=args.ply[0], color=args.color,
                expected_outcome=args.confirm_outcome, expected_reason=args.confirm_reason)
        else:
            result = inspect_loss(trace, color=args.color, plies=args.ply,
                max_positions=args.max_positions, history_limit=args.history_limit)
        encoded = json.dumps(result, indent=2, allow_nan=False) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding='utf-8')
        else:
            print(encoded, end='')
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        parser.exit(2, f'error: {error}\n')


if __name__ == '__main__':
    main()
