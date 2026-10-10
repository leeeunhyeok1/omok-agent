# AI-written by OpenAI Codex, for issue #31.
"""Reproduce agent-free legacy replay, supervision exports and checked fixtures."""
import argparse
import gzip
import json
from pathlib import Path

from offline.fixtures import fixture
from offline.inspection import checked_fixture, inspect_loss, verify_fixture
from offline.replay import replay
from offline.runner import run_game
from offline.supervised import PlayerSpec, Supervision, run_supervised_game
from tests.test_runner import ReturningPlayer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.scratch/loss-inspection'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary: dict = {'legacy_replays': [], 'supervised': [], 'fixtures': []}

    def save(name: str, data: dict) -> None:
        (args.output / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')

    for path in sorted(Path('docs/verification/issue-30').glob('game-*.json.gz')):
        record = json.loads(gzip.decompress(path.read_bytes()))
        trace = record.get('trace', record)
        position = replay(trace)
        summary['legacy_replays'].append({'path': path.as_posix(), 'outcome': position.outcome})
    for behavior in ('raise', 'exit', 'loop'):
        trace = run_supervised_game(PlayerSpec('tests.test_supervised', 'StatefulPlayer'),
            PlayerSpec('tests.test_supervised', 'BrokenPlayer', {'behavior': behavior}),
            budgets_ms=(200, 40), move_cap=4, diagnostics=True,
            supervision=Supervision(startup_ms=3000, cleanup_ms=200))
        report = inspect_loss(trace)
        assert report['positions'][-1]['ply'] == 1
        assert report['board_outcome'] == 'ongoing'
        save(f'{behavior}-trace.json', trace)
        save(f'{behavior}-inspection.json', report)
        summary['supervised'].append({'behavior': behavior, 'reason': trace['reason'], 'exported': len(report['positions'])})
    for name, outcome, reason in (('mover-win', 'black_win', 'exact_five'),
                                  ('opponent-win', 'white_win', 'exact_five'),
                                  ('simultaneous', 'draw', 'simultaneous_wins')):
        trace = run_game(ReturningPlayer(0, [(8, 10)]), ReturningPlayer(1, []), initial=fixture(name))
        checked = checked_fixture(trace, ply=0, color=0, expected_outcome=outcome, expected_reason=reason)
        verify_fixture(checked)
        save(f'{name}-fixture.json', checked)
        save(f'{name}-trace.json', trace)
        summary['fixtures'].append({'name': name, 'outcome': replay(trace).outcome, 'checked': True})
    save('summary.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
