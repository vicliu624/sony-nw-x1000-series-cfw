"""Source moves must preserve the audited implementation and SDK dependency seam."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import audit_sdk_adoption as adoption
from package_sdk import source_files
from sdk_services import manifest
from sdk_build import NATIVE


class SourceRelocationTests(unittest.TestCase):
    def test_device_info_keeps_immutable_original_logic(self):
        report = adoption.audit(check_logic=True, apps=['device-info'])
        self.assertTrue(report['passed'], report['errors'])
        self.assertEqual(report['apps'][0]['unchanged_application_logic_files'], 4)
        for name in ('device_info_data.c', 'device_info_data.h', 'device_info_space.c'):
            self.assertIn(f'runtime/apps/device-info/{name}', report['source_hashes'])

    def test_application_logic_change_is_rejected(self):
        target = ROOT / 'runtime/apps/device-info/device_info_data.c'
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

    def test_application_include_change_is_rejected(self):
        target = ROOT / 'runtime/apps/device-info/device_info_space.c'
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
        app = 'runtime/apps/qqmusic/'
        platform = 'runtime/platform/storage/'
        duplicate[app + 'duplicate.c'] = next(iter(moves.values()))
        for invalid in (duplicate, {app + 'missing.c': platform + 'missing.c'}):
            with self.subTest(moves=invalid):
                with patch.dict(adoption.POLICY, {'source_relocations': invalid}):
                    with self.assertRaises(ValueError):
                        adoption.source_relocations()

    def test_device_info_pages_are_private_app_sources(self):
        self.assertNotIn('system-info', manifest())
        app = ROOT / 'runtime/apps/device-info'
        private_sources = {app / name for name in ('device_info_data.c', 'device_info_data.h', 'device_info_space.c')}
        self.assertTrue(all(path.is_file() for path in private_sources))
        self.assertTrue(private_sources.isdisjoint(source_files()))

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

    def test_qqmusic_decoders_are_private_app_sources(self):
        self.assertNotIn('images', manifest())
        app = ROOT / 'runtime/apps/qqmusic'
        private_sources = {app / name for name in ('qqmusic_image.c', 'qqmusic_image.h', 'qqmusic_picture.c')}
        self.assertTrue(all(path.is_file() for path in private_sources))
        self.assertTrue(private_sources.isdisjoint(source_files()))
        source = app / 'qqmusic_image.c'
        includes = adoption.effective_includes(source, source.read_text(encoding='utf-8'))
        self.assertIn('third_party/qqmusic-stb/stb_image.h', includes)
        self.assertIn('third_party/qqmusic-stb/stb_image_write.h', includes)

    def test_qqmusic_decoder_cannot_silently_change_header(self):
        source = ROOT / 'runtime/apps/qqmusic/qqmusic_image.c'
        current = source.read_text(encoding='utf-8')
        changed = current.replace('#include "stb_image_write.h"', '#include "stb_image.h"')
        self.assertNotEqual(adoption.effective_includes(source, current),
                            adoption.effective_includes(source, changed))


if __name__ == '__main__':
    unittest.main()
