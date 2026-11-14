"""Native process composition must not import another executable's source."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from owner_native_profile import render


class NativeEntryTests(unittest.TestCase):
    def test_entry_include_closure_has_no_executable_or_other_app(self):
        for entry in ('runtime/apps/wireless-remote/rf_owner.c', 'runtime/apps/espnow-test/main.c'):
            pending = [ROOT / entry]
            seen = set()
            while pending:
                path = pending.pop().resolve()
                if path in seen:
                    continue
                seen.add(path)
                for name in re.findall(r'#include\s+"([^"\n]+)"', path.read_text(encoding='utf-8')):
                    self.assertFalse(name.endswith('.c'), (entry, path, name))
                    included = (path.parent / name).resolve()
                    if included.is_file():
                        pending.append(included)
            self.assertTrue(any(p.name == 'native_environment.h' for p in seen))
            if 'wireless-remote' in entry:
                self.assertFalse(any(p.is_relative_to(ROOT / 'runtime/apps/espnow-test') for p in seen))

    def test_private_adapter_is_not_an_sdk_service(self):
        from sdk_services import inputs, manifest, resolve
        paths = inputs({'resolved_modules': resolve(list(manifest()))})
        self.assertNotIn(ROOT / 'runtime/platform/espnow/native_environment.c', paths)
        self.assertNotIn(ROOT / 'runtime/platform/espnow/native_entry.h', paths)


class NativeManifestTests(unittest.TestCase):
    stock = ('struct stock_input {const char *path;unsigned bytes;unsigned char sha[32];};\n'
             'static const struct stock_input stock_inputs[]={{"/stock",7,{1}}};\n'
             'struct stock_link {const char *path,*target;};\n'
             'static const struct stock_link stock_links[]={{"/link","stock"}};\n')
    candidate = 'static const struct stock_input exchange_inputs[]={{"/user",9,{2}}};\n'

    def test_composes_values_without_embedded_type_definitions(self):
        text = render(self.stock, self.candidate)
        self.assertIn('static const struct xnow_native_file stock_inputs[]={{"/stock",7,{1}}};', text)
        self.assertIn('static const struct xnow_native_link stock_links[]={{"/link","stock"}};', text)
        self.assertIn('static const struct xnow_native_file exchange_inputs[]={{"/user",9,{2}}};', text)
        self.assertNotIn('struct stock_', text)

    def test_refuses_changed_or_duplicate_type_declaration(self):
        for stock in (self.stock.replace('unsigned bytes;', 'unsigned long bytes;'), self.stock + self.stock):
            with self.assertRaises(ValueError):
                render(stock, self.candidate)

    def test_refuses_missing_or_ambiguous_input_tables(self):
        for candidate in ('', self.candidate + self.candidate):
            with self.assertRaises(ValueError):
                render(self.stock, candidate)


if __name__ == '__main__':
    unittest.main()
