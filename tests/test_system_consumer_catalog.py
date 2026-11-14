"""Settings-managed remote services must not masquerade as installable SDK apps."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from app_registry import ROOT, applications
from sdk import create


class SystemConsumerCatalogTests(unittest.TestCase):
    def test_only_foreground_apps_are_discovered(self):
        catalog = applications()
        self.assertNotIn('wireless-remote', catalog)
        self.assertIn('hello', catalog)
        published = json.loads((ROOT / 'config/release.json').read_text(encoding='utf-8'))
        self.assertTrue(set(published['apps']).issubset(catalog))

    def test_sdk_new_preserves_existing_consumer_sources(self):
        component = ROOT / 'runtime/apps/wireless-remote'
        paths = [component / name for name in ('service.c', 'worker.c', 'VERSION')]
        before = {path: hashlib.sha256(path.read_bytes()).digest() for path in paths}
        with self.assertRaisesRegex(ValueError, 'already exists'):
            create('wireless-remote', 'minimal')
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).digest() for path in paths})
        self.assertFalse((component / 'app.json').exists())


if __name__ == '__main__':
    unittest.main()
