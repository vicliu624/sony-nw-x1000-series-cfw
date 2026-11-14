"""Replay the observed PN1/HWM18 contract through real CCMP and a fresh link key."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

from app_registry import ROOT
from player_arm_guest import stock_libraries

out = ROOT / 'work/xnow-link-counter-tests' / str(time.time_ns())
out.mkdir(parents=True)
sources = ['tools/fixtures/xnow_link_counter.c', 'runtime/platform/espnow/xnow_link_counter.c',
    'runtime/platform/espnow/xnow_link.c', 'runtime/platform/espnow/xnow_security.c',
    'runtime/platform/espnow/xnow_ccmp.c', 'runtime/platform/espnow/xnow_pn.c',
    'runtime/platform/espnow/xnow_wire.c', 'runtime/native/sha256.c']
include = ['-I', str(ROOT), '-I', str(ROOT / 'work/external-tls-probe/bearssl-0.6/inc')]
host_library = ROOT / 'work/repository-config-tools/bearssl-host/libbearssl.a'
arm_library = ROOT / 'work/external-tls-probe/arm-build/libbearssl.a'
flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', *include]
host = out / 'test.host'
subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', *sources,
                str(host_library), '-o', str(host)], check=True)
result = subprocess.run([str(host)], capture_output=True, text=True, timeout=15)
(out / 'host.log').write_text(result.stdout + result.stderr)
assert not result.returncode and 'FRESH_LINK_PN1_ACCEPTS_AND_REPLAY_REJECTS' in result.stdout, result.stdout + result.stderr
libraries = stock_libraries()
arm = out / 'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-Os', '-U_FORTIFY_SOURCE',
    '-D_FORTIFY_SOURCE=0', '-march=armv5te', '-marm', '-mfloat-abi=soft',
    '-fno-builtin', '-fno-stack-protector', '-fno-pie', '-no-pie', '-nostdlib',
    '-Wl,--hash-style=sysv,--build-id=none', *sources, 'runtime/store/start.c',
    'runtime/store/start.S', str(arm_library), str(libraries['libc.so.6']),
    str(libraries['ld-linux.so.3']), '-lgcc', '-o', str(arm)], check=True)
result = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libraries['ld-linux.so.3']),
    '--library-path', str(libraries['libc.so.6'].parent), str(arm)],
    capture_output=True, text=True, timeout=15)
(out / 'arm.log').write_text(result.stdout + result.stderr)
assert not result.returncode and 'FRESH_LINK_PN1_ACCEPTS_AND_REPLAY_REJECTS' in result.stdout, result.stdout + result.stderr
report = dict(passed=True, host_sanitizers=True, original_libc_arm926=True,
    real_ccmp=True, observed_counter_state_reproduced=True, synthetic_keys_only=True,
    legacy_journal_untouched=True, unknown_scope_refused=True, duplicate_prepare_refused=True,
    device_accessed=False, radio_integrated=False,
    source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in [*sources, 'runtime/platform/espnow/xnow_link_counter.h',
                     'runtime/platform/espnow/xnow_link.h', 'tools/test_xnow_link_counter.py']},
    archive_hashes={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (host_library, arm_library)})
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, report=(out / 'report.json').relative_to(ROOT).as_posix())))
