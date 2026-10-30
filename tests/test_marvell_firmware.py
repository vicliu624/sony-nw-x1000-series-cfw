"""Synthetic container tests; no Sony binary or device is needed."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from marvell_firmware import Record, crc32, parse, serialize


class FirmwareTests(unittest.TestCase):
    def setUp(self):
        self.records = [Record(1, 0xc0001000, b'example payload'), Record(4, 0, b'')]

    def test_crc_vector(self):
        self.assertEqual(crc32(b'123456789'), 0x89A1897F)

    def test_roundtrip(self):
        self.assertEqual(parse(serialize(self.records)), self.records)

    def test_corruptions(self):
        source = serialize(self.records)
        for position in (0, 12, 16, 16 + len(self.records[0].data)):
            with self.subTest(position=position):
                damaged = bytearray(source)
                damaged[position] ^= 1
                with self.assertRaises(ValueError):
                    parse(bytes(damaged))

    def test_incomplete_or_trailing(self):
        source = serialize(self.records)
        for blob in (b'', source[:-1], source + b'x', source[:-16]):
            with self.assertRaises(ValueError):
                parse(blob)

    def test_wrap_or_oversize(self):
        for record in (Record(1, 0xffffffff, b'ab'), Record(1, 0, bytes(509))):
            with self.assertRaises(ValueError):
                serialize([record, Record(4, 0, b'')])


if __name__ == '__main__':
    unittest.main()
