"""A current supervisor cannot hide a stale owner/service build beneath it."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from review_managed_remote_profile import input_artifact


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ManagedComponentProvenanceTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'work').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='component-proof-', dir=ROOT / 'work')
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def component(self, role):
        leaf = {'owner': 'remote-rf-owner.arm', 'service': 'wireless-remote-service.arm',
                'config': 'config.bin'}[role]
        path = self.directory / leaf
        path.write_bytes(b'identity-fixture-only-not-an-ARM-image')
        source = self.directory / 'source.c'
        source.write_text('original source\n', encoding='utf-8')
        metadata = dict(built=True, artifact=path.relative_to(ROOT).as_posix(),
                        bytes=path.stat().st_size, sha256=digest(path),
                        source_hashes={source.relative_to(ROOT).as_posix(): digest(source)})
        item = dict(bytes=path.stat().st_size, sha256=digest(path))
        supervisor = dict(inputs={role: item}, local_inputs={role: dict(
            local=path.relative_to(ROOT).as_posix(), **item)})
        return path, source, metadata, supervisor

    def write_receipt(self, metadata):
        (self.directory / 'build.json').write_text(json.dumps(metadata), encoding='utf-8')

    def test_current_source_and_artifact_are_accepted_for_each_code_component(self):
        for role in ('owner', 'service'):
            with self.subTest(role=role):
                path, _, metadata, supervisor = self.component(role)
                self.write_receipt(metadata)
                actual, _ = input_artifact(supervisor, role, path.name)
                self.assertEqual(actual, path.resolve())

    def test_stale_child_source_is_rejected_even_with_unchanged_parent_and_binary(self):
        for role in ('owner', 'service'):
            with self.subTest(role=role):
                path, source, metadata, supervisor = self.component(role)
                self.write_receipt(metadata)
                source.write_text('edited without rebuilding\n', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Stale source/input'):
                    input_artifact(supervisor, role, path.name)

    def test_child_receipt_cannot_describe_another_artifact(self):
        path, _, metadata, supervisor = self.component('owner')
        other = self.directory / 'another.arm'
        other.write_bytes(path.read_bytes())
        metadata['artifact'] = other.relative_to(ROOT).as_posix()
        self.write_receipt(metadata)
        with self.assertRaisesRegex(ValueError, 'Component build receipt differs'):
            input_artifact(supervisor, 'owner', path.name)

    def test_unbuilt_component_is_not_a_successful_build(self):
        path, _, metadata, supervisor = self.component('service')
        metadata['built'] = False
        self.write_receipt(metadata)
        with self.assertRaisesRegex(ValueError, 'Component build receipt differs'):
            input_artifact(supervisor, 'service', path.name)

    def test_configuration_is_data_and_does_not_require_a_code_build_receipt(self):
        path, _, _, supervisor = self.component('config')
        actual, _ = input_artifact(supervisor, 'config', path.name)
        self.assertEqual(actual, path.resolve())


if __name__ == '__main__':
    unittest.main()
