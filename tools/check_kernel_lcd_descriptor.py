"""Original kernel page-info transfer into LCD descriptor; virtual memory and uncontended locks."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_CPSR
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
a=(ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes();elf=ELFFile(io.BytesIO(a));assert elf.get_section_by_name('.kernel').data()==raw
source=json.loads((ROOT/'sources/native-display-submit-prefix.json').read_text());rows=[]
assert source['input_sha256']=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
for case in source['cases']:
 page=case['page_fixture'];payload=case['calls'][0]['payload_words']
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':
   low=s['p_vaddr']&~4095;high=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(low,high-low);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 put(0x60001234,0x60002000)
 for offset in (0x14,0x24):put(0x60002000+offset,1)
 # Global validated request state, as written by qfb_ioctl; that write stage is a fixture.
 state=[payload[0],payload[1],payload[2],payload[4],payload[3],0]
 target=0xc02c2250 if page==0 else 0xc02c2268
 u.mem_write(target,struct.pack('<6I',*state))
 def hook(uc,pc,size,data):
  if pc in (0xc0218680,0xc02186e0):raise AssertionError('Unexpected contended lock helper')
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 u.reg_write(UC_ARM_REG_CPSR,0x13);u.reg_write(UC_ARM_REG_R0,page);u.reg_write(UC_ARM_REG_R1,0x60001000)
 u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(0xc0100c8c,0x50000000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==0
 address=word(0xc02c21e4)
 assert address==(0x33000000 if page==0 else 0x33060000)
 observed=[word(0xc02c21e0+x) for x in (0x1c,0x20,0x24,0x28,0x2c)]
 assert observed==[payload[1],payload[0],payload[2],payload[4],page]
 assert word(0x60002014)==word(0x60002024)==1
 rows.append({'page':page,'input_request':payload,'lcd_descriptor_address_value':hex(address),'lcd_fields_at_1c_20_24_28_2c':observed,'uncontended_locks_restored':True})
report={'kernel_sha256':digest,'procedure':'0xc0100c8c set_image_info_to_LCD','cases':rows,'limits':['Original whole function executes on virtual kernel/global memory; fd info, validated-state records and lock counters are supplied.','Physical base constants come from the original kernel image, but no physical addresses are dereferenced.','No qfb_ioctl state-write stage, LCD driver call, MMIO, interrupts or actual concurrency; returned descriptor is not a rendered frame.']}
(ROOT/'sources/native-kernel-lcd-descriptor.json').write_text(json.dumps(report,indent=2)+'\n')
print('Two original page-to-LCD descriptor transfers verified; stock bases33000000/33060000, locks restored')
