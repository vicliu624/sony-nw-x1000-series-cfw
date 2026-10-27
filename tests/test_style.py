import struct
import unittest
from scripts.style import parse_style, TABLE_BYTES, RECORD_BYTES


class StyleTests(unittest.TestCase):
    def fixture(self):
        data = bytearray(TABLE_BYTES)
        struct.pack_into('<II', data, 0, 2, 1)
        struct.pack_into('<I', data, 8, 1)
        struct.pack_into('<6I', data, 36, 14, 0xFFFFFFFF, 20, 0, 240, 432)
        return data

    def test_controls_and_opaque_fields(self):
        data = self.fixture()
        struct.pack_into('<I', data, 36 + 40 * 4, 0x12345678)
        layouts = parse_style(data)
        self.assertEqual(len(layouts), 2)
        self.assertEqual(layouts[0].children[0].kind, 14)
        self.assertEqual(layouts[0].children[0].geometry, (-1, 20, 0, 240, 432))
        self.assertEqual(layouts[0].children[0].words[40], 0x12345678)
        self.assertEqual(layouts[1].children, ())

    def test_reject_truncation_and_trailing_data(self):
        for data in [self.fixture()[:-1], self.fixture() + b'\0']:
            with self.assertRaises(ValueError):
                parse_style(data)

    def test_reject_unsupported_header(self):
        for count, flag in [(205, 1), (2, 0), (2, 2)]:
            data = self.fixture()
            struct.pack_into('<II', data, 0, count, flag)
            with self.assertRaises(ValueError):
                parse_style(data)

    def test_reject_child_overflow_in_later_layout(self):
        data = self.fixture()
        struct.pack_into('<I', data, 8 + RECORD_BYTES, 33)
        with self.assertRaises(ValueError):
            parse_style(data)
