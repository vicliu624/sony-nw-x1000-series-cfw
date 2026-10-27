"""Stock device-name factory routing; stop before constructor/allocation."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for name,target,entry in (('device.tuner',0x22e4f0,0x22e030),('device.avcdecoder',0x234408,0x22e030),('device.aacdecoder',0x238430,0x22e030),('unrecognized.device',0x6001f000,0x22e030),('device.avcdecoder',0x234408,0x1987d8)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segs:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000);u.mem_write(0x60002000,name.encode()+b'\0')
 comparisons=[]
 def string(p):return bytes(u.mem_read(p,80)).split(b'\0')[0].decode()
 def hook(uc,pc,size,data):
  if pc in (0x22e4f0,0x234408,0x238430,0x6001f000):uc.emu_stop();return
  if pc==symbols['strcmp']:
   a=string(uc.reg_read(UC_ARM_REG_R0));b=string(uc.reg_read(UC_ARM_REG_R1));comparisons.append([a,b])
   uc.reg_write(UC_ARM_REG_R0,((a>b)-(a<b))&0xffffffff)
   uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 u.reg_write(UC_ARM_REG_R0,0x60003000);u.reg_write(UC_ARM_REG_R1,0x60002000)
 u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
 u.emu_start(entry,0,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==target
 if target==0x6001f000:assert u.reg_read(UC_ARM_REG_R0)==0 and u.mem_read(0x60003000,4)==bytes(4)
 if entry==0x1987d8:assert u.reg_read(UC_ARM_REG_R6)==0x7faf1c
 rows.append({'entry':hex(entry),'name_fixture':name if entry==0x22e030 else None,'name_from_native_literal':name if entry==0x1987d8 else None,'native_destination':hex(target),'comparisons':comparisons,'output_pointer_at_constructor_boundary':hex(u.reg_read(UC_ARM_REG_R6)) if target!=0x6001f000 else None})
report={'input_sha256':digest,'entry':'0x22e030','cases':rows,
 'finding':'Stock name device.avcdecoder selects234408 ->2343b0, whose constructor assigns table4833b8 containing stop slot236be8.',
 'limits':['strcmp simulated from actual strings; execution stops at factory branch targets before allocation/constructor. Unknown name returns0/null in this sample.',
           'Four factory names supplied; extra1987d8 caller uses original name/output literals through19ca7c and native factory. That output destination is7faf1c; construction success, actual object write and APF lifecycle remain unproven.']}
(ROOT/'sources/native-spider-device-factory.json').write_text(json.dumps(report,indent=2)+'\n')
print('Five stock factory cases passed; native caller requests device.avcdecoder with output destination7faf1c, before construction')
