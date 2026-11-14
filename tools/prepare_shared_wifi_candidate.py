"""Compose a private UPG to isolate stock Wi-Fi loading of the shared image."""
import argparse
import copy
import gzip
import io
import json
import tarfile
import tempfile
from pathlib import Path

from app_registry import ROOT
from prepare_managed_firmware_review import unpack
from prepare_shared_wifi_image import RADIO_PATH, HELPER_PATH, LOADER_PATH
from release_firmware import pack
from review_managed_remote_profile import digest, private
from review_managed_root_capacity import inventory

BASE_SHA256 = '2328d7375e1c1a87b4ff8e1cd77a8bf6d06be0e6498fff953692a7651abb410e'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-review', required=True)
    args = parser.parse_args()
    review_path = private(args.image_review)
    review = json.loads(review_path.read_text())
    assert review['prepared'] and review['rx_initially_disabled']
    assert set(review['overlay']) == {RADIO_PATH}
    assert set(review['unchanged']) == {HELPER_PATH, LOADER_PATH}
    row = review['overlay'][RADIO_PATH]
    image = private(row['artifact'])
    assert image == review_path.parent/'root-overlay'/RADIO_PATH
    assert digest(image)==row['sha256'] and image.stat().st_size==row['bytes']
    baseline = private('work/startup-candidate-materials/1793858639057351161/01_PC_UPDATE/NW_WM_FW.UPG')
    assert digest(baseline)==BASE_SHA256
    _, parts = unpack(baseline.read_bytes(), require_stock=False)
    before = inventory(parts[3])
    original = before[RADIO_PATH]
    assert original['kind']=='file' and original['sha256']==row['original_sha256']
    assert all(original[key]==row[key] for key in ('uid','gid','mode'))
    assert all(before[name]['sha256']==sha for name,sha in review['unchanged'].items())
    root = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as src, \
         tarfile.open(fileobj=root,mode='w',format=tarfile.GNU_FORMAT) as dst:
        for member in src:
            info = copy.copy(member)
            if member.name.removeprefix('./')==RADIO_PATH:
                info.size=row['bytes']
                dst.addfile(info,io.BytesIO(image.read_bytes()))
            else:
                dst.addfile(info,src.extractfile(member) if member.isfile() else None)
    root_bytes=gzip.compress(root.getvalue(),mtime=0)
    candidate=pack([*parts[:3],root_bytes])
    _, decoded=unpack(candidate,require_stock=False)
    assert decoded[:3]==parts[:3] and decoded[3]==root_bytes
    expected=dict(before)
    expected[RADIO_PATH]=dict(original,bytes=row['bytes'],sha256=row['sha256'])
    assert inventory(decoded[3])==expected
    out=Path(tempfile.mkdtemp(prefix='shared-wifi-candidate-',dir=ROOT/'work'))
    artifact=out/'SHARED-WIFI-ASSOCIATION-REVIEW.UPG'
    artifact.write_bytes(candidate)
    report=dict(prepared=True,artifact=artifact.relative_to(ROOT).as_posix(),sha256=digest(artifact),
                bytes=len(candidate),baseline_sha256=BASE_SHA256,changed_paths=[RADIO_PATH],
                original_installer_kernel_initrd_unchanged=True,roundtrip_verified=True,
                image_review=review_path.relative_to(ROOT).as_posix(),image_review_sha256=digest(review_path),
                device_accessed=False,ready_to_flash=False,association_verified=False,
                remote_test_supported=False,
                limits=['Existing exclusive remote must remain off for an association-only trial.'])
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(report=(out/'report.json').relative_to(ROOT).as_posix(),**report),indent=2))


if __name__=='__main__':
    main()
