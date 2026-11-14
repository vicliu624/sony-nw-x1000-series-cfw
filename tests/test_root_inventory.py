"""A reviewed root must include the parent directories the packer creates."""
from pathlib import Path
import copy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from review_managed_root_capacity import compose_root_inventory


def directory(mode=0o755, uid=0, gid=0):
    return dict(kind='directory', bytes=0, mode=mode, uid=uid, gid=gid)


def file_entry(uid=4, gid=5):
    return dict(kind='file', bytes=7, mode=0o600, uid=uid, gid=gid, sha256='old')


def replacement():
    return dict(bytes=9, mode='0o755', uid=8, gid=9, sha256='new')


class RootInventoryTests(unittest.TestCase):
    def test_implicit_parents_are_reviewed(self):
        result = compose_root_inventory({'usr': directory()}, {'usr/local/libexec/owner': replacement()})
        self.assertEqual(result['usr/local'], directory())
        self.assertEqual(result['usr/local/libexec'], directory())
        self.assertEqual(result['usr/local/libexec/owner']['uid'], 8)

    def test_existing_file_ownership_is_preserved(self):
        base = {'usr': directory(), 'usr/app': file_entry()}
        result = compose_root_inventory(base, {'usr/app': replacement()})
        self.assertEqual((result['usr/app']['uid'], result['usr/app']['gid']), (4, 5))
        self.assertEqual((result['usr/app']['mode'], result['usr/app']['bytes']), (0o755, 9))

    def test_existing_parent_metadata_is_preserved(self):
        base = {'usr': directory(), 'usr/local': directory(0o711, 2, 3)}
        result = compose_root_inventory(base, {'usr/local/app': replacement()})
        self.assertEqual(result['usr/local'], base['usr/local'])

    def test_symlink_ancestor_is_refused(self):
        base = {'usr': dict(kind='symlink', bytes=0, mode=0o777, uid=0, gid=0, target='/contents')}
        with self.assertRaises(ValueError):
            compose_root_inventory(base, {'usr/app': replacement()})

    def test_file_ancestor_is_refused(self):
        with self.assertRaises(ValueError):
            compose_root_inventory({'usr': file_entry()}, {'usr/app': replacement()})

    def test_non_file_destination_is_refused(self):
        with self.assertRaises(ValueError):
            compose_root_inventory({'usr': directory()}, {'usr': replacement()})

    def test_noncanonical_overlay_paths_are_refused(self):
        for name in ('', '.', '..', '../app', '/app', 'usr//app', 'usr/../app', 'usr\\app'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                compose_root_inventory({}, {name: replacement()})

    def test_inputs_remain_unchanged(self):
        base = {'usr': directory()}
        overlay = {'usr/app': replacement()}
        expected = copy.deepcopy((base, overlay))
        compose_root_inventory(base, overlay)
        self.assertEqual((base, overlay), expected)


if __name__ == '__main__':
    unittest.main()
