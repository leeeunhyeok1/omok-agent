# AI-written by OpenAI Codex, for issue #16.
"""Inspect a saved evaluator against an explicit board/context JSON file."""
import argparse
import json
from pathlib import Path

from omok.evaluation import ConfiguredEvaluator, EvaluationConfig
from omok.simulator import Position


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--position', required=True, type=Path,
                        help='JSON object with board and side_to_move')
    args = parser.parse_args()
    evaluator = ConfiguredEvaluator(EvaluationConfig.load(args.config))
    data = json.loads(args.position.read_text(encoding='utf-8'))
    position = Position(data['board'], data['side_to_move'])
    print(json.dumps(evaluator.inspect(position), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
