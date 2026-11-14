"""Reject misleading capacity and metadata results before reporting a margin."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from measure_layout_ext2 import IMAGE_BYTES, populate, quote, superblock_stats, validate_tree, verify_inode


def superblock():
    raw = bytearray(1024)
    struct.pack_into('<5I', raw, 0, 37888, 37888, 1894, 7000, 36440)
    struct.pack_into('<I', raw, 24, 2)
    struct.pack_into('<H', raw, 56, 0xef53)
    struct.pack_into('<H', raw, 88, 128)
    struct.pack_into('<3I', raw, 92, 0, 2, 1)
    return raw


def directory():
    return dict(kind='directory', mode=0o755, uid=500, gid=500, bytes=0)


INODE = '''Inode: 17   Type: symlink    Mode:  0777   Flags: 0x0
User: 500   Group: 500   Size: 13
mtime: 0x499602d2 -- ignored display text
Fast link dest: "libc-2.3.3.so"
'''
LINK = dict(kind='symlink', mode=0o777, uid=500, gid=500, bytes=0, target='libc-2.3.3.so')


class CapacityAccountingTests(unittest.TestCase):
    def test_reserved_blocks_are_excluded_from_reported_margin(self):
        result = superblock_stats(superblock(), IMAGE_BYTES)
        self.assertEqual(result['available_nonreserved_bytes'], (7000 - 1894) * 4096)
        self.assertEqual(result['used_bytes'], (37888 - 7000) * 4096)
        self.assertEqual(result['used_inodes'], 1448)

    def test_exhaustion_is_not_clamped_into_success(self):
        raw = superblock()
        struct.pack_into('<I', raw, 12, 1893)
        with self.assertRaisesRegex(ValueError, 'accounting'):
            superblock_stats(raw, IMAGE_BYTES)

    def test_wrong_geometry_or_features_cannot_reuse_stock_claim(self):
        for offset, value, size in ((24, 0, 'I'), (88, 256, 'H'), (92, 4, 'I'), (56, 0, 'H')):
            raw = superblock()
            struct.pack_into('<' + size, raw, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                superblock_stats(raw, IMAGE_BYTES)
        with self.assertRaises(ValueError):
            superblock_stats(superblock(), IMAGE_BYTES + 4096)
        with self.assertRaises(ValueError):
            superblock_stats(bytes(20), IMAGE_BYTES)

    def test_impossible_free_counts_are_refused(self):
        for offset in (12, 16):
            raw = superblock()
            struct.pack_into('<I', raw, offset, 37889)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                superblock_stats(raw, IMAGE_BYTES)


class PopulationBoundaryTests(unittest.TestCase):
    def test_failed_population_removes_partial_image_and_keeps_log(self):
        with tempfile.TemporaryDirectory() as folder:
            area = Path(folder)

            def fail_formatter(command, log):
                self.assertTrue(Path(command[-1]).is_file())
                log.write_text('formatter failed\n', encoding='utf-8')
                raise ValueError('formatter failed')

            with patch('measure_layout_ext2.run', side_effect=fail_formatter):
                with self.assertRaisesRegex(ValueError, 'formatter failed'):
                    populate(area, 'stock', {}, {}, {}, None, area)
            self.assertEqual([path.name for path in area.iterdir()], ['stock-mkfs.log'])

    def test_parent_link_cannot_redirect_population(self):
        rows = {'usr': LINK, 'usr/app': dict(kind='file')}
        with self.assertRaisesRegex(ValueError, 'ancestor'):
            validate_tree(rows)

    def test_missing_parents_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'ancestor'):
            validate_tree({'usr/local': directory()})

    def test_traversal_and_debugfs_command_injection_are_refused(self):
        for name in ('../bad', '/bad', 'usr/../bad', 'usr//bad', 'usr\\bad', 'bad\nmkdir /extra'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_tree({name: directory()})
        for argument in ('"', '\\', '\n', '\r', '\0'):
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                quote(argument)

    def test_unverified_link_encoding_is_refused(self):
        for target in ('', 'x' * 60):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'symlink'):
                validate_tree({'link': dict(LINK, target=target)})

    def test_unsupported_special_files_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            validate_tree({'device': dict(kind='other')})

    def test_actual_inode_metadata_and_fast_link_are_checked(self):
        verify_inode(INODE, 'link', LINK, 1234567890)
        for before, after in (('Type: symlink', 'Type: regular'), ('0777', '0755'),
                              ('User: 500', 'User: 0'), ('Group: 500', 'Group: 0'),
                              ('0x499602d2', '0x499602d3'), ('libc-2.3.3.so', 'wrong.so')):
            with self.subTest(field=before), self.assertRaises(ValueError):
                verify_inode(INODE.replace(before, after), 'link', LINK, 1234567890)

    def test_regular_file_size_is_not_inferred_from_dump_alone(self):
        text = INODE.replace('Type: symlink', 'Type: regular')
        row = dict(kind='file', mode=0o777, uid=500, gid=500, bytes=14)
        with self.assertRaisesRegex(ValueError, 'size'):
            verify_inode(text, 'file', row, 1234567890)


if __name__ == '__main__':
    unittest.main()
