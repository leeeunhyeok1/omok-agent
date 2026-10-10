# AI-written by OpenAI Codex, for issue #36.
"""Saved baseline artifacts at the agreed experiment output boundary."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from verification.optimizer_baseline import freeze, verify


class BaselineTests(unittest.TestCase):
    def test_frozen_incumbent_restores_exact_material_and_protects_holdout(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'baseline'
            record = freeze(output)
            restored = verify(output)
            self.assertEqual(restored['identity'], record['identity'])
            basis = record['basis']
            self.assertEqual(basis['incumbent']['loader']['commit'],
                             '105a8f64edaeb86082425c1fecb12932c06c4367')
            self.assertEqual(basis['resolved_player']['evaluator'], 'omok.search.material_evaluation')
            self.assertIsNone(basis['resolved_player']['evaluation'])
            self.assertEqual(basis['resolved_player']['config']['max_depth'], 8)
            self.assertEqual(basis['resolved_player']['config']['table_capacity'], 4096)
            self.assertEqual(basis['holdout_exposures'], [])
            self.assertEqual(basis['competitive_acceptance']['simple_strict_wins'], 0)
            self.assertEqual(basis['competitive_acceptance']['simple_games'], 8)
            self.assertEqual(restored['restoration'], 'exact')
            with self.assertRaises(FileExistsError):
                freeze(output)

    def test_changed_frozen_fixtures_are_rejected_before_restoration(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'baseline'
            freeze(output)
            (output / 'basis-inputs.tar.gz').write_bytes(b'changed tactical evidence')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                verify(output)


if __name__ == '__main__':
    unittest.main()
