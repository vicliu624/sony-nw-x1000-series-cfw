"""Source moves must preserve the audited implementation and SDK dependency seam."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import audit_sdk_adoption as adoption
from package_sdk import source_files
from sdk_services import manifest, service_files
from sdk_build import NATIVE


class SourceRelocationTests(unittest.TestCase):
    def test_device_info_keeps_immutable_original_logic(self):
        report = adoption.audit(check_logic=True, apps=['device-info'])
        self.assertTrue(report['passed'], report['errors'])
        self.assertEqual(report['apps'][0]['unchanged_application_logic_files'], 4)
        for original, current in adoption.source_relocations().items():
            if original.startswith('runtime/apps/device-info/'):
                self.assertIn(current, report['source_hashes'])

    def test_moved_code_change_is_still_rejected(self):
        target = ROOT / 'runtime/platform/system-info/device_info_data.c'
        read_text = Path.read_text

        def changed(path, *args, **kwargs):
            text = read_text(path, *args, **kwargs)
            if path == target:
                self.assertIn('if(!d)return -1;', text)
                return text.replace('if(!d)return -1;', 'if(!d)return 0;')
            return text

        with patch.object(Path, 'read_text', changed):
            report = adoption.audit(check_logic=True, apps=['device-info'])
        self.assertFalse(report['passed'])
        self.assertIn(target.relative_to(ROOT).as_posix() +
                      ': non-include application logic changed', report['errors'])

    def test_moved_include_change_is_still_rejected(self):
        target = ROOT / 'runtime/platform/system-info/device_info_space.c'
        read_text = Path.read_text

        def changed(path, *args, **kwargs):
            text = read_text(path, *args, **kwargs)
            if path == target:
                return text.replace('#include "device_info_data.h"', '#include <stdio.h>')
            return text

        with patch.object(Path, 'read_text', changed):
            report = adoption.audit(check_logic=True, apps=['device-info'])
        self.assertFalse(report['passed'])
        self.assertIn(target.relative_to(ROOT).as_posix() +
                      ': effective private/standard include order changed', report['errors'])

    def test_duplicate_and_missing_relocations_are_rejected(self):
        moves = adoption.source_relocations()
        duplicate = dict(moves)
        app = 'runtime/apps/device-info/'
        platform = 'runtime/platform/system-info/'
        duplicate[app + 'duplicate.c'] = next(iter(moves.values()))
        for invalid in (duplicate, {app + 'missing.c': platform + 'missing.c'}):
            with self.subTest(moves=invalid):
                with patch.dict(adoption.POLICY, {'source_relocations': invalid}):
                    with self.assertRaises(ValueError):
                        adoption.source_relocations()

    def test_shared_system_info_does_not_need_device_info_app(self):
        module = manifest()['system-info']
        self.assertTrue(all(name.startswith('runtime/platform/system-info/')
                            for name in service_files(['system-info'])))
        self.assertTrue(all(name.startswith('runtime/platform/system-info/')
                            for name in module['exports'].values()))
        exported = {path.relative_to(ROOT).as_posix() for path in source_files()}
        self.assertTrue(set(module['sources']).issubset(exported))
        for name in exported:
            if name.startswith('runtime/apps/device-info/'):
                self.assertEqual(Path(name).suffix, '.md')

    def test_shared_storage_keeps_immutable_original_logic(self):
        report = adoption.audit(check_logic=True, apps=['qqmusic', 'qqcheck'])
        self.assertTrue(report['passed'], report['errors'])
        for original, current in adoption.source_relocations().items():
            if original.startswith('runtime/apps/qqmusic/'):
                self.assertIn(current, report['source_hashes'])

    def test_callback_runtime_and_volume_do_not_import_apps(self):
        self.assertFalse(any(name.startswith('runtime/apps/') for name in NATIVE))
        module = manifest()['volume']
        self.assertTrue(all(name.startswith('runtime/platform/storage/')
                            for name in module['sources']))
        self.assertTrue(all(name.startswith('runtime/platform/storage/')
                            for name in module['exports'].values()))
        for name in ('runtime/platform/sdk/storage.c', *module['sources'],
                     *module['exports'].values()):
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertNotIn('/apps/', text)

    def test_shared_images_resolve_declared_codec_headers(self):
        module = manifest()['images']
        self.assertTrue(all(name.startswith('runtime/platform/images/')
                            for name in module['sources']))
        source = ROOT / module['sources'][0]
        includes = adoption.effective_includes(source, source.read_text(encoding='utf-8'))
        self.assertIn('third_party/qqmusic-stb/stb_image.h', includes)
        self.assertIn('third_party/qqmusic-stb/stb_image_write.h', includes)
        self.assertFalse(any(name.startswith('runtime/apps/') for name in includes))

    def test_moved_decoder_cannot_silently_change_header(self):
        source = ROOT / 'runtime/platform/images/qqmusic_image.c'
        current = source.read_text(encoding='utf-8')
        changed = current.replace('#include "stb_image_write.h"', '#include "stb_image.h"')
        self.assertNotEqual(adoption.effective_includes(source, current),
                            adoption.effective_includes(source, changed))


if __name__ == '__main__':
    unittest.main()
