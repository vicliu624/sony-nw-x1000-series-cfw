"""Current CI must preserve existing private inputs and distinguish historical checks."""

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import test_sdk_app_equivalence as driver


class CurrentSDKCITests(unittest.TestCase):
    def test_existing_identity_is_refused_before_any_generation(self):
        parent = ROOT / 'work/sdk-current-ci-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            root = Path(directory)
            identity = root / 'work/terminal-review/private-identity'
            identity.mkdir(parents=True)
            key = identity / 'server-key.pem'
            key.write_bytes(b'preserve existing local input')
            with patch.object(driver, 'ROOT', root), \
                 patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), \
                 patch.object(sys, 'argv', ['driver', '--current']), \
                 patch.object(driver.subprocess, 'check_output', return_value=b''), \
                 patch.object(driver.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'existing identities/artwork are preserved'):
                    driver.main()
                run.assert_not_called()
            self.assertEqual(key.read_bytes(), b'preserve existing local input')

    def test_routine_ci_selects_current_packages_and_semantic_tests(self):
        workflow = (ROOT / '.github/workflows/sdk-apps.yml').read_text(encoding='utf-8')
        self.assertIn('tools/test_sdk_app_equivalence.py --current', workflow)
        self.assertNotIn('tools/audit_sdk_adoption.py --check-logic', workflow)
        self.assertNotIn('tools/build_hello_app.py', workflow)
        for ident in ('dictionary', 'ebook'):
            self.assertIn(f'tools/test_{ident}_app.py --package "$APP_CHECK_ROOT/current/packages/{ident}"', workflow)
        for test in ('test_sdk_text.py', 'test_dictionary_app.py',
                     'test_ebook_app.py', 'test_ebook_epub.py'):
            self.assertIn('python tools/' + test, workflow)


if __name__ == '__main__':
    unittest.main()
