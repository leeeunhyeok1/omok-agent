# AI-written by OpenAI Codex, for issue #28.
"""Score saved eight-slot plans without changing their raw execution evidence."""
from typing import Any

from offline.experiments import ExperimentPlan
from offline.replay import replay
from offline.runner import state
from omok.simulator import Position

FORMAT = 'omok-match-scores-v1'
SCORING_POLICY = {
    'version': 'eight-game-local-v1',
    'strict_wins': 'rules wins plus documented execution forfeits; draws never count',
    'crash': 'in-turn exception or player_exit forfeits game and overrides opponent match',
    'other_player_failures': 'timeout, invalid_move, mutation, protocol_error forfeit game only',
    'infrastructure': 'setup, supervisor, invalid trace: unresolved match; no coins',
    'caps_and_pending': 'unresolved match; no draw, win or coins',
    'both_crash': 'unresolved tournament; candidate crash still disqualifies',
    'development': 'recognized game-win comparison only; ignores match crash override; no coins',
}
CRASH_REASONS = ('exception', 'player_exit')
FORFEIT_REASONS = CRASH_REASONS + ('timeout', 'invalid_move', 'mutation', 'protocol_error')


def rule_result(winner: int | None, candidate_color: int) -> str:
    return 'draw' if winner is None else 'candidate_win' if winner == candidate_color else 'opponent_win'


def game_score(job: dict[str, Any], record: dict[str, Any] | None, manifest: dict[str, Any]) -> dict[str, Any]:
    slot = {k: job[k] for k in ('game_id', 'slot', 'candidate_color')}
    slot.update(category='pending', rules=None, execution=None, recognized_result=None, crashes=[])
    if record is None:
        return slot
    trace = record.get('trace')
    slot['execution'] = {'status': record.get('status'), 'error': record.get('error'),
        'reason': trace.get('reason') if isinstance(trace, dict) else None,
        'failure': trace.get('failure') if isinstance(trace, dict) else None}
    slot['category'] = 'infrastructure_failed'
    if trace is None and record.get('status') == 'setup_failed':
        return slot
    try:
        if not isinstance(trace, dict) or record['status'] != trace['status']:
            raise ValueError('Missing trace or conflicting execution status.')
        position = replay(trace)
        opening = job['opening']
        if trace['initial'] != state(Position(opening['board'], opening['side_to_move'])) or any(
                trace[key] != manifest['settings'][key] for key in ('budgets_ms', 'move_cap')):
            raise ValueError('Trace starting state or execution settings disagree with the plan.')
        # When present, runner provenance must agree with the saved job.
        provenance = trace['config'].get('experiment')
        if provenance is not None and (provenance['job'] != job or
                                      provenance['manifest_identity'] != manifest['identity']):
            raise ValueError('Trace provenance disagrees with the planned job.')
        if 'prior_result' in trace and (trace['status'], trace['reason']) != ('supervisor_error', 'cleanup_error'):
            raise ValueError('Unexpected prior result outside a cleanup error.')
        slot['rules'] = {'outcome': position.outcome, 'winner': trace['winner'], 'reason': position.reason}
        # Cleanup errors retain an earlier player failure; infrastructure invalidity
        # prevents coins but must not erase the reproduced crash fact.
        failures = [trace['failure']]
        if trace['reason'] == 'cleanup_error':
            failures.append(trace['prior_result']['failure'])
        for failure in failures:
            if failure and failure['color'] in (0, 1) and (
                    any(v in CRASH_REASONS for v in failure['violations']) or
                    (failure['called'] and failure['exception'] is not None)):
                role = 'candidate' if failure['color'] == job['candidate_color'] else 'opponent'
                slot['crashes'].append(role)
        if trace['status'] == 'completed':
            slot['category'] = 'completed'
            slot['recognized_result'] = rule_result(trace['winner'], job['candidate_color'])
        elif trace['status'] == 'capped':
            slot['category'] = 'capped'
        elif trace['status'] == 'failed' and all(
                v in FORFEIT_REASONS for v in trace['failure']['violations']):
            slot['category'] = 'failed'
            slot['recognized_result'] = ('opponent_win' if trace['failure']['color'] == job['candidate_color']
                                         else 'candidate_win')
    except (ValueError, KeyError, TypeError) as error:
        slot['validation_error'] = str(error)
    return slot


def match_score(match_id: str, jobs: list[dict[str, Any]], records: dict[str, Any],
                manifest: dict[str, Any]) -> dict[str, Any]:
    slots = [game_score(job, records.get(job['game_id']), manifest) for job in jobs]
    colors = [sum(j['candidate_color'] == color for j in jobs) for color in (0, 1)]
    counts = {category: sum(s['category'] == category for s in slots) for category in
              ('completed', 'failed', 'capped', 'infrastructure_failed', 'pending')}
    counts['planned'] = len(jobs)
    flags = []
    if len(jobs) != 8 or colors != [4, 4] or sorted(j['slot'] for j in jobs) != list(range(8)):
        flags.append('invalid_schedule')
    for category, flag in (('pending', 'incomplete'), ('capped', 'capped'),
                           ('infrastructure_failed', 'infrastructure_invalid')):
        if counts[category]:
            flags.append(flag)
    recognized = {key: sum(s['recognized_result'] == result for s in slots) for key, result in
                  (('candidate_wins', 'candidate_win'), ('opponent_wins', 'opponent_win'), ('draws', 'draw'))}
    rules_score = {'candidate_wins': 0, 'opponent_wins': 0, 'draws': 0}
    for slot in slots:
        rules = slot['rules']
        if rules and rules['outcome'] != 'ongoing':
            key = {'draw': 'draws', 'candidate_win': 'candidate_wins', 'opponent_win': 'opponent_wins'}[
                rule_result(rules['winner'], slot['candidate_color'])]
            rules_score[key] += 1
    crashes = {role: any(role in s['crashes'] for s in slots) for role in ('candidate', 'opponent')}
    if all(crashes.values()):
        flags.append('both_crash')
    complete = not flags
    wins = recognized['candidate_wins'], recognized['opponent_wins']
    development_outcome = 'win' if wins[0] > wins[1] else 'loss' if wins[0] < wins[1] else 'draw'
    override = ('both_crash' if all(crashes.values()) else 'candidate_crash' if crashes['candidate'] else
                'opponent_crash' if crashes['opponent'] else None)
    outcome = 'loss' if override == 'candidate_crash' else 'win' if override == 'opponent_crash' else development_outcome
    return {'match_id': match_id, 'opponent_identity': jobs[0]['opponent']['identity'],
        'colors': colors, 'counts': counts, 'slots': slots, 'recognized': recognized,
        'rules_score': rules_score, 'crashes': crashes, 'flags': flags, 'complete': complete,
        'qualification': {'qualified': False if crashes['candidate'] else wins[0] >= 5 if complete else None},
        'tournament': {'outcome': outcome if complete else 'unresolved',
            'coins': {'win': [2, 0], 'loss': [0, 2], 'draw': [1, 1]}[outcome] if complete else None,
            'override': override},
        'development': {'outcome': development_outcome, 'resolved_games': sum(recognized.values()),
                        'policy': 'recognized-game-wins-only; partial evidence when unresolved'}}


def score_experiment(plan: ExperimentPlan, raw: dict[str, Any]) -> dict[str, Any]:
    plan = ExperimentPlan.from_record(plan.record())
    if raw['format'] != 'omok-experiment-results-v1' or raw['manifest_identity'] != plan.identity:
        raise ValueError('Results do not belong to this saved plan.')
    jobs_by_id = {job['game_id']: job for job in plan.data['jobs']}
    records = {}
    for record in raw['results']:
        game_id = record['game_id']
        if game_id not in jobs_by_id or game_id in records:
            raise ValueError('Foreign or duplicate game result.')
        job = jobs_by_id[game_id]
        if any(type(record[k]) is not type(job[k]) or record[k] != job[k]
               for k in ('match_id', 'slot', 'candidate_color')):
            raise ValueError('Result assignment disagrees with its planned slot.')
        records[game_id] = record
    groups: dict[str, list[dict[str, Any]]] = {}
    for job in plan.data['jobs']:
        groups.setdefault(job['match_id'], []).append(job)
    matches = [match_score(match_id, jobs, records, plan.record()) for match_id, jobs in groups.items()]
    return {'format': FORMAT, 'manifest_identity': plan.identity,
            'mode': plan.data['settings']['mode'], 'official_format': plan.data['settings']['mode'] == 'official',
            'scoring_policy': dict(SCORING_POLICY), 'matches': matches}
