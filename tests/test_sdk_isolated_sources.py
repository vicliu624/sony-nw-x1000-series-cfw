"""SDK test projects stay outside the maintained app catalog, including failures."""
from pathlib import Path
import ast
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from app_registry import application_root, applications
from sdk import create


class IsolatedSourcesTests(unittest.TestCase):
    def test_generated_fixture_does_not_change_formal_catalog(self):
        before = applications()
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as directory:
            root = Path(directory) / 'sources'
            project = create('isolated-check', 'minimal', 'Isolated Check', root)
            self.assertEqual(project, root / 'isolated-check')
            self.assertIn('isolated-check', applications(root))
            self.assertEqual(applications(), before)
            recipe = ast.parse((project / 'build.py').read_text())
            insertion = recipe.body[2].value
            self.assertEqual(ast.literal_eval(insertion.args[1]), str(ROOT / 'tools'))
            guide = (project / 'README.md').read_text().split('](', 1)[1].split(')', 1)[0]
            self.assertEqual((project / guide).resolve(), ROOT / 'docs/sdk/README.md')
            self.assertIn('--apps-root', (project / 'README.md').read_text())

    def test_mid_scaffold_failure_leaves_only_work_evidence(self):
        before = applications()
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as directory:
            root = Path(directory) / 'sources'
            write = Path.write_text

            def fail_recipe(path, *args, **kwargs):
                if path.name == 'build.json':
                    raise OSError('Injected recipe write failure')
                return write(path, *args, **kwargs)

            with patch.object(Path, 'write_text', fail_recipe), self.assertRaises(OSError):
                create('failed-check', 'minimal', app_root=root)
            self.assertTrue((root / 'failed-check/main.c').exists())
            self.assertEqual(applications(), before)

    def test_explicit_root_has_no_formal_tree_fallback(self):
        for root in (ROOT / 'runtime/apps', ROOT / 'work', ROOT / 'work/../runtime/apps'):
            with self.subTest(root=root), self.assertRaises(ValueError):
                application_root(root)


if __name__ == '__main__':
    unittest.main()
