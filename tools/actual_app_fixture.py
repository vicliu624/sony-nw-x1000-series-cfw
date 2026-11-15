"""Prepare verified QEMU virtual devices without running a launcher or app."""

import json
from pathlib import Path
import subprocess
import tempfile
import os

from component_receipts import ROOT, artifact, digest, receipt
from workflow_paths import composition_path, work_area


def stock_libc():
    library = ROOT / 'work/arm-signal-tests/lib'
    for name, expected in {
        'libc.so.6': '5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
        'ld-linux.so.3': '2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
    }.items():
        if digest(library / name) != expected:
            raise ValueError('Stock library identity differs: ' + name)
    return library


def build_device_preload():
    library = stock_libc()
    sources = ['tools/fixtures/device_preload.c', 'runtime/native/syscalls.S']
    tracked = [Path(__file__), *(ROOT / name for name in sources),
               ROOT / 'runtime/native/font.inc', library / 'libc.so.6', library / 'ld-linux.so.3']
    source_hashes = {path.relative_to(ROOT).as_posix(): digest(path) for path in tracked}
    area = Path(tempfile.mkdtemp(prefix='build-', dir=work_area(ROOT, 'virtual-device-preload')))
    preload = area / 'virtual-devices.so'
    subprocess.run([
        'arm-linux-gnueabi-gcc', '-D_GNU_SOURCE', '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror',
        '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-stack-protector', '-fPIC',
        '-shared', '-nostdlib', '-Wl,--build-id=none', '-Wl,--hash-style=sysv', '-Wl,-soname,virtual-devices.so',
        *sources, str(library / 'libc.so.6'), '-lgcc', '-o', str(preload),
    ], cwd=ROOT, check=True)
    if any(digest(ROOT / name) != expected for name, expected in source_hashes.items()):
        raise ValueError('Virtual-device inputs changed during compilation')
    report = dict(passed=True, bytes=preload.stat().st_size, sha256=digest(preload),
                  source_hashes=source_hashes)
    path = area / 'build.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return path


def prepare():
    composition = composition_path(ROOT)
    manifest = json.loads((composition / 'manifest.json').read_text(encoding='utf-8'))
    launcher = 'external/HOMEBREW/launcher/app'
    app = composition / launcher
    row = next(item for item in manifest['files'] if item['path'] == launcher)
    artifact(app, row['sha256'], row['bytes'])
    if any(Path(node).exists() for node in ('/dev/fb/0', '/dev/icx_touch_screen')):
        raise RuntimeError('Virtual-device tests require a development host without Sony device nodes')
    library = stock_libc()
    selected = os.environ.get('HB_WORKFLOW_PRELOAD_REVIEW') or build_device_preload()
    review_path, report = receipt(selected)
    if report.get('passed') is not True or Path(__file__).relative_to(ROOT).as_posix() not in report['source_hashes']:
        raise ValueError('Expected a verified virtual-device build')
    preload = review_path.parent / 'virtual-devices.so'
    artifact(preload, report['sha256'], report['bytes'])
    return dict(composition=composition, manifest=manifest, app=app, preload=preload, lib=library,
                inputs=[review_path, *(ROOT / name for name in report['source_hashes'])])
