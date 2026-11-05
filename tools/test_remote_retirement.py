"""Remote retirement adapter with the actual generic SDK pipe parser; never accesses a device."""
import hashlib
import json
import os
import subprocess
import time
from app_registry import ROOT
from player_arm_guest import stock_libraries

out = ROOT / 'work/remote-retirement-tests' / str(time.time_ns())
out.mkdir(parents=True)
sources = ['tools/test_remote_retirement.c', 'runtime/apps/wireless-remote/radio_retirement.c', 'runtime/platform/espnow/xnow_handoff.c', 'runtime/store/stock_fs_bridge.c', 'runtime/store/stock_stat64.c']
flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation']
host = out / 'test.host'
subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', *sources,
                '-o', str(host)], cwd=ROOT, check=True)
subprocess.run([str(host)], cwd=ROOT, check=True, timeout=20,
               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
libs = stock_libraries()
arm = out / 'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-Os', '-DHB_STORE_SONY_LIBC', '-march=armv5te',
                '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-stack-protector',
                '-no-pie', '-fno-pie', '-nostdlib', '-Wl,--hash-style=sysv,--build-id=none',
                *sources, 'runtime/store/start.c', 'runtime/store/start.S',
                str(libs['libc.so.6']), str(libs['ld-linux.so.3']), '-lgcc',
                '-o', str(arm)], cwd=ROOT, check=True)
run = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']),
                      '--library-path', str(libs['libc.so.6'].parent), str(arm)],
                     cwd=ROOT, env=dict(os.environ, QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),
                     capture_output=True, text=True, timeout=20)
assert run.returncode == 0, run.stdout + run.stderr
inputs = sources + ['tools/test_remote_retirement.py', 'runtime/store/start.c',
                    'runtime/store/start.S', 'runtime/platform/player/player.h',
                    'runtime/platform/player/provider.h', 'runtime/platform/espnow/xnow_client.h', 'runtime/platform/espnow/xnow_handoff.h', 'runtime/store/target_abi.h', 'runtime/store/stock_fs_bridge.h', 'runtime/store/stock_stat64.h']
inputs += [p.relative_to(ROOT).as_posix() for p in
           (ROOT / 'runtime/apps/wireless-remote').glob('*.h')]
report = dict(passed=True, host_sanitizers=True, original_libc_arm926_executed=True,
              radio_hardware_modeled=True, actual_handoff_parser=True, device_accessed=False, stdout=run.stdout,
              source_hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs})
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
