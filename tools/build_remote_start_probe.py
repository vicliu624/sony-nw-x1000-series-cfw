"""Build a private read-only queue probe for the current hardware-test UPG."""
import hashlib
import io
import json
import os
import subprocess
import tarfile
import time

from elftools.elf.elffile import ELFFile

from app_registry import ROOT
from player_arm_guest import stock_libraries
from prepare_managed_firmware_review import unpack

kit = ROOT/'work/startup-candidate-materials/1793858639057351161/01_PC_UPDATE/NW_WM_FW.UPG'
firmware = kit.read_bytes()
firmware_sha = hashlib.sha256(firmware).hexdigest()
assert firmware_sha == '2328d7375e1c1a87b4ff8e1cd77a8bf6d06be0e6498fff953692a7651abb410e'
_, parts = unpack(firmware, require_stock=False)
with tarfile.open(fileobj=io.BytesIO(parts[3]), mode='r:gz') as archive:
    library = archive.extractfile('./usr/local/lib/libx1000-player.so').read()
digest = hashlib.sha256(library).hexdigest()
assert digest == 'ffa5eb99400b8bf7368031e6768e20b4d5231737d2b32192c2eb7c9e978af269'
elf = ELFFile(io.BytesIO(library))
symbols = elf.get_section_by_name('.symtab').get_symbol_by_name('settings')
assert len(symbols) == 1 and (symbols[0]['st_value'],symbols[0]['st_size']) == (0x4a188,56)
# ARM32 queue layout from host_managed_service.c and the pinned accessor:
# skip pointers/alignment, then serial through busy (40 bytes).
offset = symbols[0]['st_value'] + 16
out = ROOT/'work/remote-start-probe'/str(time.time_ns())
out.mkdir(parents=True)
header = out/'remote_start_probe_profile.h'
header.write_text(f'#define WR_PROBE_QUEUE_OFFSET {offset}u\n'
                  f'#define WR_PROBE_LIBRARY_BYTES {len(library)}u\n'
                  '#define WR_PROBE_LIBRARY_SHA256 {'+','.join('0x'+digest[i:i+2] for i in range(0,64,2))+'}\n')
source = 'runtime/apps/diagnostics/remote_start_probe.c'
binary = out/'remote-start-probe.arm'
libs = stock_libraries()
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror',
                '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft',
                '-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-I'+str(out),
                '-Wl,--hash-style=sysv,--build-id=none',source,'runtime/native/sha256.c',
                'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),
                str(libs['ld-linux.so.3']),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
command = ['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',
           str(libs['libc.so.6'].parent),str(binary)]
for argument, code, label in (('--help',0,'pinned player library'),('abc',64,''),('1',65,'IDENTITY_REFUSED')):
    run = subprocess.run([*command,argument],capture_output=True,text=True,timeout=10,
                         env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'))
    assert run.returncode == code and label in run.stdout
report = dict(artifact=binary.relative_to(ROOT).as_posix(),bytes=binary.stat().st_size,
              sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),firmware_sha256=firmware_sha,
              library_sha256=digest,queue_offset=offset,queue_read_bytes=40,
              original_libc_smoke_and_refusal_passed=True,device_accessed=False,
              live_proc_memory_permission_verified=False)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
