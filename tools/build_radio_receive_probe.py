"""Build one fixed-profile GET-only radio probe; never deploy or execute on a device."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from app_registry import ROOT
from generate_espnow_full_profile import profile_header, reviewed_radio
from player_arm_guest import stock_libraries

VERSION = '0.1.0-alpha.1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--radio-review', type=Path, required=True)
    args = parser.parse_args()
    payload, manifest = reviewed_radio(args.radio_review)
    directory = payload.parent
    profile = profile_header(manifest)
    if not manifest.get('rx_diagnostics') or 'XNOW_RADIO_RX_SEEN' not in profile:
        raise ValueError('The exact diagnostic counter profile is required')
    out = ROOT / 'work/radio-receive-probe' / str(time.time_ns())
    out.mkdir(parents=True)
    header = out / 'radio_receive_profile.h'
    header.write_text('#define RADIO_RECEIVE_VERSION ' + json.dumps(VERSION) + '\n' +
        '#define RADIO_RECEIVE_INPUT_SHA256 ' + json.dumps(manifest['candidate_sha256']) + '\n' + profile)
    sources = ['tools/device_probes/radio_receive_probe.c', 'runtime/native/sha256.c',
               'runtime/store/start.c', 'runtime/store/start.S']
    libraries = stock_libraries()
    binary = out / 'radio-receive-probe.arm'
    flags = ['-std=c99', '-Os', '-Wall', '-Wextra', '-Werror', '-U_FORTIFY_SOURCE',
             '-D_FORTIFY_SOURCE=0', '-march=armv5te', '-marm', '-mfloat-abi=soft',
             '-fno-builtin', '-fno-stack-protector', '-fno-pie', '-no-pie', '-nostdlib',
             '-Wl,--hash-style=sysv,--build-id=none', '-Wl,--dynamic-linker=/lib/ld-linux.so.3',
             '-I' + str(ROOT), '-I' + str(out), '-I' + str(ROOT / 'runtime/platform/espnow')]
    subprocess.run(['arm-linux-gnueabi-gcc', *flags, *sources,
                    str(libraries['libc.so.6']), str(libraries['ld-linux.so.3']),
                    '-lgcc', '-o', str(binary)], cwd=ROOT, check=True)
    checks = []
    for argument, expected in (('--help', 0), ('--version', 0), ('--read-address', 64)):
        result = subprocess.run(['qemu-arm', '-cpu', 'arm926',
            str(libraries['ld-linux.so.3']), '--library-path', str(libraries['libc.so.6'].parent),
            str(binary), argument], capture_output=True, text=True, timeout=15)
        if result.returncode != expected:
            raise RuntimeError(result.stdout + result.stderr)
        checks.append(dict(argument=argument, exit_code=result.returncode))
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    inputs = [ROOT / source for source in sources] + [Path(__file__).resolve(), header, payload,
              directory / 'manifest.json', directory / 'candidate/sd8686.bin',
              directory / 'stock/sd8686.bin', directory / 'candidate/helper_sd.bin',
              ROOT / 'tools/generate_espnow_full_profile.py']
    report = dict(built=True, version=VERSION, artifact=binary.relative_to(ROOT).as_posix(),
        bytes=binary.stat().st_size, sha256=sha(binary), radio_build=directory.relative_to(ROOT).as_posix(),
        radio_sha256=manifest['candidate_sha256'], original_libc_safe_cli_checks=checks,
        inspect_executed_on_device=False, device_accessed=False, installed=False,
        source_hashes={**manifest['source_hashes'], **{path.relative_to(ROOT).as_posix(): sha(path) for path in inputs}},
        limits=['Fixed GET-only profile; no keys or payloads are read.',
                'No physical command timing or counter persistence is established.',
                'Sequential samples are not atomic; reload can reset the counters.'])
    (out / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(built=True, review=(out / 'build.json').relative_to(ROOT).as_posix(),
                          bytes=report['bytes'], sha256=report['sha256']), indent=2))


if __name__ == '__main__':
    main()
