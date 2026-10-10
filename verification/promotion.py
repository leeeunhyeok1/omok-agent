# AI-written by OpenAI Codex, for issue #42.
"""Incumbent validation audit and serial eight-game practical official clock check."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic

from offline.experiments import save_new_json
from offline.promotion import PromotionPolicy, prepare, run
from offline.registry import canonical, default_catalog, digest
from offline.replay import replay
from verification.screening import PROBE


def collect(output: Path, power: str, load: str) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    start = monotonic()
    catalog, snapshot = default_catalog()
    incumbent = catalog['phase3-material']
    process = subprocess.run([sys.executable, '-B', '-c', PROBE], input=canonical(incumbent.record()),
        capture_output=True, text=True, timeout=30)
    if process.returncode:
        raise ValueError('Restored incumbent gate failed: ' + process.stderr)
    probes = json.loads(process.stdout)
    gates = {incumbent.identity: [dict(check=check, status='pass', samples=len(probes),
        evidence={'candidate_identity': incumbent.identity, 'public_boundary_probes': probes})
        for check in ('restoration', 'invalid_score', 'mandatory_tactic')]}
    save_new_json(output / 'gates.json', gates)
    policy = PromotionPolicy.create(validation={'synthetic-defensive': 4}, official_opponents=['smoke'],
        validation_ms=5000, validation_cap=100, min_validation_pairs=2)
    policy.save(output / 'policy.json')
    openings = [[], [[9, 5], [10, 5], [9, 6], [10, 6], [9, 7], [10, 7], [9, 8], [10, 8]]]
    prepare(output / 'policy.json', incumbent, snapshot, output=output / 'checks', gates=gates,
        prior_exposures=[{'source': 'docs/verification/issue-30.md and issue-34.md',
            'details': 'Phase 4 used synthetic-defensive for controlled and actual smoke evidence. '
                'Already exposed; shared synthetic rules/source utilities and repeated use limit independence. '
                'No claim of untouched validation; exact earlier games remain in those artifacts.'}], openings=openings)
    conditions = {'power': power, 'load': load, 'other_experiments_stopped': True}
    save_new_json(output / 'conditions.json', conditions)
    final = run(output / 'checks', conditions=conditions, max_jobs_per_plan=8)
    path = output / 'checks/eligibility-results.json'
    evidence = json.loads(path.read_text(encoding='utf-8'))['data']['raw']
    replayed = 0
    for raw in evidence.values():
        for result in raw['results']:
            if result.get('trace') is not None:
                replay(result['trace'])
                replayed += 1
    member = final['candidates'][incumbent.identity]
    summary = {'incumbent': incumbent.identity, 'status': member['status'], 'reasons': member['reasons'],
        'validation': {k: member['validation'][k] for k in ('requested_jobs', 'by_opponent', 'reliability_samples')},
        'official': {k: member['official'][k] for k in ('requested_jobs', 'by_opponent', 'reliability_samples')},
        'clock': member['clock'], 'promotion': False, 'holdout_exposures': [],
        'untouched_final_evidence': False, 'replayed_traces': replayed,
        'elapsed_seconds': monotonic() - start, 'limitations': final['limitations']}
    save_new_json(output / 'summary.json', summary)
    artifacts = {p.relative_to(output).as_posix(): json.loads(p.read_text(encoding='utf-8'))
                 for p in sorted(output.rglob('*.json'))}
    with (output / 'evidence.json.gz').open('xb') as stream:
        stream.write(gzip.compress(canonical({'identity': digest(artifacts), 'artifacts': artifacts}).encode(), mtime=0))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--power', required=True, help='Observed AC/battery and power policy, including unknowns')
    parser.add_argument('--load', required=True, help='Observed load; stop other experiments first')
    args = parser.parse_args()
    summary = collect(args.output, args.power, args.load)
    print(canonical({k: summary[k] for k in ('status', 'reasons', 'elapsed_seconds', 'replayed_traces')}))


if __name__ == '__main__':
    main()
