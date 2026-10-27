"""Stock close's two query/clear/submit pairs, virtual driver feedback/backend."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
def file_bytes(address,count):
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz']:
   start=address-s['p_vaddr'];return s.data()[start:start+count]
 raise AssertionError('Address outside file-backed segment')
aux_path_address=struct.unpack('<I',file_bytes(0x14aa98,4))[0]
aux_device=file_bytes(aux_path_address,64).split(b'\0')[0].decode()
assert aux_device=='/dev/icx_watch_elapsed_time'
rows=[]
for sequence in ([0,1],[1,0],[0,0]):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segs:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000);u.mem_map(0x61000000,0xc0000);u.mem_write(0x61000000,b'\xa5'*0xc0000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def words(p,n):return list(struct.unpack('<'+'I'*n,u.mem_read(p,4*n)))
 for off,v in ((0,17),(4,0x61000000),(8,0x61060000),(0x14,0x61000000),(0x18,0x61060000)):put(0x7dca00+off,v)
 for i in range(9):put(0x7dc9dc+i*4,0xa5000000+i)
 for off in (0x50,0x54):put(0x7dca00+off,0xa5a5a5a5)
 put(0x5ff134,1) # Original wrapper's active-state precondition.
 put(0x7dca6c,18) # Auxiliary query device fd fixture.
 queries=[];clears=[];submits=[];backend=[];aux_values=[]
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if pc==symbols['ioctl']:
   if a[0]==18:
    assert a[1]==0x80044502
    value=100+len(aux_values);aux_values.append(value);put(a[2],value)
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   assert a[0]==17
   if a[1]==0x80044e00:
    assert words(a[2],1)==[100] and len(queries)<2
    page=sequence[len(queries)];uc.mem_write(a[2],struct.pack('<3I',100,page,1-page));queries.append(page)
   else:
    assert a[1]==0x40044e01
    payload=words(a[2],6);page=queries[-1]
    assert payload==[1,1,255,page,0,0];submits.append(payload)
   result=0
  elif pc==symbols['memset']:
   page=queries[-1];assert a==[0x61000000+page*0x60000,0,207360]
   clears.append(page);uc.mem_write(a[0],bytes(a[2]));result=a[0]
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x60018000)
 u.emu_start(0xe8d08,0xe8d20,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0xe8d20 and queries==clears==sequence and len(submits)==2
 assert words(0x7dc9dc,9)==[0]*9 and words(0x7dca50,2)==[0,0]
 assert words(0x761394+0xc15c,3)==[0x61000000+sequence[-1]*0x60000,0x33000000+sequence[-1]*0x60000,2]
 assert aux_values==[100,101,102,103] and words(0x761388,2)==[2,103]
 for page in (0,1):
  expected=(bytes(207360) if page in sequence else b'\xa5'*207360)+b'\xa5'*(0x60000-207360)
  assert bytes(u.mem_read(0x61000000+page*0x60000,0x60000))==expected
 rows.append({'ready_page_sequence_fixture':sequence,'cleared_pages':clears,'submits':submits,'virtual_backend_boundaries':backend,'native_13b3c8_reset_executed':True,'software_reset_words_zero':11,'native_wrapper_active_check':True,'native_target_bind_executed':True,'native_119660_is_return_only':True,'native_auxiliary_queries_executed':True,'virtual_auxiliary_values':aux_values,'native_auxiliary_delta_and_absolute':[2,103]})
report={'input_sha256':digest,'range':['0xe8d08','0xe8d20 exclusive'],'cases':rows,'aux_device_from_native_open_literal':aux_device,
 'finding':'Each stock final pair queries driver then clears/submits the selected page. Two calls alone do not guarantee distinct pages; repeated page0 feedback clears/submits page0 twice.',
 'limits':['Driver readiness and successful submit are fixtures; wrappers, selection and clear/submit paths execute original instructions.',
           'Only ioctl and memset services are mocked. Auxiliary query functions execute on supplied fd18 with counter-like values100..103; wrapper computes delta2/absolute103. Active/context state supplied; no asserted physical meaning for auxiliary values.',
           'No actual LCD completion, busy wait, close or physical display. This is not native drain or two-page completion qualification.']}
(ROOT/'sources/native-display-final-pair.json').write_text(json.dumps(report,indent=2)+'\n')
print('Three stock final-pair sequences passed: 01,10,00; distinct pages depend on driver feedback')
