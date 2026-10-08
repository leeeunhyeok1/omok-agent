# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #3.
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from omok.simulator import Position
from verification.differential import checked_move, run_sequences
from verification.reference import ReferencePosition


class DifferentialTests(unittest.TestCase):
    def test_seeded_ordinary_and_capture_biased_legal_sequences(self):
        with TemporaryDirectory() as directory:
            report = run_sequences(2, 100, 20261008, Path(directory))
            self.assertEqual(len(report['records']), 4)
            self.assertGreater(report['checked_transitions'], 100)
            self.assertGreater(sum(record['captured_stones'] for record in report['records']
                                   if record['mode'] == 'capture_biased'), 0)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_mismatch_preserves_seed_and_replayable_move_sequence(self):
        with TemporaryDirectory() as directory:
            position = Position.empty()
            reference = ReferencePosition.empty().play((0, 0)).position
            with self.assertRaisesRegex(AssertionError, 'Differential failure'):
                checked_move(position, reference, (1, 0), 123, 'ordinary', [], Path(directory))
            record = json.loads((Path(directory) / 'mismatch-ordinary-123.json').read_text())
            self.assertEqual(record['seed'], 123)
            self.assertEqual(record['moves'], [[1, 0]])
            self.assertEqual(record['initial_side'], 0)
            self.assertEqual(record['initial_board'], [[-1] * 19 for _ in range(19)])
