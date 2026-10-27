"""Replay stock libc stat64 wrappers with virtual OABI stat calls; offline only."""
from pathlib import Path
import gzip,hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
root=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(root).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(root)),mode='r:') as tar:binary=tar.extractfile('./lib/libc-2.3.3.so').read()
elf=ELFFile(io.BytesIO(binary));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};base=0x1000000
raw=bytearray(range(96));struct.pack_into('<Q',raw,0,0x1122334455667788);struct.pack_into('<I',raw,16,0x81a4);struct.pack_into('<I',raw,20,1);struct.pack_into('<q',raw,44,0x100001011);struct.pack_into('<Q',raw,88,0x123456789abcdef0);raw=bytes(raw)
rows=[]
for name,nr in [('__xstat64',195),('__lxstat64',196),('__fxstat64',197)]:
 for version,error in [(v,0) for v in range(5)]+[(3,5)]:
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD'];low=min(s['p_vaddr'] for s in segments)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
  u.mem_map(base+low,high-low)
  for segment in segments:u.mem_write(base+segment['p_vaddr'],segment.data())
  u.mem_map(0x60000000,0x20000);end=0x60000100;output=0x60002000;errno_cell=0x60001000;argument=42 if nr==197 else 0x60003000
  u.mem_write(output,b'\xa5'*128);u.mem_write(0x60003000,b'/fixture/app\0');requests=[]
  def code(uc,pc,size,unused):
   if pc!=base+symbols['__errno_location']:return
   uc.reg_write(UC_ARM_REG_R0,errno_cell);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  def intr(uc,interrupt,unused):
   pc=uc.reg_read(UC_ARM_REG_PC);instruction=struct.unpack('<I',uc.mem_read(pc-4,4))[0]
   assert instruction==0xef900000+nr
   assert uc.reg_read(UC_ARM_REG_R0)==argument
   destination=uc.reg_read(UC_ARM_REG_R1);assert destination!=output and 0x60010000<=destination<0x60020000
   requests.append({'OABI_number':nr,'temporary_buffer':True,'supplied_bytes':len(raw) if not error else 0})
   if not error:uc.mem_write(destination,raw)
   uc.reg_write(UC_ARM_REG_R0,(-error)&0xffffffff)
  u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,intr)
  for reg,value in ((UC_ARM_REG_R0,version),(UC_ARM_REG_R1,argument),(UC_ARM_REG_R2,output),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
  u.emu_start(base+symbols[name],end,count=10000);assert u.reg_read(UC_ARM_REG_PC)==end and len(requests)==1
  success=version==3 and not error;result=u.reg_read(UC_ARM_REG_R0);written=bytes(u.mem_read(output,128))
  if success:assert result==0 and written[:96]==raw and written[96:]==b'\xa5'*32
  else:
   expected_errno=error if error else 22
   assert result==0xffffffff and written==b'\xa5'*128 and struct.unpack('<I',u.mem_read(errno_cell,4))[0]==expected_errno
  rows.append({'function':name,'version':version,'supplied_kernel_errno':error,'success':success,'requests':requests,'output_guard_intact':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'libc_sha256':hashlib.sha256(binary).hexdigest(),'cases':rows,'observed_libc_stat64_copy_bytes':96,'accepted_sampled_version':3,'st_size_byte_offset_in_copy':44,'limits':['Actual stock libc instructions, but OABI syscall and errno accessor are virtual.','96-byte syscall payload is supplied; no real kernel stat or filesystem call is executed.','Converter copies96 bytes and preserves following guard; cannot substitute modern112-byte time64 structure.','No native installer link, target kernel layout qualification or device execution.']}
(ROOT/'sources/native-stock-libc-stat64.json').write_text(json.dumps(report,indent=2)+'\n');print('Stock libc stat64:',len(rows),'bounded checks passed; version3 copies96 bytes.')
