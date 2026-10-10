# AI-written by OpenAI Codex, for issue #41.
"""Controlled selection followed by bounded actual-engine confirmation fixtures."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic

from offline.confirmation import ConfirmationPolicy, prepare, run
from offline.experiments import ExperimentPlan, save_new_json
from offline.proposals import ProposalPolicy, generate
from offline.registry import Entry, canonical, default_catalog, digest
from offline.screening import ScreeningPolicy, prepare as screen
from verification.screening import PROBE
from tests.test_matches import scoring_start
from tests.test_screening import results


def collect(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    start = monotonic()
    catalog, snapshot = default_catalog()
    incumbent = catalog['phase3-material']
    ProposalPolicy.for_parent(incumbent, batch='evaluation', groups=['material']).save(output / 'proposal-policy.json')
    proposals = generate(output / 'proposal-policy.json', [incumbent], seed=41, count=1, output=output / 'population')
    candidates = [Entry.from_record(c['entry']) for c in proposals['candidates']]
    gates = {}
    for entry in [incumbent] + candidates:
        probe = subprocess.run([sys.executable, '-B', '-c', PROBE], input=canonical(entry.record()),
                               capture_output=True, text=True, timeout=30)
        if probe.returncode:
            raise ValueError('Restored candidate gate failed: ' + probe.stderr)
        checks = json.loads(probe.stdout)
        gates[entry.identity] = [dict(check=name, status='pass', samples=len(checks),
            evidence={'candidate_identity': entry.identity, 'probe': checks})
            for name in ('restoration', 'invalid_score', 'mandatory_tactic')]
    settings = dict(opponents={'smoke': 4, 'synthetic-random': 4},
        opponent_weights={'smoke': 1, 'synthetic-random': 1},
        family_weights={'random-smoke': 1, 'frontier-random': 1},
        min_evidence_per_color=1, total_ms=5000, move_cap=2)
    ScreeningPolicy.create(**settings, seed=4100).save(output / 'selection-policy.json')
    selection = screen(output / 'selection-policy.json', incumbent, candidates, snapshot,
                       output=output / 'selection', fixture=scoring_start(), gates=gates)
    raw = {p['identity']: results(ExperimentPlan.from_record(p),
            ['loss' if m['entry']['identity'] == incumbent.identity else 'win'] * 4)
           for m in selection['members'] for p in m['plans']}
    save_new_json(output / 'controlled-selection-results.json', raw)
    ConfirmationPolicy.create(screening=ScreeningPolicy.create(**settings, seed=4101).data).save(output / 'policy.json')
    prepare(output / 'policy.json', selection=output / 'selection', selection_raw=raw,
            output=output / 'confirmation', fixture=scoring_start())
    declared = (output / 'confirmation/confirmation.json').read_bytes()
    partial = run(output / 'confirmation', max_jobs_per_plan=1)
    final = run(output / 'confirmation', max_jobs_per_plan=4)
    again = run(output / 'confirmation', max_jobs_per_plan=0)
    assert (output / 'confirmation/confirmation.json').read_bytes() == declared
    assert final['advanced'] == again['advanced']
    assert not final['promotion'] and not final['ordinary_strength_evidence']
    summary = {'selection': 'controlled artificial winner; no actual selection strength claim',
        'confirmation': '16 actual supervised artificial games using restored incumbent/proposed configuration',
        'partial_statuses': {i: c['status'] for i, c in partial['candidates'].items()},
        'candidates': {i: {k: c[k] for k in ('status', 'reasons', 'effect', 'distinct_pairs',
            'sensitivity_range', 'reliability_samples')} for i, c in final['candidates'].items()},
        'retained_incumbent': final['retained_incumbent'], 'promotion': False,
        'ordinary_strength_evidence': False, 'elapsed_seconds': monotonic() - start,
        'validation_exposures': [], 'holdout_exposures': []}
    save_new_json(output / 'summary.json', summary)
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
