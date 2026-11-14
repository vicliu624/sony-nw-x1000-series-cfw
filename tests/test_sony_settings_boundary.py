"""Private stock UI adapters stay outside apps and outside the public SDK."""
from pathlib import Path
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_sdk import source_files


class SonySettingsBoundaryTests(unittest.TestCase):
    def test_private_adapters_do_not_import_application_implementation(self):
        module = ROOT / 'runtime/platform/sony-settings'
        files = sorted([*module.glob('*.c'), *module.glob('*.h')])
        self.assertGreaterEqual(len(files), 7)
        for path in files:
            text = path.read_text(encoding='utf-8')
            for include in re.findall(r'#include\s+"([^"\n]+)"', text):
                target = (path.parent / include).resolve()
                self.assertTrue(target.is_file(), (path, include))
                self.assertTrue(target.is_relative_to(ROOT / 'runtime/platform'), (path, target))
        for name in ('native_page.c', 'native_page.h', 'native_page_entry.c',
                     'native_choice_view.c', 'native_choice_view.h', 'native_settings.c'):
            self.assertFalse((ROOT / 'runtime/apps/wireless-remote' / name).exists())

    def test_private_bindings_are_not_published_as_sdk_services(self):
        exported = {p.relative_to(ROOT).as_posix() for p in source_files()}
        self.assertFalse([p for p in exported if p.startswith('runtime/platform/sony-settings/')])
        services = (ROOT / 'sdk/services.json').read_text(encoding='utf-8')
        self.assertNotIn('sony-settings', services)


if __name__ == '__main__':
    unittest.main()
