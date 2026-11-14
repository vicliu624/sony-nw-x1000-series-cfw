"""A composed-image check must not silently rebuild a different profile."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/test_player_host_anchor.py'


class ComposedAnchorCommandTests(unittest.TestCase):
    def rejected(self, arguments, message):
        result = subprocess.run([sys.executable, str(SCRIPT), *arguments], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_composed_review_requires_the_engine_binding_profile(self):
        self.rejected(['--host-review', 'work/not-an-input.json'],
                      '--host-review requires --engine-provider')

    def test_callback_profiles_cannot_be_claimed_by_the_core_binding_check(self):
        for flag in ('--native-prepare', '--native-settings', '--native-wireless-settings',
                     '--native-rf-gate', '--native-sleep-analysis', '--sleep-routing-only',
                     '--cold-routing-only'):
            with self.subTest(flag=flag):
                self.rejected(['--host-review', 'work/not-an-input.json', '--engine-provider', flag],
                              'selects only core owner/engine binding cases')

    def test_unknown_option_is_not_ignored(self):
        self.rejected(['--native-remtoe-settings'], 'unrecognized arguments')


if __name__ == '__main__':
    unittest.main()
