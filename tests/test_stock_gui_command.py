"""Reject command lines that previously passed with no GUI cases executed."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/test_stock_gui_host.py'


class StockGuiCommandTests(unittest.TestCase):
    def rejected(self, arguments, message):
        result = subprocess.run([sys.executable, str(SCRIPT), *arguments], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_conflicting_subsets_cannot_produce_an_empty_pass(self):
        self.rejected(['--engine-provider', '--direct-only'], 'not allowed with argument')

    def test_unknown_profile_does_not_run_a_different_matrix(self):
        self.rejected(['--engine-providre'], 'unrecognized arguments')


if __name__ == '__main__':
    unittest.main()
