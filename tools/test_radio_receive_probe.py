"""Execute the actual ARM receive probe through a GET-only fixture; no device IO."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from app_registry import ROOT
from marvell_firmware import parse
from player_arm_guest import stock_libraries
from prepare_espnow_radio_candidate import memory
from review_managed_remote_profile import receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', required=True)
    args = parser.parse_args()
    review_path, review = receipt(args.review)
    radio = ROOT / review['radio_build']
    manifest = json.loads((radio / 'manifest.json').read_text())
    loaded = memory(parse((radio / 'candidate/sd8686.bin').read_bytes()))
    words = {address: int.from_bytes(bytes(loaded[address + i] for i in range(4)), 'little')
             for segment in manifest['immutable_segments']
             for address in range(segment['address'], segment['address'] + segment['bytes'], 4)}
    controls = manifest['controls']
    rx = controls['xnow_full_rx']['address']
    state = {rx: 0x3252584e, rx + 4: 6, rx + 8: 6, rx + 16: 1, rx + 56: 0, rx + 60: 0,
        controls['xnow_rx_seen']['address']: 12, controls['xnow_rx_eligible']['address']: 7,
        0xc0014528: 0x8203, 0x8000a300: 0x10000000, 0x8000200c: 0x01000000}
    out = ROOT / 'work/radio-receive-probe-tests' / str(time.time_ns())
    out.mkdir(parents=True)
    (out / 'radio_receive_profile.h').write_bytes((review_path.parent / 'radio_receive_profile.h').read_bytes())
    libs = stock_libraries()
    rows = []
    for case, expected in (('valid', 0), ('code-mismatch', 70), ('queue-magic', 70), ('driver-mismatch', 69)):
        folder = out / case
        folder.mkdir()
        values = dict(words)
        if case == 'code-mismatch':
            values[min(words)] ^= 1
            # No state words: premature state reads abort in the ioctl fixture.
        else:
            values.update(state)
            if case == 'queue-magic': values[rx] ^= 1
        driver = folder / 'driver.txt'
        driver.write_text('wrong\n' if case == 'driver-mismatch' else 'driver=sd8686-9.70.3.p32-26409.p51-(FP4)\n')
        header = '#define INSPECT_DRIVER_INFO ' + json.dumps(str(driver)) + '\n'
        header += 'static const unsigned mock_words[][2]={' + ','.join(
            '{' + hex(a) + ',' + hex(v) + '}' for a, v in sorted(values.items())) + '};\n'
        (folder / 'radio_inspect_mock.h').write_text(header)
        binary = folder / 'probe-fixture.arm'
        flags = ['-std=c99', '-Os', '-Wall', '-Wextra', '-Werror', '-U_FORTIFY_SOURCE',
            '-D_FORTIFY_SOURCE=0', '-march=armv5te', '-marm', '-mfloat-abi=soft',
            '-fno-builtin', '-fno-stack-protector', '-fno-pie', '-no-pie', '-nostdlib',
            '-Wl,--hash-style=sysv,--build-id=none', '-I' + str(ROOT), '-I' + str(out),
            '-I' + str(folder), '-I' + str(ROOT / 'runtime/platform/espnow')]
        sources = ['tools/device_probes/radio_receive_probe.c', 'runtime/native/sha256.c',
                   'tools/fixtures/radio_inspect_ioctl.c', 'runtime/store/start.c', 'runtime/store/start.S']
        subprocess.run(['arm-linux-gnueabi-gcc', *flags,
            *['-Wl,--wrap=' + name for name in ('fopen', 'fopen64', 'socket', 'close', 'ioctl')],
            *sources, str(libs['libc.so.6']), str(libs['ld-linux.so.3']), '-lgcc', '-o', str(binary)], check=True)
        result = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']),
            '--library-path', str(libs['libc.so.6'].parent), str(binary), '--inspect-receive'],
            capture_output=True, text=True, timeout=15)
        (folder / 'run.log').write_text(result.stdout + result.stderr)
        assert result.returncode == expected, (case, result.stdout, result.stderr)
        if not expected:
            observed = json.loads(result.stdout)
            assert len(observed['samples']) == 2 and observed['atomic'] is False
            assert all((row['hook_entries'], row['eligible'], row['head'], row['tail']) == (12, 7, 6, 6)
                       for row in observed['samples'])
            assert observed['hardware_admission_verified'] is False
        else:
            assert '{' not in result.stdout
        rows.append(dict(case=case, exit_code=result.returncode))
    report = dict(passed=True, original_libc_arm926=True, get_only_ioctl_fixture=True,
        cases=rows, failed_fingerprint_does_not_read_counters=True,
        device_accessed=False, installed=False,
        source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
            [*sources, 'tools/test_radio_receive_probe.py']},
        build_review_sha256=hashlib.sha256(review_path.read_bytes()).hexdigest())
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, report=(out / 'report.json').relative_to(ROOT).as_posix())))


if __name__ == '__main__':
    main()
