"""Real Sony loader/preload symbol binding and foreign select delegation; no device."""
import hashlib
import json
import os
import subprocess
import time
from build_player_host import ROOT, CORE_SOURCES
from player_arm_guest import stock_libraries

out = ROOT / 'work/owner-wait-loader' / str(time.time_ns())
out.mkdir(parents=True)
libraries = stock_libraries(include_dl=True, include_rt=True)
linked = [str(path) for path in libraries.values()]
flags = ['arm-linux-gnueabi-gcc', '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror',
         '-Wno-misleading-indentation', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
         '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin',
         '-fno-stack-protector', '-nostdlib', '-Wl,--hash-style=sysv,--build-id=none']
sources = [*CORE_SOURCES, 'runtime/platform/player/owner_wait.c',
           'tools/fixtures/owner_wait_loader_stub.c']
library = out / 'libowner-wait.so'
subprocess.run([*flags, '-DXW_PLAYER_REMOTE_FACTORY', '-fPIC', '-fvisibility=hidden',
                '-shared', '-Wl,-z,defs', *sources, *linked, '-lgcc', '-o', str(library)],
               cwd=ROOT, check=True)
consumer = 'tools/fixtures/owner_wait_loader.c'
startup = ['runtime/store/start.c', 'runtime/store/start.S']
binary = out / 'consumer.arm'
subprocess.run([*flags, '-fno-pie', '-no-pie', consumer, *startup, *linked,
                '-lgcc', '-o', str(binary)], cwd=ROOT, check=True)
env = dict(os.environ, QEMU_UNSET_ENV='LD_LIBRARY_PATH')
env.pop('LD_PRELOAD', None)
paths = ':'.join(dict.fromkeys(str(path.parent) for path in libraries.values()))
run = subprocess.run(['qemu-arm', '-cpu', 'arm926', '-E', 'LD_PRELOAD=' + str(library),
    str(libraries['ld-linux.so.3']), '--library-path', paths, str(binary)], cwd=ROOT,
    env=env, capture_output=True, text=True, timeout=15)
(out / 'loader.log').write_text(run.stdout + run.stderr)
assert run.returncode == 0 and 'OWNER_WAIT_LOADER_PASS' in run.stdout, run.stdout + run.stderr
report = dict(passed=True, original_loader_libc=True, real_preload_select_binding=True,
    foreign_native_io_preserved=True, factory_registration_stub=True,
    device_accessed=False, firmware_created=False, stdout=run.stdout,
    source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                   for name in [*sources, consumer, *startup, 'runtime/platform/player/owner_wait.h',
                                'tools/test_owner_wait_loader.py']},
    original_library_hashes={path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in libraries.values()},
    limits=['Minimal owner DSO with inactive factory; not a full production composition.',
            'Native GUI callsite/readiness qualification is checked separately; no Sony kernel/RF.'])
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
print('Report:', out / 'report.json')
