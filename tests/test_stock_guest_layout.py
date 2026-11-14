"""A guest layout must use exact regular files without escaping its overlay."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from stock_guest_layout import read_overlay


class StockGuestLayoutTests(unittest.TestCase):
    def test_exact_bytes_and_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            file = directory / 'usr/lib/player'
            file.parent.mkdir(parents=True)
            file.write_bytes(b'analysis-input')
            rows = {'usr/lib/player': {'bytes': 14, 'mode': '0o755',
                    'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}}
            self.assertEqual(read_overlay(directory, rows), {'usr/lib/player': (b'analysis-input', 0o755)})
            file.write_bytes(b'analysis-other')
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                read_overlay(directory, rows)

    def test_rejects_escape_and_noncanonical_names_before_read(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('../outside', '/usr/lib/player', 'usr//lib/player', 'usr/./lib/player', 'usr\\lib\\player'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    read_overlay(Path(folder), {name: {'bytes': 0, 'mode': '0o755', 'sha256': ''}})

    def test_missing_or_wrong_size_does_not_fall_back_to_stock(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            rows = {'player': {'bytes': 1, 'mode': '0o755', 'sha256': ''}}
            with self.assertRaises(FileNotFoundError):
                read_overlay(directory, rows)
            (directory / 'player').write_bytes(b'')
            with self.assertRaisesRegex(ValueError, 'size/type changed'):
                read_overlay(directory, rows)


if __name__ == '__main__':
    unittest.main()
