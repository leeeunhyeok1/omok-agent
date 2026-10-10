# AI-written by OpenAI Codex, for issue #38.
"""A bounded actual candidate cohort, saved gates, screening and resume evidence."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic
from typing import Any

from offline.experiments import save_new_json
from offline.proposals import ProposalPolicy, generate
from offline.registry import Entry, canonical, default_catalog, digest
from offline.replay import replay
from offline.screening import ScreeningPolicy, prepare, run

# Only this isolated process imports the candidate's restored engine.
PROBE = '''import json, math, os, sys, tempfile
from offline.registry_worker import create
with tempfile.TemporaryDirectory() as snapshots:
    os.environ['OMOK_WORKER_SNAPSHOTS'] = snapshots
    entry = json.loads(sys.stdin.read())
    probes = []
    for color in (0, 1):
        player = create(color, entry=entry, seed=38)
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
            child = Position(before, color).play(move).position
            assert board == before
            if kind == 'win':
                assert child.outcome == ('black_win' if color == 0 else 'white_win')
            elif kind == 'capture-defense':
                assert tuple(move) == (7, 7)
            diagnostics = player.diagnostics()
            score = diagnostics.get('score')
            assert score is None or (type(score) in (int, float) and math.isfinite(score))
            probes.append(dict(color=color, fixture=kind, initial=before, move=move,
                               unchanged_input=True, score=score, diagnostics=diagnostics))
    print(json.dumps(probes, allow_nan=False))
'''


def collect(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    start = monotonic()
    catalog, snapshot = default_catalog()
    incumbent = catalog['phase3-material']
    proposal_path = output / 'proposal-policy.json'
    ProposalPolicy.for_parent(incumbent, batch='evaluation', groups=['material']).save(proposal_path)
    batch = generate(proposal_path, [incumbent], seed=38, count=2, output=output / 'proposals')
    candidates = [Entry.from_record(c['entry']) for c in batch['candidates']]
    gates = {}
    for entry in [incumbent] + candidates:
        process = subprocess.run([sys.executable, '-B', '-c', PROBE], input=canonical(entry.record()),
                                 capture_output=True, text=True, timeout=30)
        if process.returncode:
            raise ValueError('Candidate gate failed: ' + process.stderr)
        probes = json.loads(process.stdout)
        gates[entry.identity] = [dict(check=check, status='pass', samples=len(probes),
            evidence={'candidate_identity': entry.identity, 'probe': probes,
                      'scope': 'six fixed public calls including low-time reuse; bounded screening gate, not full correctness proof'})
            for check in ('restoration', 'invalid_score', 'mandatory_tactic')]
    save_new_json(output / 'gates.json', gates)
    # Reduced-clock legal paired opening permits a small completed screen. It is
    # intentionally easy and must never be described as full-league strength.
    policy = ScreeningPolicy.create(opponents={'smoke': 2, 'synthetic-aggressive': 2},
        opponent_weights={'smoke': 1, 'synthetic-aggressive': 1},
        family_weights={'random-smoke': 1, 'line-pattern': 1}, min_evidence_per_color=1,
        total_ms=5000, move_cap=20)
    policy.save(output / 'screening-policy.json')
    opening = [[9, 5], [10, 5], [9, 6], [10, 6], [9, 7], [10, 7], [9, 8], [10, 8]]
    prepare(output / 'screening-policy.json', incumbent, candidates, snapshot,
            output=output / 'stage', openings=[opening], gates=gates)
    partial = run(output / 'stage', max_jobs_per_plan=1)
    final = run(output / 'stage')
    traces = 0
    for path in (output / 'stage').glob('*/results.json'):
        raw = json.loads(path.read_text(encoding='utf-8'))
        for record in raw['results']:
            if record['trace'] is not None:
                replay(record['trace'])
                traces += 1
    summary = {'format': 'omok-screening-pilot-v1', 'incumbent': incumbent.identity,
        'candidates': {i: {k: e[k] for k in ('status', 'fitness', 'gain', 'reasons', 'reliability_samples')}
                       for i, e in final['candidates'].items()},
        'partial_statuses': {i: e['status'] for i, e in partial['candidates'].items()},
        'replayed_traces': traces, 'retained_incumbent': final['retained_incumbent'],
        'promotion': final['promotion'], 'elapsed_seconds': monotonic() - start,
        'validation_exposures': [], 'holdout_exposures': [],
        'limitations': '12 reduced-clock games from one easy legal paired opening against two training designs. No full-league, promotion, validation or official-clock claim.'}
    save_new_json(output / 'summary.json', summary)
    # Keep every manifest, checkpoint, attempt, trace, gate and decision in one
    # portable compressed artifact for review without thousands of loose files.
    artifacts = {p.relative_to(output).as_posix(): json.loads(p.read_text(encoding='utf-8'))
                 for p in sorted(output.rglob('*.json'))}
    with (output / 'evidence.json.gz').open('xb') as stream:
        stream.write(gzip.compress(canonical({'identity': digest(artifacts), 'artifacts': artifacts}).encode(), mtime=0))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(canonical(collect(args.output)))


if __name__ == '__main__':
    main()
