"""Artwork timing regression; real client, synthetic monotonic time, no device."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
from app_registry import ROOT
from player_arm_guest import stock_libraries

out = ROOT / 'work/artwork-timing-tests' / str(time.time_ns())
out.mkdir(parents=True)
sources = ['tools/fixtures/artwork_timing.c',
           'runtime/apps/wireless-remote/artwork_client.c',
           'runtime/apps/wireless-remote/artwork_wire.c',
           'runtime/apps/wireless-remote/status_auth.c',
           'runtime/apps/wireless-remote/link.c', 'runtime/native/sha256.c']
flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation']
host = out / 'test.host'
subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', *sources, '-o', str(host)],
               cwd=ROOT, check=True)
results = []
for case in ('pace', 'budget'):
    run = subprocess.run([str(host), case], cwd=ROOT, capture_output=True, text=True, timeout=20)
    (out / ('host-' + case + '.log')).write_text(run.stdout + run.stderr, encoding='utf-8')
    results.append(dict(case=case, exit=run.returncode, stdout=run.stdout, stderr=run.stderr))
print(json.dumps(dict(host_cases=results, output=str(out)), indent=2), flush=True)
assert all(row['exit'] == 0 for row in results), results
libs = stock_libraries()
arm = out / 'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-Os', '-march=armv5te', '-marm',
                '-mfloat-abi=soft', '-fno-builtin', '-fno-stack-protector', '-no-pie', '-fno-pie',
                '-nostdlib', '-Wl,--hash-style=sysv,--build-id=none', *sources,
                'runtime/store/start.c', 'runtime/store/start.S', str(libs['libc.so.6']),
                str(libs['ld-linux.so.3']), '-lgcc', '-o', str(arm)], cwd=ROOT, check=True)
run = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']),
                      '--library-path', str(libs['libc.so.6'].parent), str(arm)],
                     cwd=ROOT, env=dict(os.environ, QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),
                     capture_output=True, text=True, timeout=20)
(out / 'arm.log').write_text(run.stdout + run.stderr, encoding='utf-8')
assert run.returncode == 0, run.stdout + run.stderr
inputs = sources + ['runtime/apps/wireless-remote/artwork_client.h',
                    'runtime/apps/wireless-remote/artwork_wire.h', 'tools/test_artwork_timing.py']
report = dict(passed=True, host_sanitizers=True, original_libc_arm926=True,
              device_accessed=False, synthetic_time=True, stdout=run.stdout,
              source_hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs})
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
