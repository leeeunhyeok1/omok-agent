# AI-written by OpenAI Codex, for issue #23.
"""Restore pinned engines in temporary directories and exercise public boundaries."""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PHASE2 = '798963cae696eead8353232d1cc8c289cce473a9'
PHASE3 = '105a8f64edaeb86082425c1fecb12932c06c4367'


def probe(root: Path, phase: str) -> dict[str, Any]:
    # The isolated subprocess cannot import the live checkout's omok package.
    sys.path.insert(0, str(root.resolve()))
    from omok import player as player_module
    from omok.player import IterativePlayer
    from omok.search import FixedDepthSearch, material_evaluation
    from omok.simulator import Position
    if not Path(player_module.__file__).resolve().is_relative_to(root.resolve()):
        raise AssertionError('Probe imported an engine outside its restored checkpoint.')
    board = [list(row) for row in Position.empty().board]
    board[9][9] = 0
    if material_evaluation(Position(board, 0)) != 1:
        raise AssertionError('Retained material evaluator changed.')
    result: dict[str, Any] = {'engine_import': 'restored omok/player.py', 'material_score': 1}
    if phase == 'phase2':
        for color in (0, 1):
            supplied_board = [row[:] for row in board]
            move = IterativePlayer(color).take_turn(supplied_board, 0)
            Position(board, color).play(move)
            if supplied_board != board:
                raise AssertionError('Restored public player mutated its input.')
        return result | {'both_color_legal_moves': True, 'input_unchanged': True}

    from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
    configs = []
    for path in sorted((root / 'configs').glob('*.json')):
        config = EvaluationConfig.load(path)
        config.save(root / 'reloaded.json')
        reloaded = EvaluationConfig.load(root / 'reloaded.json')
        if config.identity != reloaded.identity or config.canonical_json() != reloaded.canonical_json():
            raise AssertionError('Configuration round-trip changed identity.')
        inspection = ConfiguredEvaluator(reloaded).inspect(Position.empty())
        if inspection['incomplete'] or inspection['configuration_id'] != config.identity:
            raise AssertionError('Restored configuration inspection failed.')
        configs.append({'path': 'configs/' + path.name, 'identity': config.identity,
                        'configuration': config.canonical_json(), 'empty_score': inspection['total']})
    complete = EvaluationConfig.load(root / 'configs/effects-v1.json')
    board = [list(row) for row in Position.empty().board]
    board[9][6:10] = [0] * 4
    initial = Position(board, 0)
    inspection = ConfiguredEvaluator(complete).inspect(initial)
    if inspection['features']['open_four'] != 1 or inspection['features']['verified_win'] != 2:
        raise AssertionError('Restored feature meanings changed.')
    agents = [IterativePlayer(color, evaluation_config=complete) for color in (0, 1)]
    for agent in agents:
        supplied_board = [row[:] for row in board]
        move = agent.take_turn(supplied_board, 0)
        Position(board, agent.color).play(move)
        if supplied_board != board:
            raise AssertionError('Restored public player mutated its input.')
    agents[0].set_evaluation_config(EvaluationConfig(material=2))
    if agents[0].search is agents[1].search or agents[0].search.table is agents[1].search.table:
        raise AssertionError('Restored agents share mutable search state.')
    white = agents[1].take_turn([row[:] for row in board], 0)
    Position(board, 1).play(white)
    diagnostics = agents[1].diagnostics()
    if diagnostics is None or diagnostics['evaluation']['configuration_id'] != complete.identity:
        raise AssertionError('Changing one agent leaked into the other.')
    terminal = initial.play((9, 5)).position
    score = FixedDepthSearch(evaluation_config=complete).search(terminal, 2).score
    if score != 10000:
        raise AssertionError('Terminal precedence changed.')
    return result | {'configurations': configs, 'features': inspection['features'],
                     'inspection': inspection, 'terminal_score': score,
                     'agent_isolation': True, 'input_unchanged': True,
                     'both_color_legal_moves': True,
                     'scope': 'zero-clock public fallback/isolation; tactical strength tested separately'}


def restore(ref: str, phase: str) -> dict[str, Any]:
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', ref + '^{commit}'],
                                     cwd=ROOT, text=True).strip()
    paths = ['omok', 'players'] + (['configs'] if phase == 'phase3' else [])
    archive = subprocess.check_output(['git', 'archive', commit, *paths], cwd=ROOT)
    with TemporaryDirectory(prefix='omok-checkpoint-') as directory:
        root = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(root, filter='data')
        hashes = {str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
                  for path in sorted(root.rglob('*')) if path.is_file()}
        command = [sys.executable, '-I', '-S', '-B', str(Path(__file__).resolve()),
                   '--probe', str(root), '--phase', phase]
        process = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=30)
        if process.returncode:
            raise RuntimeError('Restored checkpoint probe failed: ' + process.stderr)
        return {'commit': commit, 'archive_sha256': sha256(archive).hexdigest(),
                'restored_source_sha256': hashes, 'isolated': True, 'no_site': True,
                'probe': json.loads(process.stdout)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.scratch/issue-23-restoration.json'))
    parser.add_argument('--phase3-ref', default=PHASE3)
    parser.add_argument('--probe', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--phase', choices=('phase2', 'phase3'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(probe(args.probe, args.phase), allow_nan=False))
        return
    report: dict[str, Any] = {'format': 'omok-checkpoint-verification-v1', 'python': platform.python_version(),
              'platform': platform.platform(), 'phase2': restore(PHASE2, 'phase2'),
              'phase3': restore(args.phase3_ref, 'phase3')}
    for name in ('player.py', 'randomplayer.py', 'simpleplayer.py'):
        if report['phase2']['restored_source_sha256']['players/' + name] != report[
                'phase3']['restored_source_sha256']['players/' + name]:
            raise AssertionError('Supplied source changed between checkpoints: ' + name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'phase2': report['phase2']['commit'], 'phase3': report['phase3']['commit'],
                      'restoration': 'verified', 'output': str(args.output)}))


if __name__ == '__main__':
    main()
