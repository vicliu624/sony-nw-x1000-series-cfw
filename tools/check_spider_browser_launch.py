"""Replay stock SpiderApp WLAN request callback; virtual network/log/event services."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
b=(ROOT/'work/targets-jp/SpiderApp').read_bytes();sha=hashlib.sha256(b).hexdigest()
assert sha=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
e=ELFFile(io.BytesIO(b));rows=[]
for lookup_result,change_result in ((0,0),(0x111,0),(0,5)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x800000)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x10000);stop=0x1000100;lookups=[];changes=[]
 def hook(uc,pc,size,unused):
  if pc not in (0x265510,0xb00bc,0x33b918,0x33b83c,0x2664d0,0x2681e8,0x26534c,0xd85c):return
  args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  result=0
  if pc==0x265510:result=0x1001000
  elif pc==0xd85c:uc.mem_write(args[0],bytes(uc.mem_read(args[1],args[2])));result=args[0]
  elif pc==0x2664d0:
   name=bytes(uc.mem_read(args[1],128)).split(b'\0')[0].decode();assert name=='netfront';lookups.append(name)
   if lookup_result==0:uc.mem_write(args[2],struct.pack('<I',0x20001))
   result=lookup_result
  elif pc==0x2681e8:
   from unicorn.arm_const import UC_ARM_REG_R3
   vector=struct.unpack('<2I',uc.mem_read(args[2],8));assert vector==(0x693198,0)
   argument=bytes(uc.mem_read(vector[0],512)).split(b'\0')[0].decode()
   changes.append({'target_id':hex(args[1]),'arguments_pointer':hex(args[2]),'mode':uc.reg_read(UC_ARM_REG_R3),'arguments':[argument]})
   result=change_result
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,3);u.reg_write(UC_ARM_REG_SP,0x100f000);u.reg_write(UC_ARM_REG_LR,stop)
 u.emu_start(0xb0108,stop,count=1000);assert u.reg_read(UC_ARM_REG_PC)==stop
 url='https://example.invalid/homebrew';u.mem_write(0x1002000,url.encode()+bytes(512-len(url)))
 u.reg_write(UC_ARM_REG_R0,0x1002000);u.reg_write(UC_ARM_REG_LR,stop);u.reg_write(UC_ARM_REG_SP,0x100f000)
 u.emu_start(0xb19bc,stop,count=1000);assert u.reg_read(UC_ARM_REG_PC)==stop
 u.reg_write(UC_ARM_REG_R0,3);u.reg_write(UC_ARM_REG_LR,stop);u.reg_write(UC_ARM_REG_SP,0x100f000)
 u.emu_start(0xb0464,stop,count=2000);assert u.reg_read(UC_ARM_REG_PC)==stop
 assert lookups==['netfront'] and len(changes)==int(lookup_result==0)
 if changes:assert changes[0]=={'target_id':'0x20001','arguments_pointer':'0x693398','mode':0,'arguments':[url]}
 rows.append({'supplied_lookup_result':lookup_result,'supplied_change_result':change_result,'lookups':lookups,'change_requests':changes})
report={'SpiderApp_sha256':sha,'entry':'0xb0464','input':3,'all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Original frontend wrapper chooses netfront name and constructs change arguments; lookup/change service and diagnostics are virtual.','Lookup success returns stock-config target0x20001 as fixture; manager registration/transport and actual launching are not replayed.','Original vector initialization and512-byte URL setter execute with a host sample URL; actual browser delivery and navigation are not established.','Action3 here belongs to this wrapper; it must not be confused with network-parent input13 or an application ID.']}
(ROOT/'sources/native-spider-browser-launch.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


