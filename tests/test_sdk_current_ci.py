"""Current CI must preserve existing private inputs and distinguish historical checks."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from textwrap import dedent
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

    @unittest.skipUnless(os.name == 'posix', 'The CI scope runs in Bash on Linux')
    def test_application_scope_skips_independent_probes_and_keeps_build_inputs(self):
        def scope_command(name):
            workflow = (ROOT / '.github/workflows' / name).read_text(encoding='utf-8')
            step = workflow.split('\n        id: scope\n', 1)[1].split('\n      - ', 1)[0]
            return dedent(step.split('\n        run: |\n', 1)[1])

        app_scope = scope_command('sdk-apps.yml')
        host_scope = scope_command('ci.yml')
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            repo = workspace / 'repo'
            repo.mkdir()
            output = workspace / 'github-output'

            def git(*args):
                return subprocess.check_output(
                    ['git', '-c', 'user.email=ci@example.invalid', '-c', 'user.name=CI',
                     '-c', 'commit.gpgsign=false', *args], cwd=repo, text=True)

            def selected(scope, base, event='push', ref='refs/heads/main'):
                output.unlink(missing_ok=True)
                env = dict(os.environ, BASE_SHA=base, GITHUB_EVENT_NAME=event, GITHUB_REF=ref,
                           GITHUB_OUTPUT=str(output))
                subprocess.run(['bash', '-e', '-c', scope], cwd=repo, env=env, capture_output=True, check=True)
                return dict(line.split('=', 1) for line in output.read_text().splitlines())

            git('init', '--quiet')
            pathspec = Path('config/ci-offline-tool-pathspecs.txt')
            (repo / pathspec.parent).mkdir()
            (repo / pathspec).write_bytes((ROOT / pathspec).read_bytes())
            git('add', '--', str(pathspec))
            git('commit', '--quiet', '-m', 'base')
            cases = [
                ('docs/WORKFLOW.md', 'false', 'false', 'false'),
                ('tools/check_home_parent.py', 'false', 'true', 'false'),
                ('tools/test_store_fs_faults.py', 'false', 'true', 'false'),
                ('tools/native_app_build.py', 'true', 'true', 'true'),
                ('runtime/apps/store/build.py', 'true', 'true', 'true'),
                ('docs/apps/STORE.md', 'true', 'false', 'false'),
                ('tools/test_fm_storage.py', 'true', 'true', 'true'),
                ('tools/test_sdk_text.py', 'true', 'true', 'true'),
            ]
            for name, needed, host, compiled_host in cases:
                with self.subTest(path=name):
                    base = git('rev-parse', 'HEAD').strip()
                    path = repo / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('changed\n')
                    git('add', '--', name)
                    git('commit', '--quiet', '-m', name)
                    self.assertEqual(selected(app_scope, base), dict(needed=needed))
                    self.assertEqual(selected(host_scope, base), dict(host=host, compiled_host=compiled_host))
            head = git('rev-parse', 'HEAD').strip()
            self.assertEqual(selected(app_scope, head, 'workflow_dispatch'), dict(needed='true'))
            self.assertEqual(selected(app_scope, '0' * 40), dict(needed='true'))
            self.assertEqual(selected(host_scope, head, ref='refs/tags/v1'),
                             dict(host='true', compiled_host='true'))


if __name__ == '__main__':
    unittest.main()
