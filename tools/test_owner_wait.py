"""Real select/pipe wakeups, with host sanitizers and original Sony libc ABI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from app_registry import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-only', action='store_true')
    parser.add_argument('--baseline', action='store_true', help='Reproduce original-only blocked wait')
    args = parser.parse_args()
    out = ROOT / 'work/owner-wait' / str(time.time_ns())
    out.mkdir(parents=True, exist_ok=False)
    sources = ['runtime/platform/player/owner_wait.c', 'tools/fixtures/owner_wait_io.c']
    warnings = ['-std=c99', '-Wall', '-Wextra', '-Werror']
    host = out / 'host'
    subprocess.run(['gcc-12', *warnings, '-O1', '-fsanitize=address,undefined',
                    *sources, '-o', str(host)], cwd=ROOT, check=True)
    if args.baseline:
        run = subprocess.run([str(host), '--original-only'], capture_output=True, text=True, timeout=5)
        (out / 'baseline.log').write_text(run.stdout + run.stderr)
        assert run.returncode == -signal.SIGALRM, (run.returncode, run.stderr)
        print('REPRODUCED: original wait did not wake for pending SDK request')
    run = subprocess.run([str(host)], capture_output=True, text=True, timeout=10)
    (out / 'host.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0, run.stdout + run.stderr
    report = dict(passed=True, host_sanitizers=True, real_select_pipe=True,
                  original_libc_arm=False, baseline_reproduced=args.baseline,
                  device_accessed=False, firmware_created=False)
    if not args.host_only:
        from player_arm_guest import stock_libraries
        libraries = stock_libraries()
        arm = out / 'test.arm'
        startup = ['runtime/store/start.c', 'runtime/store/start.S']
        subprocess.run(['arm-linux-gnueabi-gcc', *warnings, '-Os', '-DXW_WAIT_STOCK',
            '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-march=armv5te', '-marm',
            '-mfloat-abi=soft', '-fno-builtin', '-fno-pie', '-fno-stack-protector',
            '-nostdlib', '-no-pie', '-Wl,--hash-style=sysv,--build-id=none',
            *sources, *startup, str(libraries['libc.so.6']), str(libraries['ld-linux.so.3']),
            '-lgcc', '-o', str(arm)], cwd=ROOT, check=True)
        checked = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libraries['ld-linux.so.3']),
            '--library-path', str(libraries['libc.so.6'].parent), str(arm)], cwd=ROOT,
            env=dict(os.environ, QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),
            capture_output=True, text=True, timeout=10)
        (out / 'arm.log').write_text(checked.stdout + checked.stderr)
        assert checked.returncode == 0, checked.stdout + checked.stderr
        report.update(original_libc_arm=True, arm_stdout=checked.stdout,
            original_libc_sha256=hashlib.sha256(libraries['libc.so.6'].read_bytes()).hexdigest())
    inputs = [*sources, 'runtime/platform/player/owner_wait.h', 'tools/test_owner_wait.py']
    report['source_hashes'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                               for name in inputs}
    report['limits'] = ['Native GUI/RF and physical sleep are not executed.',
                        'The original-only baseline reproduces the wait seam, not a full device fault.']
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    print('Report:', out / 'report.json')


if __name__ == '__main__':
    main()
