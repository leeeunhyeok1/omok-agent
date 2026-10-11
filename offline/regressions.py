# AI-written by OpenAI Codex, for issue #44.
"""Budgeted independent tactical analysis and additive checked regressions."""
from copy import deepcopy
import json
from math import isfinite
from pathlib import Path
from time import monotonic
from typing import Any

from offline.experiments import save_new_json
from offline.inspection import inspect_loss, verify_fixture
from offline.registry import digest
from offline.runner import state
from omok.simulator import Position
from verification.reference import ReferencePosition


class AnalysisExhausted(Exception):
    pass


def analyze_tactic(record: dict[str, Any], *, kind: str, max_transitions: int,
                  max_seconds: float) -> dict[str, Any]:
    """Exhaustive one-ply wins or two-ply immediate defenses, using only the oracle.

    An immediate defense prevents any strict opponent win on their next turn.
    This is a bounded tactical assertion, never a strategic optimum claim.
    """
    if kind not in ('immediate-win', 'immediate-defense'):
        raise ValueError('Only immediate wins and immediate defenses can be confirmed.')
    if (type(max_transitions) is not int or not 1 <= max_transitions <= 131000
            or type(max_seconds) not in (int, float) or not isfinite(max_seconds)
            or not 0 < max_seconds <= 3600):
        raise ValueError('Declare a separate positive bounded analysis budget.')
    initial = record['position']
    position = Position(initial['board'], initial['side_to_move'])
    if state(position) != initial or position.side_to_move != record['color'] or position.outcome != 'ongoing':
        raise ValueError('Analyze a consistent live pre-turn position.')
    oracle = ReferencePosition(position.board, position.side_to_move)
    start, transitions = monotonic(), 0
    mover_win = 'black_win' if record['color'] == 0 else 'white_win'
    opponent_win = 'white_win' if record['color'] == 0 else 'black_win'

    def legal(p: ReferencePosition):
        return ((r, c) for r in range(19) for c in range(19) if p.board[r][c] == -1)

    def play(p: ReferencePosition, move):
        nonlocal transitions
        if transitions >= max_transitions or monotonic() - start >= max_seconds:
            raise AnalysisExhausted
        transitions += 1
        return p.play(move).position

    allowed = []
    status, applicable = 'checked', True
    try:
        if kind == 'immediate-defense':
            attacker = ReferencePosition(position.board, 1 - position.side_to_move)
            applicable = any(play(attacker, move).outcome == opponent_win for move in legal(attacker))
        if applicable:
            for move in legal(oracle):
                child = play(oracle, move)
                if kind == 'immediate-win':
                    accepted = child.outcome == mover_win
                else:
                    accepted = child.outcome in (mover_win, 'draw') or (child.outcome == 'ongoing'
                        and not any(play(child, reply).outcome == opponent_win for reply in legal(child)))
                if accepted:
                    allowed.append(list(move))
        if monotonic() - start >= max_seconds:
            raise AnalysisExhausted
    except AnalysisExhausted:
        status = 'unknown'
    complete = status == 'checked'
    return {'format': 'omok-tactical-analysis-v1', 'kind': kind, 'status': status,
        'position_identity': digest(initial), 'record_identity': digest(record),
        'analysis': 'exhaustive independent reference transitions; one ply wins / two ply defenses',
        'applicable': applicable if complete else None,
        'allowed_moves': allowed if complete else None,
        'confirmed_failure': bool(complete and applicable and allowed and record['chosen_move'] is not None
                                  and record['chosen_move'] not in allowed and record['execution'] is None),
        'budget': {'max_transitions': max_transitions, 'max_seconds': max_seconds,
                   'used_transitions': transitions, 'wall_seconds': monotonic() - start},
        'strategic_best_move': None}


def verify_regression(fixture: dict[str, Any]) -> None:
    if fixture.get('format') == 'omok-checked-rule-fixture-v1':
        verify_fixture(fixture)
        return
    if fixture['format'] != 'omok-checked-tactical-fixture-v1':
        raise ValueError('Unsupported regression format.')
    trace = fixture['source']['trace']
    source = inspect_loss(trace, color=fixture['source']['color'], plies=[fixture['source']['ply']])['positions'][0]
    if fixture['record'] != source or fixture['source']['trace_identity'] != digest(trace):
        raise ValueError('Regression source differs from replayed evidence.')
    analysis = fixture['analysis']
    checked = analyze_tactic(source, kind=analysis['kind'],
        max_transitions=analysis['budget']['max_transitions'], max_seconds=analysis['budget']['max_seconds'])
    fields = ('format', 'kind', 'status', 'position_identity', 'record_identity', 'analysis',
              'applicable', 'allowed_moves', 'confirmed_failure', 'strategic_best_move')
    if (not checked['confirmed_failure'] or any(analysis[k] != checked[k] for k in fields)
            or analysis['budget']['used_transitions'] != checked['budget']['used_transitions']
            or fixture['expected'] != {'allowed_moves': checked['allowed_moves'], 'kind': checked['kind']}):
        raise ValueError('Regression is not a confirmed tactical failure with a fixed checked move set.')


def export_regression(output: Path, trace: dict[str, Any], *, ply: int, color: int,
                      analysis: dict[str, Any]) -> Path:
    record = inspect_loss(trace, color=color, plies=[ply])['positions'][0]
    fixture = {'format': 'omok-checked-tactical-fixture-v1', 'record': record,
        'analysis': deepcopy(analysis), 'expected': {'kind': analysis['kind'], 'allowed_moves': analysis['allowed_moves']},
        'source': {'trace': trace, 'trace_identity': digest(trace), 'ply': ply, 'color': color,
                   'attribution': 'AI-written OpenAI Codex; saved player/source provenance in original trace'}}
    return append_fixture(output, fixture)


def append_fixture(output: Path, fixture: dict[str, Any]) -> Path:
    """Never replace a fixture, including one whose expectations disagree."""
    verify_regression(fixture)
    key = ({'position': fixture['record']['position'], 'kind': fixture['expected']['kind']}
           if fixture['format'] == 'omok-checked-tactical-fixture-v1'
           else {'position': fixture['position'], 'move': fixture['move'], 'kind': fixture['assertion']})
    output.mkdir(parents=True, exist_ok=True)
    path = output / (digest(key) + '.json')
    try:
        save_new_json(path, fixture)
    except FileExistsError:
        existing = json.loads(path.read_text(encoding='utf-8'))
        verify_regression(existing)
        if existing['expected'] != fixture['expected']:
            raise ValueError('Existing regression expectations cannot be changed.')
    return path
