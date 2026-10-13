# AI-written by OpenAI Codex for issue #45.
"""Actual restored-player gates, isolated from the optimizer's engine imports."""
import json
import subprocess
import sys
from typing import Any

from offline.registry import Entry, canonical

# Fixed fixtures are also exercised by the repository's public tactical suite.
PROBE = '''import json, math, os, sys, tempfile
from offline.registry_worker import create
with tempfile.TemporaryDirectory() as snapshots:
    os.environ['OMOK_WORKER_SNAPSHOTS'] = snapshots
    entry = json.loads(sys.stdin.read())
    probes = []
    for color in (0, 1):
        player = create(color, entry=entry, seed=45)
        from omok.simulator import Position
        for kind in ('interruption', 'win', 'capture-defense'):
            board = [[-1] * 19 for _ in range(19)]
            if kind == 'win':
                board[9][5:9] = [color] * 4
            elif kind == 'capture-defense':
                for r, c in ((9, 6), (9, 7), (9, 8), (9, 9), (8, 7)):
                    board[r][c] = 1 - color
                board[10][7] = color
            before = [row[:] for row in board]
            move = player.take_turn(board, 0 if kind == 'interruption' else 5000)
            position = Position(before, color)
            outcome = position.play(move).position.outcome
            assert position.board == tuple(tuple(row) for row in before)
            assert board == before
            if kind == 'win':
                assert outcome == ('black_win' if color == 0 else 'white_win')
            elif kind == 'capture-defense':
                assert tuple(move) == (7, 7)
            score = player.diagnostics().get('score')
            assert score is None or (type(score) in (int, float) and math.isfinite(score))
            probes.append(dict(color=color, fixture=kind, initial=before, move=move,
                               unchanged_input=True, score=score))
    print(json.dumps(probes, allow_nan=False))
'''


def evaluate(entry: Entry, suite_identity: str, *, timeout: float = 30) -> list[dict[str, Any]]:
    """Retain failures as vetoes; never manufacture passing gate evidence."""
    process = subprocess.run([sys.executable, '-B', '-c', PROBE], input=canonical(entry.record()),
                             capture_output=True, text=True, timeout=timeout)
    probes = json.loads(process.stdout) if process.returncode == 0 else []
    return [dict(check=check, status='pass' if probes else 'fail', samples=max(1, len(probes)),
                 suite_identity=suite_identity, evidence={'candidate_identity': entry.identity,
                     'probes': probes, 'returncode': process.returncode, 'stderr': process.stderr[-4000:],
                     'scope': 'six fixed restored public calls; rules transitions, input, scores and mandatory tactics'})
            for check in ('restoration', 'invalid_score', 'mandatory_tactic')]
