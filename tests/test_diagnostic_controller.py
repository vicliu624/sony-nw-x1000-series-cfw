"""PC-only diagnostic material compatibility and human instructions."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import prepare_diagnostic_materials as materials

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class DiagnosticControllerTests(unittest.TestCase):
    def setUp(self):
        self.area=tempfile.TemporaryDirectory(dir=ROOT/'work',prefix='diagnostic-controller-test-')
        self.addCleanup(self.area.cleanup)
        self.folder=Path(self.area.name)
        self.archive=self.folder/'native/sdk/lib/libxnow.a'
        self.archive.parent.mkdir(parents=True)
        self.archive.write_bytes(b'fixture archive; never linked or installed')
        self.transport={name:digest(ROOT/name) for name in (
            'runtime/platform/espnow/xnow_link.c','runtime/platform/espnow/xnow_link.h')}
        native=dict(built=True,archive_sha256=digest(self.archive),source_hashes=self.transport)
        self.native_receipt=self.archive.parent.parent/'build.json'
        self.native_receipt.write_text(json.dumps(native))
        self.image=self.folder/'firmware.bin';self.image.write_bytes(b'fixture controller; never flashed')
        sources={**self.transport,**{name:digest(ROOT/name) for name in (
            'runtime/apps/wireless-remote/core2/src/main.cpp',
            'runtime/apps/wireless-remote/core2/src/link_transport.cpp',
            'runtime/apps/wireless-remote/core2/src/link_transport.h')}}
        self.core=dict(built=True,version='0.1.0-alpha.29',target='Core2 + Faces Gamepad3',
            source_hashes=sources,artifacts={'firmware.bin':dict(local=self.image.relative_to(ROOT).as_posix(),
                bytes=self.image.stat().st_size,sha256=digest(self.image))})
        self.core_receipt=self.folder/'build.json';self.write_core()
        self.owner=dict(negotiated_link_keys=True,source_hashes={
            'runtime/platform/espnow/xnow_link.h':self.transport['runtime/platform/espnow/xnow_link.h']},
            linked_input_hashes={self.archive.relative_to(ROOT).as_posix():digest(self.archive)})

    def write_core(self):
        self.core_receipt.write_text(json.dumps(self.core))

    def mode_fixture(self):
        self.core['version']='0.1.0-alpha.31'
        self.core['play_mode_write_ui']=True
        names=('runtime/platform/player/player.h',
               'runtime/apps/wireless-remote/control.c','runtime/apps/wireless-remote/control.h',
               'runtime/apps/wireless-remote/link.c','runtime/apps/wireless-remote/link.h',
               'runtime/apps/wireless-remote/mode_wire.c','runtime/apps/wireless-remote/mode_wire.h')
        protocol={name:digest(ROOT/name) for name in names}
        self.core['source_hashes'].update(protocol);self.write_core()
        path=self.folder/'service-review.json'
        service=dict(built=True,command_negotiation_supported=True,source_hashes=protocol)
        path.write_text(json.dumps(service))
        return path,service

    def test_mode_control_requires_new_peer_and_matching_service(self):
        path,_=self.mode_fixture()
        result=materials.matching_controller(self.owner,self.core_receipt,
            play_mode_control=True,service_review=path)
        self.assertTrue(result['play_mode_control'])
        self.assertIn('runtime/platform/player/player.h',result['player_protocol_source_hashes'])
        self.core['version']='0.1.0-alpha.30';self.write_core()
        with self.assertRaisesRegex(ValueError,'alpha.31'):
            materials.matching_controller(self.owner,self.core_receipt,
                play_mode_control=True,service_review=path)

    def test_mode_control_rejects_missing_ui_or_service(self):
        path,_=self.mode_fixture();self.core['play_mode_write_ui']=False;self.write_core()
        with self.assertRaisesRegex(ValueError,'mode-write UI'):
            materials.matching_controller(self.owner,self.core_receipt,
                play_mode_control=True,service_review=path)
        self.core['play_mode_write_ui']=True;self.write_core()
        with self.assertRaisesRegex(ValueError,'service receipt'):
            materials.matching_controller(self.owner,self.core_receipt,play_mode_control=True)

    def test_mode_control_rejects_incomplete_player_protocol_receipt(self):
        path,service=self.mode_fixture()
        del service['source_hashes']['runtime/apps/wireless-remote/control.c']
        path.write_text(json.dumps(service))
        with self.assertRaisesRegex(ValueError,'command protocol sources differ'):
            materials.matching_controller(self.owner,self.core_receipt,
                play_mode_control=True,service_review=path)

    def test_mode_control_rejects_service_without_negotiation(self):
        path,service=self.mode_fixture();service['command_negotiation_supported']=False
        path.write_text(json.dumps(service))
        with self.assertRaisesRegex(ValueError,'explicit command negotiation'):
            materials.matching_controller(self.owner,self.core_receipt,
                play_mode_control=True,service_review=path)

    def test_matching_build_keeps_exact_image_and_transport_identity(self):
        result=materials.matching_controller(self.owner,self.core_receipt)
        self.assertEqual(result['binary'],self.image)
        self.assertEqual(result['sha256'],digest(self.image))
        self.assertEqual(result['transport_source_hashes'],self.transport)
        self.assertEqual(result['native_review'],self.native_receipt)

    def test_negotiated_firmware_requires_controller_before_staging(self):
        with self.assertRaisesRegex(ValueError,'requires --controller-review'):
            materials.matching_controller(self.owner,None)

    def test_legacy_profile_does_not_mix_with_negotiated_controller(self):
        self.owner['negotiated_link_keys']=False
        self.assertIsNone(materials.matching_controller(self.owner,None))
        with self.assertRaisesRegex(ValueError,'requires the negotiated-link'):
            materials.matching_controller(self.owner,self.core_receipt)

    def test_changed_image_is_rejected(self):
        self.image.write_bytes(b'changed fixture')
        with self.assertRaisesRegex(ValueError,'image changed'):
            materials.matching_controller(self.owner,self.core_receipt)

    def test_stale_controller_source_is_rejected(self):
        self.core['source_hashes']['runtime/platform/espnow/xnow_link.c']='0'*64
        self.write_core()
        with self.assertRaisesRegex(ValueError,'Stale source'):
            materials.matching_controller(self.owner,self.core_receipt)

    def test_mismatched_root_header_is_rejected(self):
        self.owner['source_hashes']['runtime/platform/espnow/xnow_link.h']='0'*64
        with self.assertRaisesRegex(ValueError,'transport headers differ'):
            materials.matching_controller(self.owner,self.core_receipt)

    def test_unsupported_controller_and_invalid_semver_are_rejected(self):
        self.core['target']='another board';self.write_core()
        with self.assertRaisesRegex(ValueError,'reviewed Core2'):
            materials.matching_controller(self.owner,self.core_receipt)
        self.core['target']='Core2 + Faces Gamepad3';self.core['version']='0.1.0-alpha.029';self.write_core()
        with self.assertRaisesRegex(ValueError,'Leading zero'):
            materials.matching_controller(self.owner,self.core_receipt)

    def test_readme_uses_reviewed_capacity_and_requires_matching_peer(self):
        controller=materials.matching_controller(self.owner,self.core_receipt)
        reviewed=dict(model=dict(used_growth_bytes=647168,model_nonreserved_margin_bytes=28409856))
        text=materials.instructions('0.1.0-dev.33',reviewed,controller)
        self.assertIn('Use the matching Core2 0.1.0-alpha.29 application',text)
        self.assertIn('image is already installed, keep it',text)
        self.assertIn('632 KiB',text);self.assertIn('27.09 MiB',text)
        self.assertIn('preserve NVS',text);self.assertIn('Turn Wireless Remote off',text)
        self.assertNotIn('No Core2 update is required',text)
        legacy=materials.instructions('0.1.0-dev.33',reviewed,None)
        self.assertNotIn('04_CORE2',legacy);self.assertIn('legacy transport profile',legacy)


class DiagnosticOutputTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(dir=ROOT / 'work', prefix='diagnostic-output-test-')
        self.addCleanup(area.cleanup)
        self.folder = Path(area.name)
        self.output = self.folder / 'delivery' / 'example'
        self.stock = self.folder / 'stock.upg'
        self.firmware = self.folder / 'candidate.upg'
        self.stock.write_bytes(b'fixture original')
        self.firmware.write_bytes(b'fixture candidate')
        self.reviewed = dict(upg=self.firmware, firmware={'sha256': digest(self.firmware)},
                             model=dict(used_growth_bytes=0, model_nonreserved_margin_bytes=0),
                             input_paths=[], subsequent_pc_changes=[], subsequent_external_app_changes=[])

    def assemble(self):
        return materials.assemble_materials(self.output, self.reviewed, None,
                                            {'NW_WM_FW.UPG': self.stock}, {})

    def test_archive_and_directory_contain_the_same_verified_files(self):
        archive, sha256 = self.assemble()
        self.assertEqual(digest(archive), sha256)
        self.assertEqual(archive.with_suffix('.zip.sha256').read_text(), f'{sha256}  {archive.name}\n')
        with zipfile.ZipFile(archive) as bundle:
            files = {str(path.relative_to(self.output).as_posix()): path.read_bytes()
                     for path in self.output.rglob('*') if path.is_file()}
            self.assertEqual(set(bundle.namelist()), {f'example/{name}' for name in files})
            for name, data in files.items():
                self.assertEqual(bundle.read(f'example/{name}'), data)
        self.assertEqual(files['01_PC_UPDATE/NW_WM_FW.UPG'], self.firmware.read_bytes())
        self.assertEqual(files['02_ORIGINAL_SONY/NW_WM_FW.UPG'], self.stock.read_bytes())
        self.assertEqual(len(list(self.output.parent.iterdir())), 3)

    def test_failed_archive_verification_leaves_no_staging_or_final_outputs(self):
        original = materials.stage_materials

        def corrupt_staged_copy(staging, *args):
            files = original(staging, *args)
            (staging / 'materials.json').write_bytes(b'corrupted after inventory')
            return files

        with patch.object(materials, 'stage_materials', side_effect=corrupt_staged_copy):
            with self.assertRaisesRegex(ValueError, 'Archived file differs: example/materials.json'):
                self.assemble()
        self.assertEqual(list(self.output.parent.iterdir()), [])
        with patch.object(Path, 'replace', side_effect=AssertionError('Replaced a final output placeholder')):
            self.assemble()

    def test_output_collision_preserves_existing_checksum_and_removes_partial_zip(self):
        existing = self.output.with_name('example.zip.sha256')
        original = materials.write_verified_archive

        def add_conflicting_file(*args):
            result = original(*args)
            existing.write_text('other delivery\n', encoding='utf-8')
            return result

        with patch.object(materials, 'write_verified_archive', side_effect=add_conflicting_file):
            with self.assertRaises(FileExistsError):
                self.assemble()
        self.assertEqual(list(self.output.parent.iterdir()), [existing])
        self.assertEqual(existing.read_text(encoding='utf-8'), 'other delivery\n')


class DiagnosticRegressionScopeTests(unittest.TestCase):
    def test_unrelated_registered_app_edits_are_reported_separately(self):
        app = 'runtime/apps/qqmusic/'
        tested = {app + 'app.json': 'definition', app + 'main.c': 'old', 'tools/editor.py': 'old'}
        current = {**tested, app + 'main.c': 'new', app + 'new.c': 'added', 'tools/editor.py': 'new'}
        pc, apps = materials.subsequent_source_changes(tested, current, {'source_hashes': {}})
        self.assertEqual(pc, ['tools/editor.py'])
        self.assertEqual(apps, [app + 'main.c', app + 'new.c'])

    def test_reviewed_app_and_layout_builder_changes_invalidate_evidence(self):
        app = 'runtime/apps/qqmusic/'
        tests = ((app + 'main.c', app + 'adapter.h'), ('tools/layout.py', 'tools/layout.py'))
        for changed, reviewed in tests:
            with self.subTest(changed=changed):
                tested = {app + 'app.json': 'definition', changed: 'old'}
                current = {**tested, changed: 'new'}
                review = {'source_hashes': {reviewed.replace('/', '\\'): 'reviewed'}}
                with self.assertRaisesRegex(ValueError, 'Product sources changed'):
                    materials.subsequent_source_changes(tested, current, review)

    def test_system_inputs_and_unclassified_apps_invalidate_evidence(self):
        for name in ('VERSION', 'runtime/platform/player/remote_auto.c', 'sdk/VERSION', 'config/release.json',
                     'runtime/apps/wireless-remote/core2/src/main.cpp', 'runtime/apps/unknown/' + 'new.c'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Product sources changed'):
                materials.subsequent_source_changes({}, {name: 'new'}, {'source_hashes': {}})


if __name__=='__main__':
    unittest.main()
