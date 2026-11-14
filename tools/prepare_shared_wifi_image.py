"""Prepare a local radio overlay for the original Japanese 1.11 Wi-Fi loader."""
import argparse
import hashlib
import json
import tarfile
import tempfile
from pathlib import Path

from app_registry import ROOT
from build_espnow_full_radio import build, digest
from generate_espnow_full_profile import reviewed_radio
from review_managed_remote_profile import private
from sdk_build import fresh_work

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
    parser.add_argument('--radio-review', type=Path, help='Reuse an existing radio build directory under work/')
    parser.add_argument('--output', type=Path, help='New output directory under work/')
    args = parser.parse_args()
    if args.radio_review is not None and any((args.rx_diagnostics, args.bulk_commands, args.read_vector, args.frame_transactions)):
        parser.error('--radio-review uses the recorded profile and cannot be combined with build flags')
    rootfs = private('work/upg-jp/verified-3.bin')
    with rootfs.open('rb') as file:
        if hashlib.file_digest(file, 'sha256').hexdigest() != ROOT_SHA256:
            raise ValueError('Original Sony root identity differs')
    with tarfile.open(rootfs,'r:gz') as archive:
        inputs = {}
        for name in (RADIO_PATH,HELPER_PATH,LOADER_PATH):
            member = archive.getmember('./'+name)
            assert member.isfile() and member.size < 1024*1024
            inputs[name] = (member,archive.extractfile(member).read())
    loader = inputs[LOADER_PATH][1]
    assert b'fw_dir=${fw_dir:-/lib/modules}' in loader
    assert b'helper_name=${fw_dir}/helper_sd.bin fw_name=${fw_dir}/sd8686.bin' in loader
    if args.radio_review is not None:
        elf, radio = reviewed_radio(args.radio_review)
        radio_dir = elf.parent
    out = (fresh_work(args.output) if args.output is not None else
           Path(tempfile.mkdtemp(prefix='shared-wifi-image-', dir=ROOT / 'work')))
    if args.radio_review is None:
        radio_dir = out / 'radio-build'
        with tempfile.TemporaryDirectory(prefix='stock-', dir=out) as folder:
            stock, helper = (Path(folder) / Path(name).name for name in (RADIO_PATH, HELPER_PATH))
            stock.write_bytes(inputs[RADIO_PATH][1])
            helper.write_bytes(inputs[HELPER_PATH][1])
            radio = build(stock, helper, radio_dir, args.rx_diagnostics, args.bulk_commands,
                          args.read_vector, args.frame_transactions)
    assert radio['rx_initially_disabled'] and radio['crc_roundtrip_passed']
    if (radio['original_sha256'] != digest(inputs[RADIO_PATH][1]) or
            radio['helper_sha256'] != digest(inputs[HELPER_PATH][1])):
        raise ValueError('Radio review uses different Sony loader inputs')
    payload = private(radio_dir / 'candidate/sd8686.bin').read_bytes()
    if digest(payload) != radio['candidate_sha256']:
        raise ValueError('Radio image identity differs')
    build_receipt = private(radio_dir / 'manifest.json')
    receipt_bytes = build_receipt.read_bytes()
    if json.loads(receipt_bytes) != radio:
        raise ValueError('Radio build receipt changed during overlay preparation')
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
                  radio_build=build_receipt.relative_to(ROOT).as_posix(),
                  radio_build_sha256=digest(receipt_bytes),
                  rx_initially_disabled=True,device_accessed=False,ready_to_flash=False,
                  bulk_word_commands=radio.get('bulk_word_commands'),
                  frame_transactions=radio.get('frame_transactions'),
                  association_verified=False,simultaneous_espnow_verified=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(report=(out/'report.json').relative_to(ROOT).as_posix(),**report),indent=2))


if __name__ == '__main__':
    main()
