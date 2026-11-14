"""Exercise cancellation at real SDK storage admission/publication boundaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from app_registry import ROOT
from sdk_build import COMMON, NATIVE


def main():
    area = ROOT / 'work/sdk-storage-stop' / str(time.time_ns())
    area.mkdir(parents=True)
    flags = ['-std=gnu99', '-Os', '-Wall', '-Wextra', '-Werror',
             '-Wno-misleading-indentation', '-D_DEFAULT_SOURCE', '-D_FORTIFY_SOURCE=0',
             '-fno-builtin', '-I' + str(ROOT / 'sdk/include')]
    common = [ROOT / p for p in COMMON if not p.endswith('entry.c')]
    fixture = ROOT / 'sdk/tests/storage_stop.c'
    host = area / 'host'
    subprocess.run(['gcc', *flags, '-DXW_HOST', str(fixture), *map(str, common),
                    '-o', str(host)], cwd=ROOT, check=True)
    lib = ROOT / 'work/arm-signal-tests/lib'
    arm = area / 'arm'
    subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-march=armv5te', '-marm',
                    '-mfloat-abi=soft', '-fno-pie', '-fno-stack-protector',
                    '-DHB_STORE_SONY_LIBC', '-DHB_USE_POSIX_DEVICE_IO', str(fixture),
                    *map(str, common), *[str(ROOT / p) for p in NATIVE], '-nostdlib',
                    '-no-pie', '-Wl,--hash-style=sysv,--dynamic-linker=/lib/ld-linux.so.3',
                    str(lib / 'libc.so.6'), str(lib / 'ld-linux.so.3'), '-lgcc', '-o', str(arm)],
                   cwd=ROOT, check=True)
    cases = ('live', 'unbound', 'owner-stop', 'backend-stop', 'backend-owner-stop',
             'owner-deny', 'owner-replace', 'context-replace', 'registration-stop')
    rows = []
    env = dict(os.environ, QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    for profile in ('host', 'arm'):
        selected = cases + (('signal-owner-stop', 'signal-registration-stop') if profile == 'arm' else ())
        for name in selected:
            if profile == 'host':
                data = area / name
                data.mkdir()
                command = [str(host), name, str(data)]
            else:
                command = ['qemu-arm', '-cpu', 'arm926', str(lib / 'ld-linux.so.3'),
                           '--library-path', str(lib), str(arm), name]
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
            log = area / (profile + '-' + name + '.log')
            log.write_text(result.stdout + result.stderr, encoding='utf-8')
            rows.append({'profile': profile, 'case': name, 'passed': result.returncode == 0,
                         'exit_code': result.returncode, 'log': log.relative_to(ROOT).as_posix()})
    inputs = [fixture, Path(__file__), *common, *[ROOT / p for p in NATIVE],
              ROOT / 'sdk/include/x1000/storage.h', ROOT / 'runtime/platform/sdk/internal.h', ROOT / 'sdk/VERSION']
    report = {'passed': all(row['passed'] for row in rows), 'cases': rows,
              'sdk_version': (ROOT / 'sdk/VERSION').read_text(encoding='utf-8').strip(),
              'device_accessed': False, 'firmware_created': False,
              'source_hashes': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in inputs}}
    (area / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'report': (area / 'report.json').relative_to(ROOT).as_posix(),
                      'failed': [row for row in rows if not row['passed']]}, indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
