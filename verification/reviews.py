# AI-written by OpenAI Codex, for issue #44.
"""Reproduce controlled reviews and checked missed-win regressions without opponents."""
import argparse
import json
from pathlib import Path

from offline.inspection import inspect_loss
from offline.regressions import analyze_tactic, export_regression
from offline.reviews import review_batch, render_review
from offline.runner import run_game
from omok.simulator import Position
from tests import test_screening
from tests.test_runner import ReturningPlayer


def collect(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    stage, raw, _, _ = test_screening.ScreeningTests().cohort(output)
    review = review_batch(stage, raw, max_failures=2)
    board = [[-1] * 19 for _ in range(19)]
    board[9][4] = 1
    board[9][5:9] = [0] * 4
    trace = run_game(ReturningPlayer(0, [(0, 0)]), ReturningPlayer(1, []),
                     initial=Position(board, 0), move_cap=1)
    record = inspect_loss(trace, color=0)['positions'][0]
    partial = analyze_tactic(record, kind='immediate-win', max_transitions=1, max_seconds=10)
    analysis = analyze_tactic(record, kind='immediate-win', max_transitions=361, max_seconds=30)
    path = export_regression(output / 'fixtures', trace, ply=0, color=0, analysis=analysis)
    for name, data in [('raw.json', raw), ('review.json', review), ('trace.json', trace),
                       ('unknown-analysis.json', partial), ('checked-analysis.json', analysis),
                       ('summary.json', {'format': 'omok-review-controlled-example-v1',
                           'attribution': 'AI-written OpenAI Codex controlled examples; fabricated outcomes, not measured strength',
                           'holdout_calls': 0, 'validation_calls': 0, 'registered_opponent_calls': 0,
                           'checked_fixture': str(path.relative_to(output)),
                           'allowed_moves': analysis['allowed_moves'], 'partial_status': partial['status']})]:
        (output / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (output / 'review.md').write_text(render_review(review), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    collect(parser.parse_args().output)
