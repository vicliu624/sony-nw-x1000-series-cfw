"""Check production broker threads and close admission without accessing a device.

--host-only needs no Sony inputs or ARM tools. The default Linux profile also
checks original pthread primitive initialization; that ARM smoke creates no thread.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CORE = [
    'runtime/platform/player/client.c',
    'runtime/platform/player/local_identity.c',
    'runtime/platform/player/metadata_async.c',
]
HOST_SOURCES = [*CORE, 'runtime/platform/player/player_broker.c',
                'tools/fixtures/player_broker.c']
WARNINGS = ['-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation']


def run_checked(command, log, timeout):
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=timeout,
        env=dict(os.environ, QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),
    )
    log.write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'{command[0]} failed ({result.returncode}); see {log}\n'
                           + result.stdout + result.stderr)
    return result.stdout


def host_check(output):
    windows = os.name == 'nt'
    sources = list(HOST_SOURCES)
    if windows:
        sources.append('tools/fixtures/windows_pthread.c')
        flags = ['clang', '-std=c11', '-O1', '-D_CRT_SECURE_NO_WARNINGS']
    else:
        flags = ['gcc-12', '-std=c99', '-O1', '-fsanitize=address,undefined', '-pthread']
    binary = output / ('host.exe' if windows else 'host')
    subprocess.run([*flags, *WARNINGS, *sources, '-o', str(binary)], cwd=ROOT, check=True)
    stdout = run_checked([str(binary)], output / 'host.log', 30)
    return sources, stdout


def arm_primitive_check(output):
    sources = [*CORE,
               'runtime/platform/player/stock_media.c',
               'runtime/platform/player/stock_query.c',
               'runtime/platform/player/query_snapshot.c',
               'runtime/platform/player/media_text.c',
               'runtime/platform/player/stock_image.c',
               'runtime/native/sha256.c',
               'tools/fixtures/player_metadata_abi.c',
               'runtime/store/start.c', 'runtime/store/start.S']
    library = ROOT / 'work/arm-signal-tests/lib'
    extra = ROOT / 'work/player-sqlite-ro'
    libraries = [extra / 'libdl.so.2', extra / 'libpthread.so.0',
                 library / 'libc.so.6', library / 'ld-linux.so.3']
    binary = output / 'abi.arm'
    flags = ['arm-linux-gnueabi-gcc', '-std=c99', *WARNINGS, '-Os',
             '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-march=armv5te',
             '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-pie', '-nostdlib',
             '-no-pie', '-Wl,--hash-style=sysv', '-Wl,--dynamic-linker=/lib/ld-linux.so.3']
    subprocess.run([*flags, *sources, *map(str, libraries), '-lgcc', '-o', str(binary)],
                   cwd=ROOT, check=True)
    stdout = run_checked(
        ['qemu-arm', '-cpu', 'arm926', str(library / 'ld-linux.so.3'),
         '--library-path', str(extra) + ':' + str(library), str(binary)],
        output / 'arm.log', 15,
    )
    return sources, libraries, stdout


def windows_arm_compile_check(output):
    # Freestanding compile only: this does not execute original pthread methods.
    subprocess.run([
        'clang', '--target=armv5te-none-eabi', '-std=c99', '-Os',
        '-ffreestanding', '-fno-builtin',
        '-I' + str(ROOT / 'tools/fixtures/freestanding'), *WARNINGS,
        '-Wframe-larger-than=2048', '-fstack-usage', '-c',
        str(ROOT / 'runtime/platform/player/player_broker.c'),
        '-o', str(output / 'broker-arm-clang.o'),
    ], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-only', action='store_true')
    parser.add_argument('--output', type=Path, help='New result directory under work/')
    args = parser.parse_args()
    output = (args.output or ROOT / 'work/player-broker' / str(time.time_ns())).resolve()
    if not output.is_relative_to((ROOT / 'work').resolve()):
        parser.error('Output must stay under work/')
    output.mkdir(parents=True, exist_ok=False)
    sources, stdout = host_check(output)
    windows = os.name == 'nt'
    report = {
        'passed': True, 'host_only': args.host_only,
        'host': 'windows-win32-shim' if windows else 'linux-pthread',
        'host_sanitizers': not windows, 'supported_gnu_build': not windows,
        'real_host_worker': True, 'original_pthread_primitives': False,
        'sony_thread_created': False, 'device_accessed': False, 'firmware_created': False,
        'clock_loss_invalidates_metadata_catalog_queue': True,
        'closing_admission_checked': True, 'host_stdout': stdout,
        'limits': ['Native media/backend values are modeled; this does not qualify '
                   'Sony scheduling, RF, USB or physical sleep/wake.'],
    }
    if not args.host_only:
        if windows:
            windows_arm_compile_check(output)
        else:
            arm_sources, libraries, arm_stdout = arm_primitive_check(output)
            sources += arm_sources
            report.update(original_pthread_primitives=True, arm_stdout=arm_stdout)
            report['original_library_hashes'] = {
                path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in libraries
            }
    sources += ['runtime/platform/player/player_broker.h',
                'runtime/platform/player/metadata_async.h', 'tools/test_player_broker.py']
    if windows:
        sources += ['tools/fixtures/windows_pthread.h']
    report['source_hashes'] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in sorted(set(sources))
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('Report:', output / 'report.json')


if __name__ == '__main__':
    main()