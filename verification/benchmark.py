# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #3.
"""Small repeatable transition benchmark; excludes setup and reference checks."""
import json
import platform
import timeit

from omok.simulator import Position


def main() -> None:
    capture = [[-1] * 19 for _ in range(19)]
    capture[9][10] = capture[9][11] = 1
    capture[9][12] = 0
    dense = [[(r + 2 * c) % 4 // 2 for c in range(19)] for r in range(19)]
    dense[0][0] = -1
    fixtures = [('empty', Position.empty(), (9, 9)),
                ('capture', Position(capture, 0), (9, 9)),
                ('dense_capture', Position(dense, 0), (0, 0))]
    timings = []
    for name, position, move in fixtures:
        seconds = min(timeit.repeat(lambda: position.play(move), repeat=3, number=1000))
        timings.append({'fixture': name, 'transitions': 1000, 'best_seconds': seconds,
                        'transitions_per_second': 1000 / seconds})
    print(json.dumps({'python': platform.python_version(), 'platform': platform.platform(),
                      'processor': platform.processor(), 'workers': 1,
                      'timings': timings}, indent=2))


if __name__ == '__main__':
    main()
