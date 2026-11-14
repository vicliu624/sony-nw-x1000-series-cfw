"""Regression evidence must retain tested bytes, including uncommitted changes."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from test_firmware_regressions import write_source_snapshot


class RegressionSnapshotTests(unittest.TestCase):
    def test_retains_bytes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = "/* uncommitted source */\n".encode()
            (root / "source.c").write_bytes(data)
            hashes = {"source.c": hashlib.sha256(data).hexdigest()}
            archive = root / "checked.zip"
            digest = write_source_snapshot(root, hashes, archive)
            self.assertEqual(digest, hashlib.sha256(archive.read_bytes()).hexdigest())
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(bundle.namelist(), ["source.c"])
                self.assertEqual(bundle.read("source.c"), data)
            with self.assertRaises(FileExistsError):
                write_source_snapshot(root, hashes, archive)

    def test_refuses_changed_source_before_creating_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.c").write_bytes(b"changed")
            archive = root / "checked.zip"
            with self.assertRaisesRegex(ValueError, "changed before snapshot"):
                write_source_snapshot(root, {"source.c": "0" * 64}, archive)
            self.assertFalse(archive.exists())

    def test_refuses_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "Invalid snapshot name"):
                write_source_snapshot(root, {"../source.c": "0" * 64}, root / "checked.zip")


if __name__ == "__main__":
    unittest.main()
