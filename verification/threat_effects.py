# AI-written by OpenAI Codex, for issue #20.
"""Independent endpoint/defender labels, capture effects and family cost samples."""
import argparse
from dataclasses import replace
import json
from statistics import median
from time import perf_counter

from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
from omok.simulator import Position, SIZE
from verification.captures import suite, verify
from verification.reference import ReferencePosition


def reference_wins(position: ReferencePosition, color: int) -> list[tuple[int, int]]:
    """Independent five-window filter followed by the reference rules, not tactics."""
    if position.outcome != 'ongoing':
        return []
    candidates = set()
    board = position.board
    for r in range(SIZE):
        for c in range(SIZE):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                end = r + 4 * dr, c + 4 * dc
                if not (0 <= end[0] < SIZE and 0 <= end[1] < SIZE):
                    continue
                cells = [(r + n * dr, c + n * dc) for n in range(5)]
                values = [board[x][y] for x, y in cells]
                if values.count(color) == 4 and values.count(-1) == 1:
                    candidates.add(cells[values.index(-1)])
    own = ReferencePosition(board, color)
    target = 'black_win' if color == 0 else 'white_win'
    return sorted(move for move in candidates if own.play(move).position.outcome == target)


def reference_defenses(position: Position, attacker: int) -> list[tuple[int, int]]:
    defender = ReferencePosition(position.board, 1 - attacker)
    safe = []
    win = 'white_win' if attacker == 0 else 'black_win'
    for r in range(SIZE):
        for c in range(SIZE):
            if defender.board[r][c] != -1:
                continue
            child = defender.play((r, c)).position
            if child.outcome in (win, 'draw') or (child.outcome == 'ongoing'
                                                  and not reference_wins(child, attacker)):
                safe.append((r, c))
    return safe


def games() -> dict:
    """Small deterministic ablations; capped development evidence, not win rates."""
    from offline.runner import run_game
    from offline.replay import replay
    from omok.player import IterativePlayer
    config = EvaluationConfig.load('configs/effects-v1.json')
    records = []
    for label, cfg in (('enabled', config), ('no_effects', replace(config, effects_enabled=False)),
                       ('no_multiplicity', replace(config, multiplicity_enabled=False)),
                       ('both_disabled', replace(config, effects_enabled=False, multiplicity_enabled=False))):
        for color in (0, 1):
            board = suite()['single'].board
            if color:
                board = tuple(tuple(1 - cell if cell != -1 else -1 for cell in row) for row in board)
            agent = IterativePlayer(color, max_depth=2, evaluation_config=cfg)
            opponent = IterativePlayer(1 - color, max_depth=2, evaluation_config=EvaluationConfig())
            players = [agent, opponent] if color == 0 else [opponent, agent]
            trace = run_game(*players, initial=Position(board, color), move_cap=8,
                             budgets_ms=(60000, 60000), diagnostics=lambda p: p.diagnostics() if isinstance(p, IterativePlayer) else None,
                             config={'ablation': label, 'agent_color': color, 'evaluator_id': cfg.identity,
                                     'opponent': 'retained phase2 material', 'max_depth': 2,
                                     'fixture': 'single capture, color swapped with agent',
                                     'clock_policy': 'unchanged', 'ordinary_candidates': 'unchanged'})
            assert trace['failure'] is None
            replay(trace)
            records.append(trace)
    return {'interpretation': 'Eight capped deterministic development traces; no strength promotion or official win rate.',
            'traces': records}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--games', action='store_true', help='Run bounded two-color ablations instead of the oracle suite')
    parser.add_argument('--repetitions', type=int, default=5)
    args = parser.parse_args()
    if args.games:
        print(json.dumps(games(), indent=2, sort_keys=True))
        return
    if args.repetitions < 1:
        parser.error('repetitions must be positive')
    config = EvaluationConfig.load('configs/effects-v1.json')
    evaluator = ConfiguredEvaluator(config)
    positions = suite()
    board = [list(row) for row in positions['capture_defense'].board]
    board[8][7] = -1
    positions['control'] = Position(board, 0)
    board = [list(row) for row in positions['capture_defense'].board]
    board[7][6] = board[6][5] = 1
    positions['intersecting'] = Position(board, 0)
    reports = {}
    checked = 0
    for name, position in positions.items():
        inspection = evaluator.inspect(position)
        checked += verify(position, inspection)
        for color, label in enumerate(('black', 'white')):
            assert inspection['multiplicity'][label]['verified_endpoints'] == reference_wins(
                ReferencePosition(position.board, color), color)
            for effect in inspection['effects'][label]['moves']:
                oracle = ReferencePosition(position.board, color).play(effect['move'])
                assert effect['removed'] == [cell.cell for cell in oracle.captured]
                assert effect['outcome'] == oracle.position.outcome
                for target, target_label in enumerate(('black', 'white')):
                    assert effect['after'][target_label]['verified_endpoints'] == reference_wins(oracle.position, target)
                assert all(oracle.position.board[r][c] == -1 for r, c in effect['removed'])
        if name in ('capture_defense', 'control', 'intersecting'):
            expected = reference_defenses(position, 1)
            assert inspection['multiplicity']['white']['shared_defenders'] == expected
            assert inspection['multiplicity']['white']['independence'] == ('refuted' if expected else 'verified')
        timings = {}
        for label, cfg in (
                ('enabled', config), ('no_effects', replace(config, effects_enabled=False)),
                ('no_multiplicity', replace(config, multiplicity_enabled=False)),
                ('both_disabled', replace(config, effects_enabled=False, multiplicity_enabled=False)),
                ('phase2', EvaluationConfig())):
            callback = ConfiguredEvaluator(cfg)
            samples = []
            value = 0
            for _ in range(args.repetitions):
                start = perf_counter()
                value = callback(position)
                samples.append((perf_counter() - start) * 1000)
            timings[label] = {'median_ms': median(samples), 'max_ms': max(samples), 'value': value}
        reports[name] = {'inspection': inspection, 'timings': timings}
    print(json.dumps({'configuration': json.loads(config.canonical_json()),
                      'oracle_legal_transitions': checked, 'repetitions': args.repetitions,
                      'interpretation': 'Provisional static model; independence is immediate-reply evidence only.',
                      'positions': reports}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
