# AI-written by OpenAI Codex, for issue #40.
"""Bounded real-engine broader-round pilot after a controlled screening admission."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic

from offline.experiments import ExperimentPlan, save_new_json
from offline.league import LeaguePolicy, archive_history, prepare, run
from offline.proposals import ProposalPolicy, generate
from offline.registry import Entry, canonical, default_catalog, digest
from offline.replay import replay
from offline.screening import ScreeningPolicy, prepare as screen
from tests.test_matches import scoring_start
from tests.test_screening import results
from verification.screening import PROBE


def collect(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    start = monotonic()
    catalog, snapshot = default_catalog()
    incumbent = catalog['phase3-material']
    proposal = output / 'proposal-policy.json'
    ProposalPolicy.for_parent(incumbent, batch='evaluation', groups=['material']).save(proposal)
    population = generate(proposal, [incumbent], seed=40, count=1, output=output / 'population')
    candidate = Entry.from_record(population['candidates'][0]['entry'])
    gates = {}
    for entry in (incumbent, candidate):
        probe = subprocess.run([sys.executable, '-B', '-c', PROBE], input=canonical(entry.record()),
                               capture_output=True, text=True, timeout=30)
        if probe.returncode:
            raise ValueError(probe.stderr)
        evidence = json.loads(probe.stdout)
        gates[entry.identity] = [dict(check=check, status='pass', samples=len(evidence),
            evidence={'scope': 'six actual public calls; bounded fixed gates', 'probes': evidence})
            for check in ('restoration', 'invalid_score', 'mandatory_tactic')]
    screen_policy = ScreeningPolicy.create(opponents={'synthetic-aggressive': 2},
        opponent_weights={'synthetic-aggressive': 1}, family_weights={'line-pattern': 1},
        min_evidence_per_color=1, move_cap=2)
    screen_policy.save(output / 'screen-policy.json')
    rung = screen(output / 'screen-policy.json', incumbent, [candidate], snapshot,
                  output=output / 'screen', fixture=scoring_start(), gates=gates)
    controlled = {r['identity']: results(ExperimentPlan.from_record(r),
        ['loss'] * 2 if m['entry']['identity'] == incumbent.identity else ['win'] * 2)
        for m in rung['members'] for r in m['plans']}
    old = catalog['phase2']
    history = archive_history(output / 'history', [old])
    opponents = {'synthetic-aggressive': 2, 'synthetic-capture': 2,
                 incumbent.data['logical_id']: 2, old.data['logical_id']: 2}
    policy = LeaguePolicy.create(screening=ScreeningPolicy.create(opponents=opponents,
        opponent_weights={n: 1 for n in opponents},
        family_weights={'line-pattern': 1, 'capture-collection': 1, 'omok': 1},
        min_evidence_per_color=1, move_cap=20, seed=40).data,
        history_period=2, history_slots={old.identity: 0})
    policy.save(output / 'league-policy.json')
    opening = [[9, 5], [10, 5], [9, 6], [10, 6], [9, 7], [10, 7], [9, 8], [10, 8]]
    prepare(output / 'league-policy.json', incumbent, snapshot, history=history,
        rungs=[(output / 'screen', controlled)], output=output / 'round', openings=[opening], gates=gates)
    partial = run(output / 'round', max_jobs_per_plan=1)
    final = run(output / 'round')
    again = run(output / 'round', max_jobs_per_plan=0)
    traces = 0
    for path in (output / 'round').glob('*/results.json'):
        for result in json.loads(path.read_text(encoding='utf-8'))['results']:
            if result['trace'] is not None:
                replay(result['trace'])
                traces += 1
    keys = ('status', 'fitness', 'gain', 'reasons', 'by_family', 'by_color', 'worst_matchup', 'reliability_samples')
    summary = {'incumbent': incumbent.identity, 'candidate': candidate.identity,
        'candidates': {i: {k: e[k] for k in keys} for i, e in final['candidates'].items()},
        'partial_statuses': {i: e['status'] for i, e in partial['candidates'].items()},
        'resumed_samples_unchanged': all(e['reliability_samples'] == again['candidates'][i]['reliability_samples']
                                       for i, e in final['candidates'].items()),
        'history_coverage': final['history_coverage'], 'replayed_traces': traces,
        'elapsed_seconds': monotonic() - start, 'advanced': final['advanced'], 'promotion': False,
        'validation_exposures': [], 'holdout_exposures': [],
        'limitations': 'Controlled screening admission; 16 actual reduced-clock jobs from one easy legal opening, '
            'two synthetic designs plus incumbent and retained phase2. No full-game strength, promotion or official-clock claim.'}
    save_new_json(output / 'summary.json', summary)
    artifacts = {p.relative_to(output).as_posix(): json.loads(p.read_text(encoding='utf-8'))
                 for p in sorted(output.rglob('*.json'))}
    (output / 'evidence.json.gz').write_bytes(gzip.compress(
        canonical({'identity': digest(artifacts), 'artifacts': artifacts}).encode(), mtime=0))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(canonical(collect(parser.parse_args().output)))
