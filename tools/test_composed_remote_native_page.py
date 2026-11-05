"""Execute both patched native registrations and the composed Remote callbacks.

The request bridge, startup initializer body and GUI queue/renderer are fixtures.
Original constructor/state/row-lookup/category code executes; no UPG/device.
"""
import argparse,hashlib,io,json,struct,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from review_managed_remote_profile import receipt,private,digest
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',required=True);args=parser.parse_args()
rp,review=receipt(args.review);path=private(review['artifact']);assert digest(path)==review['sha256'];raw=path.read_bytes();rows=[]
for case in ('entry-unpaired','query-unavailable','entry-and-cancel','stock-selection',
             'wireless-busy','wireless-restored','wireless-other-row'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x70000000,0x10000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 area=0x70000000;done=area+0xff00;context=0x683400
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
 word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 master=int(review['metadata_address'],16)
 assert bytes(u.mem_read(master,193*4))==bytes(u.mem_read(0x3f55d8,193*4))
 original_desc=word(master+192*4);initializers=word(original_desc+20)
 startup=word(initializers) if initializers else 0
 initial_calls=[];requests=[];posts=[];delegated=[]
 def hook(cpu,pc,size,unused):
  values=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
  if startup and pc==startup:initial_calls.append(pc)
  elif pc==0xda84:
   assert cpu.reg_read(UC_ARM_REG_LR) in review['request_callers']
   operation,row=values[:2];requests.append([operation,row])
   if case=='entry-unpaired':result=4321
   elif case=='query-unavailable' and operation==2:result=0x5752fffd
   elif operation in (1,2):result=0x57530001
   elif operation in (3,5):result=0x57520000
   elif operation==6:result=0x5752fffd if case=='wireless-busy' else 0x57520000
   else:raise AssertionError(values)
  elif pc==0x950f0:delegated.append(values[:3]);result=0x0202
  elif pc==0x7c8cc:delegated.append(values[:3]);result=0x5a02
  elif pc==0xa57f0:posts.append(values)
  elif pc in (0x17c42c,0x33b918):pass
  else:return
  cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,values=()):
  sp=area+0xe000;put(sp,0)
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),[*values,0,0,0,0][:4]):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(address,done,count=300000);assert u.reg_read(UC_ARM_REG_PC)==done
  return u.reg_read(UC_ARM_REG_R0)
 assert call(0x736d0)==0
 assert word(0x6833fc)==context and list(u.mem_read(context,3))==[193,1,194]
 assert word(context+4)==master and not requests
 assert call(0x73694,[context])==0
 assert list(u.mem_read(context,3))==[193,1,194] and not requests
 assert len(initial_calls)==(2 if startup else 0)
 environment=call(0xe5f4);put(environment+0x20,1)
 call(0x74668,[0,2,0,0]);assert call(0x7461c)==2
 assert call(0x74634,[11])==0xfd0000
 assert call(0x17ca34,[context,2,2])==0x0202
 def event(kind,value=0):assert call(0x17c608,[context,kind,value,0])==0
 if case.startswith('wireless-'):
  call(0x74668,[2,90,0,0])
  assert call(0x17ca34,[context,90,2])==0x5a02
  index=1 if case=='wireless-other-row' else 0
  assert (call(0x74634,[index])==0xf60005)==(index==0)
  event(0x4a0111,index)
  assert requests==([] if index else [[6,0]])
  assert delegated==([] if case=='wireless-busy' else [[context,0x4a0111,index]])
  assert not posts and list(u.mem_read(context,2))==[90,2]
 else:
  event(0x4a0111,0 if case=='stock-selection' else 11)
 if case.startswith('wireless-'):
  pass
 elif case=='stock-selection':
  assert delegated==[[context,0x4a0111,0]] and not requests and not posts
  assert list(u.mem_read(context,2))==[2,2]
 elif case=='entry-unpaired':
  assert requests==[[1,0]] and not posts and not delegated
  assert list(u.mem_read(context,2))==[2,2]
 elif case=='query-unavailable':
  assert requests==[[1,0],[2,0],[5,0]]
  assert posts==[[0x20106,0,97,11]]
  assert list(u.mem_read(context,2))==[2,1]
  event(0x4a0116)
  assert list(u.mem_read(context,2))==[2,2]
  assert call(0x74634,[11])==0xfd0000
 else:
  assert list(u.mem_read(context,2))==[194,1]
  assert posts==[[0x20106,0,29,1]] and requests==[[1,0],[2,0]]
  event(0x4a0116);assert list(u.mem_read(context,2))==[194,2]
  event(0x4a0111,0);assert requests[-1]==[3,0]
  event(0x4a0119,0xff0001)
  assert posts[-1]==[0x20106,0,97,11] and list(u.mem_read(context,2))==[2,1]
  event(0x4a0116);assert list(u.mem_read(context,2))==[2,2]
  assert all(operation!=4 for operation,row in requests)
  assert call(0x74634,[11])==0xfd0000 # Category restored by actual setter.
 rows.append(dict(case=case,initial_state_preserved=[193,1],registered_groups=194,
                  request_operations=requests,queued_pages=posts,final_state=list(u.mem_read(context,2))))
report=dict(passed=True,candidate_sha256=review['sha256'],cases=rows,
 both_native_registration_paths_executed=True,original_row_and_category_helpers=True,
 device_accessed=False,firmware_created=False,
 source_hashes={'tools/test_composed_remote_native_page.py':digest(ROOT/'tools/test_composed_remote_native_page.py')},
 limits=['Original startup module initializer body, request authority/backend and GUI queue/rendering are fixtures.',
         'No guarded DSO/view observer or ordinary-Wi-Fi entry guard is paired; no physical startup qualification.'])
out=rp.parent/'checks'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
