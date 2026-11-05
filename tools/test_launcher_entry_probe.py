"""Execute exact entry-probe ARM instructions with bounded filesystem models."""
import argparse,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_PC
from app_registry import ROOT
from review_managed_remote_profile import receipt,artifact,digest
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',required=True);args=parser.parse_args()
rp,build=receipt(args.review);binary=ROOT/build['artifact'];artifact(binary,build['sha256'],build['bytes'])
header=bytes.fromhex(build['header_hex']);raw=binary.read_bytes();rows=[]
trace='/contents/HOMEBREW/data/diagnostics/entry-boundary.bin'
for case in ('valid','wrong-mount','nested-mount','wrong-header','missing-trace','symlink-trace','readonly','short-write','fsync-error'):
 mounts=b'rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\n'
 if case=='wrong-mount':mounts=mounts.replace(b'/dev/mtdblock/2 /contents vfat',b'/dev/mtdblock/1 /contents ext2')
 if case=='nested-mount':mounts+=b'/dev/mtdblock/1 /contents/HOMEBREW ext2 rw 0 0\n'
 data=bytearray(header+bytes(96))
 if case=='wrong-header':data[0]^=1
 initial=bytes(data);positions={10:0,11:0};writes=[];opened=[];calls=[];exit_code=[]
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in ELFFile(io.BytesIO(raw)).iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  base=segment['p_vaddr']&~4095;size=(segment['p_vaddr']-base+segment['p_memsz']+4095)&~4095
  u.mem_map(base,size);u.mem_write(segment['p_vaddr'],segment.data())
 u.mem_map(0x70000000,65536);u.reg_write(UC_ARM_REG_SP,0x7000fff0)
 def string(address):return bytes(u.mem_read(address,256)).split(b'\0')[0].decode()
 def interrupt(uc,event,unused):
  pc=uc.reg_read(UC_ARM_REG_PC);instruction=struct.unpack('<I',uc.mem_read(pc-4,4))[0]
  assert instruction&0xffff0000==0xef900000,hex(instruction)
  number=(instruction&0xffffff)-0x900000;calls.append(number)
  a,b,c=[uc.reg_read(reg) for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
  if number==1:exit_code.append(a);uc.emu_stop();return
  if number==5:
   path=string(a);opened.append(path)
   assert path in ('/proc/mounts',trace),path
   if path=='/proc/mounts':assert b==0;result=10
   else:
    assert b==(2|0o100000|0o4000)
    result=-2 if case=='missing-trace' else -40 if case=='symlink-trace' else -30 if case=='readonly' else 11
  elif number==3:
   content=mounts if a==10 else bytes(data);start=positions[a];block=content[start:start+c]
   uc.mem_write(b,block);positions[a]+=len(block);result=len(block)
  elif number==19:
   assert a==11 and c in (0,2);positions[a]=b if c==0 else len(data)+b;result=positions[a]
  elif number==4:
   assert a==11 and positions[a]==32 and c==64
   payload=bytes(uc.mem_read(b,c));assert payload[:8]==b'ENTERED1' and payload[56:]==b'COMMIT01'
   writes.append(payload);result=32 if case=='short-write' else 64
   data[positions[a]:positions[a]+result]=payload[:result];positions[a]+=result
  elif number==20:result=4321
  elif number==118:assert a==11;result=-5 if case=='fsync-error' else 0
  elif number==6:assert a in (10,11)
  else:raise AssertionError(('Unexpected syscall',number))
  uc.reg_write(UC_ARM_REG_R0,result&0xffffffff)
 u.hook_add(UC_HOOK_INTR,interrupt)
 u.emu_start(ELFFile(io.BytesIO(raw))['e_entry'],0,count=500000)
 expected={'valid':0,'wrong-mount':71,'nested-mount':71,'missing-trace':72,'symlink-trace':72,'readonly':72,'wrong-header':73,'short-write':75,'fsync-error':76}[case]
 assert exit_code==[expected],(case,exit_code)
 assert len(data)==128 and data[:32]==initial[:32] and data[96:]==initial[96:]
 assert len(writes)==int(case in ('valid','short-write','fsync-error'))
 if not writes:assert bytes(data)==initial
 if case=='short-write':assert bytes(data[88:96])!=b'COMMIT01'
 rows.append(dict(case=case,exit=expected,write_attempts=len(writes),max_write_bytes=64 if writes else 0,syscalls=sorted(set(calls))))
report=dict(passed=True,artifact_sha256=build['sha256'],cases=rows,device_executed=False,device_written=False,
 source_hashes={'tools/test_launcher_entry_probe.py':digest(ROOT/'tools/test_launcher_entry_probe.py')},
 limits=['Exact ARM/OABI instructions execute, filesystem and kernel syscall results are modeled.',
 'This validates diagnostic bounds/refusals, not Sony application switching or a Homebrew fix.'])
(rp.parent/'checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
