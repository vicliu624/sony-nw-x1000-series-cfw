"""Compile the real seven-bit SDK client from Git and connect it to the new host."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import posixpath
import re
import selectors
import subprocess
import time
from app_registry import ROOT

REVISION = '161a3d5450f57f9a29ff7a09cf22f4a119cd93b5'
out = ROOT / 'work/player-hello-compat' / str(time.time_ns())
out.mkdir(parents=True)
legacy = out / 'legacy-source'
sources = ['runtime/platform/player/' + name + '.c' for name in ('client', 'rpc_wire', 'rpc_posix')]
copied = {}
def freeze(name):
    if name in copied:
        return
    if name.startswith('../') or PurePosixPath(name).is_absolute():
        raise ValueError('Source include escaped project')
    data = subprocess.check_output(['git', 'show', REVISION + ':' + name], cwd=ROOT)
    copied[name] = hashlib.sha256(data).hexdigest()
    destination = legacy / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    for include in re.findall(rb'^\s*#\s*include\s*"([^"]+)"', data, re.MULTILINE):
        freeze(posixpath.normpath(str(PurePosixPath(name).parent / include.decode())))
for source in sources:
    freeze(source)
managed_sources = ['runtime/platform/player/' + name + '.c' for name in
                   ('managed_remote', 'managed_client', 'managed_codec', 'managed_clock')]
for source in managed_sources:
    freeze(source)
fixture = 'tools/fixtures/hello_compat_endpoint.c'
old_fixture = legacy / fixture
old_fixture.parent.mkdir(parents=True, exist_ok=True)
old_fixture.write_bytes((ROOT / fixture).read_bytes())
flags = ['-std=c99', '-O1', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation', '-pthread']
current = out / 'current'
old = out / 'old-client'
old_managed = out / 'old-managed-client'
managed_server = out / 'managed-server'
subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', *sources, fixture, '-o', str(current)], cwd=ROOT, check=True)
subprocess.run(['gcc-12', *flags, '-DXW_HELLO_LEGACY_CLIENT',
                *(str(legacy / p) for p in sources), str(old_fixture), '-o', str(old)], cwd=ROOT, check=True)
subprocess.run(['gcc-12', *flags, '-DXW_HELLO_LEGACY_CLIENT', '-DXW_HELLO_MANAGED_CLIENT',
                *(str(legacy / p) for p in sources + managed_sources), str(old_fixture),
                '-o', str(old_managed)], cwd=ROOT, check=True)
host_sources = ['runtime/platform/services/' + name + '.c' for name in ('session', 'request', 'events')]
host_sources += ['runtime/platform/player/' + name + '.c' for name in
                 ('client', 'managed', 'managed_rpc', 'rpc_wire', 'managed_channel',
                  'managed_control', 'managed_codec', 'managed_remote', 'managed_client', 'managed_clock')]
host_sources += ['tools/fixtures/player_host_clock.c', 'tools/fixtures/service_channel.c']
subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', *host_sources,
                '-o', str(managed_server)], cwd=ROOT, check=True)
endpoint = 'xw-hello-compat-' + str(os.getpid())
process = subprocess.Popen([str(current), '--server', endpoint], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, cwd=ROOT)
try:
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    assert selector.select(5), 'Server readiness not observed'
    assert process.stdout.readline().strip() == 'READY'
    runs = []
    for binary, option in ((old, '--client'), (current, '--probes')):
        run = subprocess.run([str(binary), option, endpoint], cwd=ROOT, capture_output=True,
                             text=True, timeout=20)
        runs.append(dict(binary=binary.name, option=option, exit=run.returncode, stdout=run.stdout, stderr=run.stderr))
        assert run.returncode == 0, run.stdout + run.stderr
    process.terminate()
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, stdout + stderr
    operations = re.findall(r'^COMMAND (\d+) (-?\d+)$', stdout, re.MULTILINE)
    assert [int(row[0]) for row in operations] == list(range(7)), stdout
    (out / 'server.log').write_text(stdout + stderr, encoding='utf-8')
finally:
    if process.poll() is None:
        process.terminate()
        process.communicate(timeout=5)
managed_run = subprocess.run([str(managed_server), str(old_managed), '--managed'], cwd=ROOT,
                             capture_output=True, text=True, timeout=20)
assert managed_run.returncode == 0 and 'FROZEN_7BIT_MANAGED_CLIENT_PASS' in managed_run.stdout, managed_run.stdout + managed_run.stderr
runs.append(dict(binary='managed-server + old-managed-client', exit=managed_run.returncode,
                 stdout=managed_run.stdout, stderr=managed_run.stderr))
inputs = sources + managed_sources + host_sources + [fixture, 'runtime/platform/player/rpc_wire.h',
                    'runtime/platform/player/player.h', 'tools/test_player_hello_compat.py']
report = dict(passed=True, frozen_revision=REVISION, frozen_client_command_count=7,
              real_unix_sockets=True, fragmented_explicit_hello=True, old_operations=list(range(7)),
              device_accessed=False, frozen_source_hashes=copied, runs=runs,
              source_hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs},
              limits=['Old client is compiled from retained source, not an installed device app.',
                      'Host sanitizers and synthetic player; no original OS, RF or audio execution.'])
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(passed=True, report=str(out / 'report.json'), runs=runs), indent=2))
