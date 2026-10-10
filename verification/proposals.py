# AI-written by OpenAI Codex, for issue #37.
"""Bounded proposal/execution evidence; no fitness, promotion or holdout exposure."""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
from time import monotonic
from typing import Any

from offline.proposals import ProposalPolicy, generate, resolve_entry
from offline.registry import Entry, canonical, default_catalog, digest
from offline.replay import replay
from offline.registry import run_registered_game
from verification.reference import ReferencePosition


def collect(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    catalog, pools = default_catalog()
    parent = catalog['phase3-material']
    start = monotonic()
    batches = []
    games = []
    for kind, groups in (('evaluation', ['material']), ('search-time', ['candidates', 'time'])):
        path = output / (kind + '-policy.json')
        policy = ProposalPolicy.for_parent(parent, batch=kind, groups=groups, repair='clip-domain')
        policy.save(path)
        batch = generate(path, [parent], seed=37, count=2, output=output / kind)
        reproduced = generate(path, [parent], seed=37, count=2, output=output / (kind + '-repeat'))
        if batch != reproduced or not batch['candidates']:
            raise ValueError('Proposal reproduction failed or no candidate accepted.')
        candidate_record = batch['candidates'][0]
        candidate = Entry.from_record(candidate_record['entry'])
        batches.append({'kind': kind, 'policy_identity': policy.identity, 'seed': 37,
            'reproduced_exactly': True, 'accepted': len(batch['candidates']),
            'attempts': len(batch['attempts']), 'exhausted_slots': batch['exhausted_slots'],
            'executed_genotype': candidate_record['genotype'], 'candidate': candidate.record(),
            'actual_configuration': resolve_entry(candidate)})
        for color in (0, 1):
            trace = run_registered_game(candidate, pools, 'smoke', candidate_color=color,
                purpose='training', seed=37, move_cap=4, budgets_ms=(5000, 5000), diagnostics=True)
            replayed = replay(trace)
            reference = ReferencePosition.empty()
            for event in trace['moves']:
                reference = reference.play(event['move']).position
            if (reference.board, reference.side_to_move, reference.outcome, reference.reason) != (
                    replayed.board, replayed.side_to_move, replayed.outcome, replayed.reason):
                raise ValueError('Independent reference disagrees with the candidate trace.')
            if trace['status'] != 'capped' or len(trace['moves']) != 4:
                raise ValueError('Bounded pilot produced a player or infrastructure failure.')
            trace_path = output / (kind + '-color-' + str(color) + '.json.gz')
            with trace_path.open('xb') as stream:
                stream.write(gzip.compress(canonical(trace).encode(), mtime=0))
            games.append({'batch': kind, 'candidate_color': color, 'status': trace['status'],
                'moves': len(trace['moves']), 'trace': trace_path.name,
                'sha256': sha256(trace_path.read_bytes()).hexdigest(),
                'replay_verified': True, 'reference_outcome': reference.outcome})
            print(kind + ' color ' + str(color) + ': replayed capped game', flush=True)
    result = {'format': 'omok-proposal-pilot-v1', 'parent': parent.record(),
        'parent_configuration': resolve_entry(parent), 'pool_snapshot': pools.record(),
        'batches': batches, 'games': games, 'elapsed_seconds': monotonic() - start,
        'holdout_exposures': [], 'validation_exposures': [],
        'limitations': '4 capped screening games; no completed league fitness, strength claim or promotion',
        'proposal_artifacts': {path.relative_to(output).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.rglob('*.json'))}}
    (output / 'summary.json').write_text(json.dumps({'identity': digest(result), 'pilot': result},
        indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.output)
    print(canonical({'games': len(result['games']), 'holdout_exposures': [],
                     'elapsed_seconds': result['elapsed_seconds']}))


if __name__ == '__main__':
    main()
