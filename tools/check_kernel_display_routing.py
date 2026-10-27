"""Original kernel QFB ioctl routing only; stop before case body/hardware."""
from pathlib import Path
import hashlib,io,json
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
analysis=(ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes();elf=ELFFile(io.BytesIO(analysis))
assert elf.get_section_by_name('.kernel').data()==raw
rows=[]
for request,expected in ((0x40044e01,0xc01023f8),(0x80044e00,0xc01021d4),(0x80044e04,0xc0102680),(0x4e01,0xc01032e0)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':
   base=s['p_vaddr']&~4095;size=((s['p_vaddr']+s['p_memsz']+4095)&~4095)-base
   u.mem_map(base,size);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000)
 def hook(uc,pc,size,data):
  if pc in (0xc01023f8,0xc01021d4,0xc0102680,0xc01032e0):uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook)
 u.reg_write(UC_ARM_REG_R2,request);u.reg_write(UC_ARM_REG_R3,0x60001000);u.reg_write(UC_ARM_REG_SP,0x60018000)
 u.emu_start(0xc0101f80,0,count=1000)
 assert u.reg_read(UC_ARM_REG_PC)==expected
 rows.append({'request':hex(request),'native_dispatch_destination':hex(expected)})
report={'kernel_sha256':digest,'analysis_sha256':hashlib.sha256(analysis).hexdigest(),'entry':'0xc0101f80','cases':rows,'limits':['Original dispatch instructions only; stop before argument copying, locks, device state or MMIO.','Destination32e0 is the common default exit, not an asserted error return.','No driver execution, frame presentation or hardware qualification.']}
(ROOT/'sources/native-kernel-display-routing.json').write_text(json.dumps(report,indent=2)+'\n')
print('Four stock kernel QFB routes verified; actual submit and legacy header request take different paths')
