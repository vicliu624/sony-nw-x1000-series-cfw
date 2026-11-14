"""Actual service callback after cooperative stop, host/stock-libc ARM; no device."""
import hashlib
import json
import os
import subprocess
import time
from app_registry import ROOT
from player_arm_guest import stock_libraries

out = ROOT / 'work/service-stop-observation' / str(time.time_ns())
out.mkdir(parents=True)
source = 'tools/fixtures/service_stop_observation.c'
flags = ['-std=c99', '-O1', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
         '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections']
host = out / 'test.host'
subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', source, '-o', str(host)],
               cwd=ROOT, check=True)
run = subprocess.run([str(host)], capture_output=True, text=True, timeout=10)
(out / 'host.log').write_text(run.stdout + run.stderr)
assert run.returncode == 0, run.stdout + run.stderr
libraries = stock_libraries()
binary = out / 'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
    '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-pie',
    '-fno-stack-protector', '-no-pie', '-nostdlib', '-Wl,--hash-style=sysv,--build-id=none',
    source, 'runtime/store/start.c', 'runtime/store/start.S', str(libraries['libc.so.6']),
    str(libraries['ld-linux.so.3']), '-lgcc', '-o', str(binary)], cwd=ROOT, check=True)
checked = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libraries['ld-linux.so.3']),
    '--library-path', str(libraries['libc.so.6'].parent), str(binary)], cwd=ROOT,
    env=dict(os.environ, QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),
    capture_output=True, text=True, timeout=10)
(out / 'arm.log').write_text(checked.stdout + checked.stderr)
assert checked.returncode == 0, checked.stdout + checked.stderr
inputs = [source, 'runtime/apps/wireless-remote/service.c', 'tools/test_service_stop_observation.py',
          'runtime/store/start.c', 'runtime/store/start.S']
inputs += [p.relative_to(ROOT).as_posix() for p in
           (ROOT / 'runtime/apps/wireless-remote').glob('*.h')]
report = dict(passed=True, actual_service_callback=True, host_sanitizers=True,
    original_libc_arm=True, port_results_modeled=True, cases=5,
    device_accessed=False, firmware_created=False, stdout=checked.stdout,
    source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs},
    limits=['Callback is source-included; unused service entry sections are removed.',
            'Stop flag models cooperative observation; no OS signal, radio or full service process runs.'])
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
print('Report:', out / 'report.json')
