"""Build a local radio overlay for the original Japanese 1.11 Wi-Fi loader."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile

from app_registry import ROOT
from build_espnow_full_radio import build, digest

ROOT_SHA256 = 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
RADIO_PATH = 'lib/modules/sd8686.bin'
HELPER_PATH = 'lib/modules/helper_sd.bin'
LOADER_PATH = 'usr/local/bin/wlan_load_driver.sh'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rx-diagnostics', action='store_true')
    parser.add_argument('--bulk-commands', action='store_true',
                        help='Bounded packet-only command extension; requires its matching native adapter')
    parser.add_argument('--read-vector', action='store_true')
    parser.add_argument('--frame-transactions', action='store_true')
    args = parser.parse_args()
    rootfs = ROOT / 'work/upg-jp/verified-3.bin'
    with rootfs.open('rb') as file:
        assert hashlib.file_digest(file,'sha256').hexdigest() == ROOT_SHA256
    out = Path(tempfile.mkdtemp(prefix='shared-wifi-image-',dir=ROOT/'work'))
    with tarfile.open(rootfs,'r:gz') as archive:
        inputs = {}
        for name in (RADIO_PATH,HELPER_PATH,LOADER_PATH):
            member = archive.getmember('./'+name)
            assert member.isfile() and member.size < 1024*1024
            inputs[name] = (member,archive.extractfile(member).read())
    loader = inputs[LOADER_PATH][1]
    assert b'fw_dir=${fw_dir:-/lib/modules}' in loader
    assert b'helper_name=${fw_dir}/helper_sd.bin fw_name=${fw_dir}/sd8686.bin' in loader
    for name in (RADIO_PATH,HELPER_PATH):
        (out/Path(name).name).write_bytes(inputs[name][1])
    radio = build(out/'sd8686.bin',out/'helper_sd.bin',out/'radio-build',args.rx_diagnostics,args.bulk_commands,args.read_vector,args.frame_transactions)
    assert radio['rx_initially_disabled'] and radio['crc_roundtrip_passed']
    payload = (out/'radio-build/candidate/sd8686.bin').read_bytes()
    assert digest(payload)==radio['candidate_sha256']
    target = out/'root-overlay'/RADIO_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)
    original = inputs[RADIO_PATH][0]
    target.chmod(original.mode)
    report = dict(prepared=True,root_sha256=ROOT_SHA256,
                  overlay={RADIO_PATH:dict(artifact=target.relative_to(ROOT).as_posix(),
                      sha256=digest(payload),original_sha256=radio['original_sha256'],
                      bytes=len(payload),delta_bytes=len(payload)-original.size,
                      mode=original.mode,uid=original.uid,gid=original.gid)},
                  unchanged={name:digest(inputs[name][1]) for name in (HELPER_PATH,LOADER_PATH)},
                  radio_build=(out/'radio-build/manifest.json').relative_to(ROOT).as_posix(),
                  rx_initially_disabled=True,device_accessed=False,ready_to_flash=False,
                  bulk_word_commands=radio.get('bulk_word_commands'),
                  frame_transactions=radio.get('frame_transactions'),
                  association_verified=False,simultaneous_espnow_verified=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(report=(out/'report.json').relative_to(ROOT).as_posix(),**report),indent=2))


if __name__ == '__main__':
    main()
