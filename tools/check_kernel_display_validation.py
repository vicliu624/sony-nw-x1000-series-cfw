"""Original kernel six-word display-argument copy/validation, before locks or LCD I/O."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R4,UC_ARM_REG_FP,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
a=(ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes();elf=ELFFile(io.BytesIO(a));assert elf.get_section_by_name('.kernel').data()==raw
source=json.loads((ROOT/'sources/native-display-submit-prefix.json').read_text())
assert source['input_sha256']=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
cases=[('native-page-'+str(c['page_fixture']),c['calls'][0]['payload_words'],True) for c in source['cases']]
base=[1,1,255,0,0,0]
for field,maximum in enumerate((1,65535,255,1,1)):
 for value,accept in ((maximum,True),(maximum+1,False),(0xffffffff,False)):
  payload=base.copy();payload[field]=value;cases.append((f'field{field}-{value}',payload,accept))
for value in (1,2,0xffffffff):
 payload=base.copy();payload[5]=value;cases.append((f'update-normalized-{value}',payload,True))
rows=[]
for name,payload,accept in cases:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':
   low=s['p_vaddr']&~4095;high=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(low,high-low);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000);fp=0x60010000
 u.mem_write(fp-0x74,struct.pack('<6I',*payload))
 def hook(uc,pc,size,data):
  if pc in (0xc01024c0,0xc0102738):uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_FP,fp);u.reg_write(UC_ARM_REG_R4,fp-0x74)
 u.emu_start(0xc0102440,0,count=1000)
 destination=u.reg_read(UC_ARM_REG_PC)
 assert destination==(0xc01024c0 if accept else 0xc0102738)
 normalized=list(struct.unpack('<6I',u.mem_read(fp-0x8c,24)))
 assert normalized==payload[:5]+[0]
 rows.append({'case':name,'payload':payload,'normalized_payload':normalized,'accepted_by_validation':accept,'destination':hex(destination)})
report={'kernel_sha256':digest,'analysis_sha256':hashlib.sha256(a).hexdigest(),'range':['0xc0102440','validation exit before0xc01024c0 locks'],'cases':rows,'field_names_from_kernel_error_strings':['tc_enable','t_color','alpha','page','rot','update'],'limits':['User copy already completed into supplied stack storage; original internal copy/normalization and range checks execute.','Stops before locks, kernel globals, image state changes and LCD calls. Acceptance only means passing these range checks.','Field5 is zeroed in this path before validation; do not generalize to other ioctls or driver versions.']}
(ROOT/'sources/native-kernel-display-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'{len(rows)} original kernel payload validation cases verified; update normalized to0')
