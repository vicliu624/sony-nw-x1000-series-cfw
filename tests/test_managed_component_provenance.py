"""A current supervisor cannot hide a stale owner/service build beneath it."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from review_managed_remote_profile import (component_build, input_artifact, player_remote_header,
                                           player_remote_inputs, select_player_remote_inputs)


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

    def test_direct_component_review_refuses_changed_linked_input(self):
        path, _, metadata, _ = self.component('owner')
        linked = self.directory / 'runtime.a'
        linked.write_bytes(b'original linked input')
        metadata['linked_input_hashes'] = {linked.relative_to(ROOT).as_posix(): digest(linked)}
        self.write_receipt(metadata)
        receipt = self.directory / 'build.json'
        _, _, identity = component_build(receipt, path.name)
        self.assertEqual(identity['sha256'], digest(path))

        linked.write_bytes(b'changed linked input')
        with self.assertRaisesRegex(ValueError, 'Component linked input differs'):
            component_build(receipt, path.name)

    def supervisor(self, name, data, **flags):
        profile = dict(built=True, reusable_sessions=True, source_hashes={}, inputs={}, local_inputs={})
        for role in ('owner', 'service'):
            area = self.directory / role
            area.mkdir(exist_ok=True)
            leaf = {'owner':'remote-rf-owner.arm', 'service':'wireless-remote-service.arm'}[role]
            executable = area / leaf
            executable.write_bytes(role.encode())
            identity = dict(bytes=executable.stat().st_size, sha256=digest(executable))
            local = executable.relative_to(ROOT).as_posix()
            (area/'build.json').write_text(json.dumps(dict(built=True, artifact=local, source_hashes={}, **identity)))
            profile['inputs'][role] = identity
            profile['local_inputs'][role] = dict(local=local, **identity)
        binary = self.directory / (name + '.arm')
        binary.write_bytes(data)
        profile.update(flags, artifact=binary.relative_to(ROOT).as_posix(), bytes=len(data), sha256=digest(binary))
        path = self.directory / (name + '.json')
        path.write_text(json.dumps(profile), encoding='utf-8')
        return path

    def test_layout_can_select_a_new_supervisor_with_the_same_compiled_contract(self):
        original = self.supervisor('original', b'old')
        replacement = self.supervisor('replacement', b'new')
        expected, binding, _, _ = player_remote_inputs(original)
        host = dict(remote_factory_profile=binding, remote_factory_contract=expected)
        (self.directory/'original.arm').unlink()
        selected, _, _ = select_player_remote_inputs(host, replacement)
        self.assertNotEqual(selected['sha256'], binding['sha256'])
        self.assertEqual(player_remote_header(expected), player_remote_header(player_remote_inputs(replacement)[0]))
        self.assertEqual(host['remote_factory_profile'], binding)

    def test_layout_refuses_supervisor_with_changed_size_or_owner_mode(self):
        original = self.supervisor('original', b'old')
        expected, binding, _, _ = player_remote_inputs(original)
        host = dict(remote_factory_profile=binding, remote_factory_contract=expected)
        cases = [(self.supervisor('different-size', b'longer'), 'supervisor_bytes'),
                 (self.supervisor('different-mode', b'new', owner_mode_view_forwarded=True),
                  'owner_mode_view_forwarded')]
        for review, field in cases:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                select_player_remote_inputs(host, review)
        with self.assertRaisesRegex(ValueError, 'recorded compile contract'):
            select_player_remote_inputs(dict(remote_factory_profile=binding), cases[0][0])


if __name__ == '__main__':
    unittest.main()
