"""Original normal-path display submit prefix; simulated ioctl, no hardware."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for page in (0,1):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segments)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segments:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def words(p,n):return list(struct.unpack('<'+'I'*n,u.mem_read(p,n*4)))
 for p,v in ((0x60000000,17),(0x6000001c,page),(0x60000020,255),(0x60000024,1)):put(p,v)
 calls=[]
 def hook(uc,pc,size,data):
  if pc!=symbols['ioctl']:return
  fd,request,pointer=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  payload=words(pointer,6)
  assert fd==17 and request==0x40044e01 and payload==[1,1,255,page,0,0]
  calls.append({'fd':fd,'request':hex(request),'payload_words':payload})
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 u.reg_write(UC_ARM_REG_R0,0x60000000);u.reg_write(UC_ARM_REG_SP,0x60018000)
 u.emu_start(0x14a5a4,0x14a60c,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x14a60c and len(calls)==1
 rows.append({'page_fixture':page,'calls':calls})
report={'input_sha256':digest,'native_range':['0x14a5a4','0x14a60c exclusive'],'cases':rows,'limits':['Normal context flag0 and object fd/page/alpha fields are fixtures; original getter and submit prefix execute.','ioctl is simulated; no actual frame submission or synchronization, no13b3c8 completion helper.','Request40044e01 differs from archived mp200 header QFB_BLD_SCRN4e01; that header is not a verified X1000 ioctl contract.','Six payload words are observations, not a complete public struct definition or permission to copy requests to hardware.']}
(ROOT/'sources/native-display-submit-prefix.json').write_text(json.dumps(report,indent=2)+'\n')
print('Two original page-submit prefixes verified: ioctl40044e01 with six-word payload; archived header mismatch confirmed')
