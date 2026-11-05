"""Build a private one-shot OABI entry marker; never installs or executes it."""
import hashlib,json,secrets,subprocess,time
from pathlib import Path
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
out=ROOT/'work/launcher-entry-probe'/str(time.time_ns());out.mkdir(parents=True)
header=b'X1ENTRYPROBE0001'+secrets.token_bytes(16);assert len(header)==32
(out/'entry_probe_profile.h').write_text('#define ENTRY_PROBE_HEADER {'+','.join(str(x) for x in header)+'}\n')
seed=header+bytes(96);(out/'entry-boundary.bin').write_bytes(seed)
sources=['runtime/apps/diagnostics/launcher_entry_probe.c','runtime/native/entry_start.S','runtime/native/syscalls.S','runtime/native/support.c']
binary=out/'entry-probe.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-static','-no-pie','-Wl,--build-id=none,-Ttext-segment=0x10000,-e,_start','-I',str(out),*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
with binary.open('rb') as f:
 elf=ELFFile(f);assert elf['e_machine']=='EM_ARM' and elf['e_type']=='ET_EXEC'
 assert all(segment['p_type']!='PT_INTERP' for segment in elf.iter_segments())
report=dict(built=True,artifact=binary.relative_to(ROOT).as_posix(),bytes=binary.stat().st_size,
 sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),header_hex=header.hex(),seed_sha256=hashlib.sha256(seed).hexdigest(),
 device_executed=False,device_written=False,installed=False,firmware_created=False,
 trace_path='/contents/HOMEBREW/data/diagnostics/entry-boundary.bin',trace_file_bytes=128,max_trace_write_bytes=64,
 needs_explicit_diagnostic_execution=True,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'tools/build_launcher_entry_probe.py']},
 limits=['Unstarted or absent marker does not by itself prove no execution: mount/header/IO validation may refuse.',
 'This probe exits without opening Sony UI; success proves process entry only, not a functioning launcher or firmware.'])
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(directory=out.relative_to(ROOT).as_posix(),**report),indent=2))
