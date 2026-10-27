"""Original LCD IRQ ->qfb_callback over virtual register memory; no device interrupts."""
from pathlib import Path
import hashlib,io,json,struct,itertools
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_CPSR
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
a=(ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes();elf=ELFFile(io.BytesIO(a));assert elf.get_section_by_name('.kernel').data()==raw
rows=[]
for page,pending,mode,bits in itertools.product((0,1),(0,1),(0,1),(0,4,8,12)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':
   low=s['p_vaddr']&~4095;high=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(low,high-low);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 for p,v in ((0xc02c2d64,0x60005000),(0x60005060,pending),(0x60005044,bits),(0xc02c2f24,mode),(0xc02c2e80,page),(0xc02c28e0,0xffffffff),(0xc02c2d84,0)):
  put(p,v)
 services=[];callbacks=[]
 def hook(uc,pc,size,data):
  if pc==0xc0101680:callbacks.append(uc.reg_read(UC_ARM_REG_R0))
  if pc in (0xc01056a4,0xc004ffa8,0xc0042f90):
   services.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 u.reg_write(UC_ARM_REG_CPSR,0x13);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(0xc01042c8,0x50000000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==1
 expected=bool(pending and bits==(4 if mode==0 else 8))
 assert callbacks==([page] if expected else [])
 assert word(0xc02c28e0)==(page if expected else 0xffffffff)
 assert word(0x60005070)==pending
 assert ('0xc01056a4' in services)==expected
 rows.append({'page_fixture':page,'pending_register_fixture':pending,'mode_fixture':mode,'status_bits_fixture':bits,'native_callback_pages':callbacks,'selector_after':word(0xc02c28e0),'virtual_services':services})
report={'kernel_sha256':digest,'procedures':['0xc01042c8 lcd_irq_handler','0xc0101680 qfb_callback'],'cases':rows,'limits':['Virtual register values, register base, mode/page globals and lock count are supplied; no real IRQ, MMIO or device access.','Hardware interrupt disable, timer deletion and wakeup are mocked; optional video callback and timer rearm paths disabled by fixture.','Original IRQ conditions, callback call, selector writes and return execute; event arrival timing and actual display completion remain unqualified.']}
(ROOT/'sources/native-kernel-lcd-irq.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'{len(rows)} original LCD IRQ/callback condition cases passed on virtual registers')
