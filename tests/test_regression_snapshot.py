"""Regression evidence must retain tested bytes, including uncommitted changes."""
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from evidence_checks import source_inventory, verify_source_snapshot, write_source_snapshot
import test_firmware_regressions as regression


class RegressionSnapshotTests(unittest.TestCase):
    def test_inventory_prunes_generated_subtrees(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "VERSION").write_bytes(b"1\n")
            for name in ("runtime/live.c", "runtime/managed_components_user/live.h",
                         "runtime/.pio/build/ignored.c", "runtime/managed_components/ignored.c",
                         "tools/__pycache__/ignored.py"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            visited = []
            real_walk = os.walk

            def walk(*args):
                for entry in real_walk(*args):
                    visited.append(Path(entry[0]).relative_to(root).parts)
                    yield entry

            with mock.patch.object(os, "walk", walk):
                inventory = source_inventory(root)
            self.assertEqual(set(inventory), {"VERSION", "runtime/live.c", "runtime/managed_components_user/live.h"})
            self.assertFalse(any(set(parts) & {".pio", "managed_components", "__pycache__"} for parts in visited))

    def test_plan_deduplicates_commands_but_keeps_distinct_arguments(self):
        suites = {"a": [["one.py"], ["one.py", "--mode"]], "b": [["one.py"], ["two.py"]]}
        with mock.patch.object(regression, "SUITES", suites):
            planned, duplicates = regression.plan_checks(["a", "b", "a"])
        self.assertEqual(planned, [("a", ["one.py"]), ("a", ["one.py", "--mode"]), ("b", ["two.py"])])
        self.assertEqual(len(duplicates), 3)

    def test_plan_does_not_execute_or_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "uncreated"
            arguments = ["regressions", "--suite", "focus", "--plan", "--output", str(output)]
            with mock.patch.object(regression, "SUITES", {"focus": [["never-run.py"]]}), \
                    mock.patch.object(sys, "argv", arguments), \
                    mock.patch.object(regression, "source_inventory", side_effect=AssertionError("scanned")), \
                    mock.patch.object(regression.subprocess, "run", side_effect=AssertionError("executed")), \
                    contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(regression.main(), 0)
            self.assertEqual(len(json.loads(stdout.getvalue())["checks"]), 1)
            self.assertFalse(output.exists())

    def test_unit_module_without_main_is_actually_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "sdk").mkdir()
            (root / "VERSION").write_text("0.1.0\n")
            (root / "sdk/VERSION").write_text("0.2.0\n")
            (root / "tests/test_fixture.py").write_text(
                "import unittest\nfrom pathlib import Path\nclass Check(unittest.TestCase):\n"
                " def test_executed(self): Path('executed').write_text('yes')\n")
            output = root / "work/check"
            with mock.patch.object(regression, "ROOT", root), \
                    mock.patch.object(regression, "SUITES", {"unit": [["tests/test_fixture.py"]]}), \
                    mock.patch.object(sys, "argv", ["regressions", "--suite", "unit", "--output", str(output)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(regression.main(), 0)
            self.assertEqual((root / "executed").read_text(), "yes")
            self.assertTrue(json.loads((output / "report.json").read_text())["passed"])

    def test_aggregate_records_the_radio_child_report_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "sdk").mkdir()
            (root / "VERSION").write_text("0.1.0\n")
            (root / "sdk/VERSION").write_text("0.2.0\n")
            output = root / "work/check"

            def radio_replay(command, **kwargs):
                report_dir = Path(command[command.index("--output") + 1])
                self.assertEqual(report_dir, output / "radio-profiles")
                self.assertEqual(command[command.index("--radio-reviews") + 1], str(root / 'work/radio'))
                self.assertEqual(command[command.index("--sdk-review") + 1], str(root / 'work/sdk/build.json'))
                snapshot = Path(command[command.index("--source-snapshot") + 1])
                self.assertEqual(snapshot, output / "checked-source.zip")
                self.assertEqual(verify_source_snapshot(source_inventory(root), snapshot),
                                 hashlib.sha256(snapshot.read_bytes()).hexdigest())
                report_dir.mkdir()
                (report_dir / "report.json").write_bytes(b'{"passed":true}')
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.object(regression, "ROOT", root), \
                    mock.patch.object(regression, "SUITES", {"integration": [["test_radio_profiles.py"]]}), \
                    mock.patch.object(sys, "argv", ["regressions", "--suite", "integration", "--output", str(output),
                                                     "--radio-reviews", str(root / 'work/radio'),
                                                     "--sdk-review", str(root / 'work/sdk/build.json')]), \
                    mock.patch.object(regression.subprocess, "run", side_effect=radio_replay), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(regression.main(), 0)
            check = json.loads((output / "report.json").read_text())["checks"][0]
            self.assertEqual(check["radio_review"], "work/check/radio-profiles/report.json")
            self.assertEqual(check["radio_review_sha256"],
                             hashlib.sha256(b'{"passed":true}').hexdigest())

    def test_aggregate_builds_one_service_for_all_selected_consumers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "sdk").mkdir()
            (root / "VERSION").write_text("0.1.0\n")
            (root / "sdk/VERSION").write_text("0.2.0\n")
            output = root / "work/check"
            commands = [["test_remote_service.py"], ["test_remote_supervisor.py", "--automatic-factory"]]
            with mock.patch.object(regression, "ROOT", root), \
                    mock.patch.object(regression, "SUITES", {"integration": commands}), \
                    mock.patch.object(sys, "argv", ["regressions", "--suite", "integration", "--output", str(output)]), \
                    mock.patch.object(regression.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(regression.main(), 0)
            build, *consumers = [call.args[0][1:] for call in run.call_args_list]
            self.assertEqual(Path(build[0]).name, "build_remote_service.py")
            self.assertEqual(build[1:], ["--output", str(output / "remote-service")])
            self.assertEqual([Path(command[0]).name for command in consumers], [c[0] for c in commands])
            for command in consumers:
                self.assertEqual(command[-2:], ["--service-review", str(output / "remote-service/build.json")])

    def test_retains_bytes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = "/* uncommitted source */\n".encode()
            (root / "source.c").write_bytes(data)
            hashes = {"source.c": hashlib.sha256(data).hexdigest()}
            archive = root / "checked.zip"
            digest = write_source_snapshot(root, hashes, archive)
            self.assertEqual(digest, hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(verify_source_snapshot(hashes, archive), digest)
            with self.assertRaisesRegex(ValueError, "bytes differ"):
                verify_source_snapshot({"source.c": "0" * 64}, archive)
            with self.assertRaisesRegex(ValueError, "inventory differs"):
                verify_source_snapshot({}, archive)
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
