"""Replay stock final-presentation clear helper; no device commands or rendering backend."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for page in (0,1):
 for flags in (0,1,3):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
  low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
  u.mem_map(low,high-low)
  for s in segs:u.mem_write(s['p_vaddr'],s.data())
  u.mem_map(0x60000000,0x20000);u.mem_map(0x61000000,0xc0000)
  u.mem_write(0x61000000,b'\xa5'*0xc0000)
  state=[0]*34;state[1]=0x61000000;state[2]=0x61060000;state[7]=page
  u.mem_write(0x60001000,struct.pack('<34I',*state));calls=[]
  def hook(uc,pc,size,data):
   if pc==symbols['memset']:
    args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
    assert args==[0x61000000+page*0x60000,0,240*432*2]
    calls.append(args);uc.mem_write(args[0],bytes(args[2]))
    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,hook)
  u.reg_write(UC_ARM_REG_R0,0x60001000);u.reg_write(UC_ARM_REG_R1,flags)
  u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
  u.emu_start(0x14a470,0x6001f000,count=1000)
  assert u.reg_read(UC_ARM_REG_PC)==0x6001f000
  changed=bool(flags&1);assert len(calls)==int(changed)
  for p in (0,1):
   expected=(bytes(240*432*2)+b'\xa5'*(0x60000-240*432*2)) if changed and p==page else b'\xa5'*0x60000
   assert bytes(u.mem_read(0x61000000+p*0x60000,0x60000))==expected
  final=list(struct.unpack('<34I',u.mem_read(0x60001000,136)))
  expected=state[:]
  if changed:expected[8]=255;expected[9]=1
  assert final==expected
  rows.append({'selected_page_fixture':page,'flags':flags,'clear_calls':calls,'other_page_and_padding_unchanged':True})
report={'input_sha256':digest,'entry':'0x14a470','cases':rows,'finding':'Flag1 clears selected visible page to zero and sets alpha255/tc_enable1. Flag0 does nothing; flag3 takes the same direct clear branch.',
        'limits':['Selected page/pointers are fixtures; memset is simulated. No page readiness query, submit, display completion or panel behavior.',
                  'Stock close calls115f68(1)/11600c twice, but this helper test alone does not prove which two pages are selected or why two submissions are necessary.']}
(ROOT/'sources/native-display-clear-page.json').write_text(json.dumps(report,indent=2)+'\n')
print('Six stock selected-page clear cases passed; zero visible bytes, untouched other page/padding; no drain claim')
