"""Exercise link negotiation and restart lifetimes without any radio/device IO."""
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import subprocess
import time

from app_registry import ROOT
from player_arm_guest import stock_libraries

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--host-only', action='store_true')
options = parser.parse_args()
out = ROOT / 'work/xnow-link-tests' / str(time.time_ns())
out.mkdir(parents=True)
sources = ['tools/fixtures/xnow_link.c', 'runtime/platform/espnow/xnow_link.c',
           'runtime/native/sha256.c']
flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT)]
host = out / 'test.host'
subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', *sources,
                '-o', str(host)], check=True)
result = subprocess.run([str(host)], capture_output=True, text=True, timeout=10)
(out / 'host.log').write_text(result.stdout + result.stderr)
assert not result.returncode and 'XNOW_LINK_PASS' in result.stdout, result.stdout + result.stderr
root_mac = bytes([2, 0, 0, 0, 0, 1])
controller_mac = bytes([2, 0, 0, 0, 0, 2])
transcript = root_mac + controller_mac + bytes([101]) * 16 + bytes([1]) * 16
expected = hmac.new(bytes([0x5a]) * 32, b'X1000-ESPNOW-LINK-LMK-v1' + transcript,
                    hashlib.sha256).digest()[:16].hex()
assert result.stdout.splitlines()[0] == expected, (result.stdout, expected)
if not options.host_only:
    libraries = stock_libraries()
    arm = out / 'test.arm'
    subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-Os', '-U_FORTIFY_SOURCE',
        '-D_FORTIFY_SOURCE=0', '-march=armv5te', '-marm', '-mfloat-abi=soft',
        '-fno-builtin', '-fno-stack-protector', '-fno-pie', '-no-pie', '-nostdlib',
        '-Wl,--hash-style=sysv,--build-id=none', *sources, 'runtime/store/start.c',
        'runtime/store/start.S', str(libraries['libc.so.6']), str(libraries['ld-linux.so.3']),
        '-lgcc', '-o', str(arm)], check=True)
    result = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libraries['ld-linux.so.3']),
        '--library-path', str(libraries['libc.so.6'].parent), str(arm)],
        capture_output=True, text=True, timeout=10)
    (out / 'arm.log').write_text(result.stdout + result.stderr)
    assert not result.returncode and 'XNOW_LINK_PASS' in result.stdout, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == expected
report = dict(passed=True, host_sanitizers=True, original_libc_arm926=not options.host_only,
    independent_hmac_derivation=True, device_accessed=False, radio_integrated=False,
    covered=['both endpoint reboots', 'lost Ready and duplicates', 'no install before confirmation',
             'wrong authentication and source', 'expiry and late key installation',
             'bounded retries', 'stale send ticket', 'stop during entropy', 'no idle heartbeat'],
    source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                   for name in [*sources, 'runtime/platform/espnow/xnow_link.h', 'tools/test_xnow_link.py']})
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, report=(out / 'report.json').relative_to(ROOT).as_posix())))
