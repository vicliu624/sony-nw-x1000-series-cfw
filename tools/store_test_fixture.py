"""Build independent Store test inputs in temporary host storage."""

import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FS_DRIVER_SOURCES = (
    'runtime/store/fs_posix.c', 'runtime/store/transaction.c', 'runtime/store/package.c',
    'runtime/native/sha256.c', 'tools/test_store_fs_driver.c',
)


def workspace(prefix):
    base = ROOT / 'work'
    base.mkdir(exist_ok=True)
    if base.resolve() != base:
        raise ValueError('Store fixtures require a local work directory')
    return tempfile.TemporaryDirectory(prefix=prefix, dir=base)


def build_fs_driver(work):
    subprocess.run([
        'gcc', '-DHB_STORE_HOST_FIXTURE', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
        *FS_DRIVER_SOURCES, '-o', str(work / 'driver'),
    ], cwd=ROOT, check=True)


def make_legacy_package(folder, revision):
    folder.mkdir(exist_ok=True)
    program = bytearray(96)
    program[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HH', program, 16, 2, 40)
    program[-1] = revision
    (folder / 'app').write_bytes(program)
    fields = dict(api='1', id='demo', name='Demo', version=f'0.1.{revision}',
                  target='sony-nw-x1000-jp', exec='app', bytes='96',
                  sha256=hashlib.sha256(program).hexdigest())
    (folder / 'app.ini').write_text(''.join(f'{key}={value}\n' for key, value in fields.items()), encoding='utf-8')
    return bytes(program)
