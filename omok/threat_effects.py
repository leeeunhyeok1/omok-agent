# AI-written by OpenAI Codex, for issue #20.
"""After-board capture effects and bounded-horizon multiplicity evidence."""
from collections.abc import Callable
from typing import Any

from omok.captures import capture_features
from omok.lines import LINE_FEATURES, POTENTIAL_FEATURES, line_features
from omok.search import SearchCancelled
from omok.simulator import Position
from omok.tactics import TacticalPolicy

EFFECT_FEATURES = ('capture_break_four', 'capture_break_potential',
                   'capture_create_four', 'capture_create_potential', 'capture_remove_blocker', 'capture_expose_five')
MULTIPLICITY_FEATURES = ('geometric_multiple', 'verified_multiple',
                         'offensive_opportunity', 'defensive_urgency')
COLORS = ('black', 'white')


def _units(lines: dict[str, Any], color: str, *, potential: bool = False) -> set[tuple]:
    source = lines['potential'][color] if potential else lines[color]
    return {tuple(unit) for units in source['units'].values() for unit in units}


def _summary(lines: dict[str, Any], color: str) -> dict[str, Any]:
    return {**{name: lines[color][name] for name in LINE_FEATURES},
            **{name: lines['potential'][color][name] for name in POTENTIAL_FEATURES},
            'exact_fives': lines[color]['exact_fives'], 'overlines': lines[color]['overlines'],
            'geometric_endpoints': lines[color]['geometric_completions'],
            'verified_endpoints': lines[color]['verified_wins']}


def capture_effects(position: Position, check: Callable[[], None], *,
                    inspection: bool = False) -> dict[str, Any]:
    before = line_features(position, check, potential=True)
    captures = capture_features(position, check, inspection=True)
    result: dict[str, Any] = {}
    for color, name in enumerate(COLORS):
        enemy = COLORS[1 - color]
        counts = dict.fromkeys(EFFECT_FEATURES, 0)
        records = []
        check()
        own = Position(position.board, color)
        for capture in captures[name]['moves']:
            check()
            child = own.play(capture['move']).position
            check()  # Includes cancellation after captures; the parent is immutable.
            after = line_features(child, check, potential=True)
            # Inspection/scoring distinguishes removal from the placement's effect.
            # This is geometric counterfactual evidence, never a legal move outcome.
            blocked_board = [list(row) for row in child.board]
            for row, col in capture['cells']:
                blocked_board[row][col] = 1 - color
            check()
            blocked = line_features(Position(blocked_board, child.side_to_move), check, potential=True)
            opened = {family: sorted(_units(after, name, potential=potential)
                                     - _units(blocked, name, potential=potential))
                      for family, potential in (('fours', False), ('potential', True))}
            changes: dict[str, Any] = {}
            for target in COLORS:
                changes[target] = {}
                for family, potential in (('fours', False), ('potential', True)):
                    old, new = _units(before, target, potential=potential), _units(after, target, potential=potential)
                    changes[target][family] = {'removed': sorted(old - new), 'created': sorted(new - old)}
            # Beneficial effects only count ongoing/mover-win captures. Outcome risk
            # is separately represented; draws cannot masquerade as attack wins.
            favorable = capture['classification'] in ('continuation', 'win')
            counts['capture_break_four'] += int(favorable and bool(changes[enemy]['fours']['removed']))
            counts['capture_break_potential'] += int(favorable and bool(changes[enemy]['potential']['removed']))
            counts['capture_create_four'] += int(favorable and bool(changes[name]['fours']['created']))
            counts['capture_create_potential'] += int(favorable and bool(changes[name]['potential']['created']))
            counts['capture_remove_blocker'] += int(favorable and any(opened.values()))
            counts['capture_expose_five'] += int(bool(set(after[enemy]['exact_fives']) - set(before[enemy]['exact_fives'])))
            if inspection:
                records.append({'move': capture['move'], 'removed': capture['cells'],
                                'classification': capture['classification'], 'outcome': child.outcome,
                                'before': {c: _summary(before, c) for c in COLORS},
                                'after': {c: _summary(after, c) for c in COLORS},
                                'changed_units': changes, 'capture_opened_units': opened})
        result[name] = {**counts, 'moves': records}
    check()
    return result


def multiplicity_features(position: Position, lines: dict[str, Any],
                          check: Callable[[], None], *, inspection: bool = False) -> dict[str, Any]:
    reports = {}
    for color, name in enumerate(COLORS):
        check()
        geometric = lines[name]['geometric_completions']
        verified = lines[name]['verified_wins']
        record: dict[str, Any] = {
            'geometric_multiple': int(len(geometric) >= 2),
            'verified_multiple': int(len(verified) >= 2),
            'offensive_opportunity': len(verified) if position.side_to_move == color else 0,
            'defensive_urgency': len(verified) if position.side_to_move != color else 0,
            'geometric_endpoints': geometric, 'verified_endpoints': verified,
            'independence': 'unknown' if len(verified) >= 2 else 'not_applicable',
            'defenses_complete': False, 'shared_defenders': [], 'shared_capture_defenders': [],
            'evidence_scope': 'all legal defender moves against immediate strict wins; not a solved game',
        }
        if inspection and len(verified) >= 2 and position.outcome == 'ongoing':
            check()
            defender = Position(position.board, 1 - color)
            evidence = TacticalPolicy().analyze(defender, check)
            if evidence.cancellation is not None:
                raise SearchCancelled(evidence.cancellation)
            check()
            record['defenses_complete'] = evidence.threats_complete and evidence.defenses_complete
            record['shared_defenders'] = list(evidence.defenses)
            for move in evidence.defenses:
                check()
                if defender.play(move).captured:
                    record['shared_capture_defenders'].append(move)
            if record['defenses_complete']:
                record['independence'] = 'refuted' if evidence.defenses else 'verified'
        reports[name] = record
    check()
    return reports
