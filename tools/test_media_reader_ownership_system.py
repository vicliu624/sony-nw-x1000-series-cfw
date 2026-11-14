"""Run media ownership faults with original Sony LinuxThreads in an offline ARM guest."""
import hashlib
import json
import subprocess
import time
from app_registry import ROOT
from player_arm_guest import stock_libraries, run_guest

out = ROOT / 'work/media-reader-ownership-system' / str(time.time_ns())
out.mkdir(parents=True)
libraries = stock_libraries()
sources = ['runtime/platform/player/metadata_async.c',
           'runtime/platform/player/local_identity.c',
           'tools/fixtures/media_reader_ownership.c']
startup = ['runtime/store/start.c', 'runtime/store/start.S']
init_source = 'tools/fixtures/player_worker_system_init.c'
flags = ['arm-linux-gnueabi-gcc', '-std=c99', '-O1', '-Wall', '-Wextra', '-Werror',
         '-Wno-misleading-indentation', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
         '-march=armv5te', '-marm', '-mfloat-abi=soft', '-ffreestanding', '-fno-builtin',
         '-fno-stack-protector', '-fno-pie', '-no-pie', '-nostdlib',
         '-Wl,--hash-style=sysv,--build-id=none', '-Wl,--dynamic-linker=/lib/ld-linux.so.3']
app, init = out / 'ownership.arm', out / 'init.arm'
subprocess.run([*flags, '-Wl,--wrap=pthread_create', *sources, *startup,
                str(libraries['libpthread.so.0']), str(libraries['libc.so.6']),
                str(libraries['ld-linux.so.3']), '-lgcc', '-o', str(app)], cwd=ROOT, check=True)
subprocess.run([*flags, init_source, *startup, str(libraries['libc.so.6']),
                str(libraries['ld-linux.so.3']), '-lgcc', '-o', str(init)], cwd=ROOT, check=True)
markers = ['MEDIA_READER_CASE_PASS scenario=' + str(i) for i in range(5)]
markers += ['MEDIA_READER_OWNERSHIP_PASS', 'PLAYER_WORKER_CHILD_STATUS=0']
report = run_guest(out, init, {'test': app}, libraries, markers)
report.update(device_accessed=False, native_media_modeled=True,
              original_sony_linuxthreads=True, ownership_fault_cases=5,
              source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in [*sources, *startup, init_source,
                                          'runtime/platform/player/metadata_async.h',
                                          'tools/test_media_reader_ownership_system.py']})
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
