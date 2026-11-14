"""PC-only diagnostic material compatibility and human instructions."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

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
        self.assertIn('Core2 0.1.0-alpha.29 is required',text)
        self.assertIn('632 KiB',text);self.assertIn('27.09 MiB',text)
        self.assertIn('preserve NVS',text);self.assertIn('Turn Wireless Remote off',text)
        self.assertNotIn('No Core2 update is required',text)
        legacy=materials.instructions('0.1.0-dev.33',reviewed,None)
        self.assertNotIn('04_CORE2',legacy);self.assertIn('legacy transport profile',legacy)

if __name__=='__main__':
    unittest.main()
