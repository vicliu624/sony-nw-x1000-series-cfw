"""A guest control receipt must not impersonate native USB completion."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from stock_usb_input import FRAME_BYTES, command, receipt


class StockUsbInputTests(unittest.TestCase):
    def test_correlated_receipt_is_only_input_acceptance(self):
        self.assertEqual(command(4, 17), b'XWU2\x04\0\0\0\x11\0\0\0')
        result = receipt(struct.pack('<4sI4B', b'XWA2', 17, 4, 0, 1, 1), 17)
        self.assertTrue(result['input_accepted'])
        self.assertFalse(result['handoff_acknowledged'])
        self.assertEqual(result['request'], 17)

    def test_update_mtp_and_invalid_requests_are_refused(self):
        for status in (-1, 2, 3, 5, True, '1'):
            with self.subTest(status=status), self.assertRaises(ValueError):
                command(status, 1)
        for request in (0, -1, 1 << 32, True, '1'):
            with self.subTest(request=request), self.assertRaises(ValueError):
                command(1, request)

    def test_truncated_stale_and_malformed_receipts_are_refused(self):
        valid = struct.pack('<4sI4B', b'XWA2', 1, 1, 0, 0, 0)
        self.assertEqual(len(valid), FRAME_BYTES)
        invalid = [valid[:-1], valid + b'\0', valid.replace(b'XWA2', b'XWA1'),
                   struct.pack('<4sI4B', b'XWA2', 2, 1, 0, 0, 0)]
        for field, value in ((0, 2), (1, 3), (2, 2), (3, 255)):
            state = [1, 0, 0, 0]
            state[field] = value
            invalid.append(struct.pack('<4sI4B', b'XWA2', 1, *state))
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                receipt(data, 1)


if __name__ == '__main__':
    unittest.main()
