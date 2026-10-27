"""Load-only static derivative checks the added BSS reservation; never runs Sony main."""
from pathlib import Path
import json,struct,subprocess,io,hashlib
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];area=ROOT/'work/external-language-bridge-10-process-cache-final';meta=json.loads((area/'report.json').read_text());raw=bytearray((ROOT/meta['artifact']).read_bytes());elf=ELFFile(io.BytesIO(raw));cache=int(meta['cache_address'],16);start=0x4da100
assembly=area/'layout-probe.S';assembly.write_text('''.syntax unified
.arch armv5te
.arm
.global probe
probe:
 ldr r0,cache_address
 mov r1,#0
1:
 ldr r2,[r0,r1]
 cmp r2,#0
 bne fail
 add r1,r1,#4
 cmp r1,#64
 blt 1b
 ldr r1,pattern
 str r1,[r0,#60]
 ldr r2,[r0,#60]
 cmp r1,r2
 bne fail
 mov r0,#0
 mov r7,#1
 svc #0
fail:
 mov r0,#1
 mov r7,#1
 svc #0
cache_address: .word '''+hex(cache)+'''
pattern: .word 0x12345678
''')
subprocess.run(['arm-linux-gnueabi-as',str(assembly),'-o',str(area/'layout-probe.o')],check=True)
subprocess.run(['arm-linux-gnueabi-ld','-Ttext='+hex(start),'-e','probe',str(area/'layout-probe.o'),'-o',str(area/'layout-stub.elf')],check=True)
subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(area/'layout-stub.elf'),str(area/'layout-stub.bin')],check=True)
stub=(area/'layout-stub.bin').read_bytes();loads=[s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'];assert len(loads)==2
for i,s in enumerate(loads):raw[elf['e_phoff']+32*i:elf['e_phoff']+32*(i+1)]=struct.pack('<8I',1,s['p_offset'],s['p_vaddr'],s['p_paddr'],s['p_filesz'],s['p_memsz'],s['p_flags'],s['p_align'])
struct.pack_into('<H',raw,44,2);struct.pack_into('<I',raw,24,start)
off=loads[0]['p_offset']+start-loads[0]['p_vaddr'];assert raw[off:off+len(stub)]==bytes(len(stub));raw[off:off+len(stub)]=stub
probe=area/'layout-probe.static-only.elf';probe.write_bytes(raw);probe.chmod(0o755)
r=subprocess.run(['qemu-arm',str(probe)],capture_output=True,timeout=10);assert r.returncode==0,(r.returncode,r.stderr)
report={'passed':True,'candidate_sha256':meta['sha256'],'fixture_sha256':hashlib.sha256(raw).hexdigest(),'probe_stub_bytes':len(stub),'cache_reserved_zero_and_writable':True,'probe_does_not_run_sony_main':True,'scope':'QEMU user ELF loader executes a test-only ARM stub in a static derivative preserving the two candidate PT_LOADs. No interpreter/dynamic initialization, Sony application main, hardware or process heap qualification. Shipping artifact unmodified.','physical_device_access':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(area/'layout-probe.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
