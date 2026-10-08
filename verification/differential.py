# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #3.
"""Seeded legal sequences, child isolation checks, and replayable mismatches."""
import argparse
import json
from pathlib import Path
import random
import time
from collections.abc import Sequence
from typing import Any

from omok.simulator import Coordinate, Position, SIZE, EMPTY
from verification.reference import ReferencePosition


def legal_moves(board: Sequence[Sequence[int]]) -> list[Coordinate]:
    return [(r, c) for r in range(SIZE) for c in range(SIZE) if board[r][c] == EMPTY]


def state(position: Position | ReferencePosition) -> tuple[object, ...]:
    return (tuple(tuple(row) for row in position.board), position.side_to_move,
            position.outcome, position.reason)


def choose_move(position: Position, rng: random.Random, biased: bool) -> Coordinate:
    moves = legal_moves(position.board)
    if not biased:
        return rng.choice(moves)
    capture_moves = []
    for r, c in moves:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if not (dr or dc):
                    continue
                end_r, end_c = r + 3 * dr, c + 3 * dc
                if (0 <= end_r < SIZE and 0 <= end_c < SIZE
                        and position.board[r + dr][c + dc] == 1 - position.side_to_move
                        and position.board[r + 2 * dr][c + 2 * dc] == 1 - position.side_to_move
                        and position.board[end_r][end_c] == position.side_to_move):
                    capture_moves.append((r, c))
                    break
            else:
                continue
            break
    if capture_moves:
        return rng.choice(capture_moves)
    # Concentrate fallback play around existing stones to create capture opportunities.
    nearby = [(r, c) for r, c in moves if any(
        0 <= r + dr < SIZE and 0 <= c + dc < SIZE
        and position.board[r + dr][c + dc] != EMPTY
        for dr in (-1, 0, 1) for dc in (-1, 0, 1))]
    return rng.choice(nearby or moves)


def checked_move(position: Position, reference: ReferencePosition, move: Coordinate,
                 seed: int, mode: str, history: list[Coordinate],
                 failure_dir: Path) -> tuple[Position, ReferencePosition, int]:
    before, ref_before = state(position), state(reference)
    try:
        actual = position.play(move)
        expected = reference.play(move)
        if state(actual.position) != state(expected.position):
            raise AssertionError('Board, side, outcome, or reason mismatch.')
        if {item.cell: item.prior_value for item in actual.captured} != {
                item.cell: item.prior_value for item in expected.captured}:
            raise AssertionError('Captured cells/prior values mismatch.')
        if state(position) != before or state(reference) != ref_before:
            raise AssertionError('Parent state mutated.')
    except Exception as error:
        failure_dir.mkdir(parents=True, exist_ok=True)
        path = failure_dir / f'mismatch-{mode}-{seed}.json'
        path.write_text(json.dumps({
            'seed': seed, 'mode': mode, 'moves': history + [move],
            'initial_board': Position.empty().board, 'initial_side': 0,
            'before': before, 'reference_before': ref_before,
            'error': repr(error),
        }, indent=2) + '\n')
        raise AssertionError(f'Differential failure; replay moves in {path}') from error
    return actual.position, expected.position, len(actual.captured)


def run_sequences(sequences: int = 16, max_moves: int = 240, seed: int = 20261008,
                  failure_dir: Path = Path('.scratch/differential')) -> dict[str, Any]:
    records = []
    checked = 0
    started = time.perf_counter()
    for mode in ('ordinary', 'capture_biased'):
        for number in range(sequences):
            sequence_seed = seed + number + (100000 if mode == 'capture_biased' else 0)
            rng = random.Random(sequence_seed)
            position = Position.empty()
            reference = ReferencePosition.empty()
            history: list[Coordinate] = []
            captured_count = 0
            for ply in range(max_moves):
                if position.outcome != 'ongoing':
                    break
                if ply % 20 == 0:
                    snapshot = state(position)
                    siblings = []
                    for move in rng.sample(legal_moves(position.board),
                                           min(3, len(legal_moves(position.board)))):
                        child, ref_child, _ = checked_move(
                            position, reference, move, sequence_seed, mode, history, failure_dir)
                        checked += 1
                        siblings.append((child, state(child)))
                        if child.outcome == 'ongoing':
                            nested_move = rng.choice(legal_moves(child.board))
                            checked_move(child, ref_child, nested_move, sequence_seed, mode,
                                         history + [move], failure_dir)
                            checked += 1
                    if state(position) != snapshot or any(state(child) != saved for child, saved in siblings):
                        raise AssertionError('Parent/sibling isolation failure.')
                move = choose_move(position, rng, mode == 'capture_biased')
                position, reference, captured = checked_move(
                    position, reference, move, sequence_seed, mode, history, failure_dir)
                checked += 1
                captured_count += captured
                history.append(move)
            records.append({'mode': mode, 'seed': sequence_seed, 'moves': len(history),
                            'captured_stones': captured_count, 'outcome': position.outcome,
                            'reason': position.reason,
                            'stopped': 'terminal' if position.outcome != 'ongoing' else 'verification_cap'})
    return {'sequences_per_mode': sequences, 'max_moves': max_moves,
            'checked_transitions': checked, 'elapsed_seconds': time.perf_counter() - started,
            'records': records}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sequences', type=int, default=16)
    parser.add_argument('--max-moves', type=int, default=240)
    parser.add_argument('--seed', type=int, default=20261008)
    parser.add_argument('--failure-dir', type=Path, default=Path('.scratch/differential'))
    args = parser.parse_args()
    if args.sequences < 1 or args.max_moves < 1:
        parser.error('Sequence and move counts must be positive.')
    print(json.dumps(run_sequences(args.sequences, args.max_moves, args.seed, args.failure_dir), indent=2))


if __name__ == '__main__':
    main()
