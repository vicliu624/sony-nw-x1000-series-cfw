"""Original Home request -> registered Pcs descriptor -> original widget config.

No count or control ID is supplied as a query result. Original pool allocation
and widget records execute; pixel rendering/full hardware are not emulated.
"""
import argparse,hashlib,io,json,struct,sys,tarfile,time
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest,private
from native_settings_count import compose,offset,revert

def replay(image,registration=0x4e692c,template_count=156):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
 for s in ELFFile(io.BytesIO(image)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000);u.mem_map(0x70000000,0x10000)
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 queue=[];configs=[];media=[]
 def hook(uc,pc,size,data):
  if pc in (0x12ae8,0x12c64):media.append(pc)
  if pc==0xa57f0:
   queue.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]);value=0
  elif pc==0x1095e0:
   address=uc.reg_read(UC_ARM_REG_R1)
   configs.append(bytes(uc.mem_read(address,0x94)))
   return # Execute the real native allocator/copy constructor.
  elif pc==0xd85c:
   address=uc.reg_read(UC_ARM_REG_R0);uc.mem_write(address,bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R1),uc.reg_read(UC_ARM_REG_R2))));value=address
  elif pc==0xd574:
   address=uc.reg_read(UC_ARM_REG_R0);uc.mem_write(address,bytes([uc.reg_read(UC_ARM_REG_R1)&255])*uc.reg_read(UC_ARM_REG_R2));value=address
  else:return
  uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 handle=u.hook_add(UC_HOOK_CODE,hook)
 def call(address,args):
  u.mem_write(0x70000000,bytes(0x10000))
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),[*args,0,0,0,0][:4]):u.reg_write(reg,value)
  u.reg_write(UC_ARM_REG_SP,0x70008000);u.reg_write(UC_ARM_REG_LR,0x7000ff00)
  u.emu_start(address,0x7000ff00,count=100000);assert u.reg_read(UC_ARM_REG_PC)==0x7000ff00
  return u.reg_read(UC_ARM_REG_R0)
 context=call(0xe5f4,[]);put(context+0x20,1) # Explicit Japanese classification, not a live readback.
 call(0x751ec,[0x33,0x60000000,0x60000004]);pointer,count=word(0x60000000),word(0x60000004)
 home_ids=struct.unpack('<'+'I'*count,u.mem_read(pointer,count*4));index=home_ids.index(0xf00000)
 call(0x737ec,[0,0,index]);request=next(item for item in queue if item[0]==0x20106)
 control=request[2];assert control==0x61
 call(0x10e754,[registration,template_count]) # Original registration instructions.
 assert word(0x75cef8)==registration and word(0x75cefc)==template_count
 manager=call(0x1094f0,[]);assert manager==0x754ac0
 call(0x109524,[manager]) # Original pool/record initialization, capacity176.
 records=[]
 for item in range(template_count):
  resource=call(0x10e850,[item]);configs.clear();put(0x60001000,0)
  assert call(0x10e558,[item,0x60001000])==0
  assert len(configs)==1
  object_address=word(0x60001000);assert manager+4<=object_address<manager+0x7644
  config=configs[0];assert bytes(u.mem_read(object_address,0x94))==config
  record=dict(id=item,resource=resource,field21=word(object_address+0x4c),field32=word(object_address+0x90),capacity=word(object_address+0xa4),configuration_sha256=hashlib.sha256(config).hexdigest())
  assert struct.unpack_from('<I',config,32)[0]==item
  records.append(record)
 assert records[control]['resource']==5000 and records[control]['capacity']==49
 # Keep the UI list/category state explicit: page activation and live touch
 # routing are not executed here. Run the original setters and index lookup,
 # rather than returning selected IDs from a callback mock.
 call(0x74668,[0,2])
 call(0x751ec,[2,0x60000000,0x60000004]);item_pointer,item_count=word(0x60000000),word(0x60000004)
 items=[call(0x74634,[i]) for i in range(item_count)]
 assert items==list(struct.unpack('<'+'I'*item_count,u.mem_read(item_pointer,item_count*4)))
 visible=records[control]['field21'];assert visible<=item_count
 u.hook_del(handle)
 return dict(home_request=request,home_index=index,templates=records,media_builder_calls=media,
             selection_items=items,visible_selection_items=items[:visible],selection_category_fixture=2)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--host-review',required=True);parser.add_argument('--failed-firmware');args=parser.parse_args()
 hp,host=receipt(args.host_review);source=hp.parent/'SpiderApp.player-prepare.analysis-only.elf';candidate=source.read_bytes();assert digest(source)==host['candidate_sha256']
 integrated=host.get('settings_visible_count_composition')
 page_review=host.get('native_remote_page_analysis')
 if page_review:
  _,page=receipt(page_review)
  assert page['sha256']==host['candidate_sha256']
  # Verify the earlier count receipt against its exact input, then remove
  # only those two fields from the final image for the negative control.
  without_page=bytearray(candidate)
  for edit in page['edits']:
   old,new=bytes.fromhex(edit['before']),bytes.fromhex(edit['after'])
   at=offset(candidate,int(edit['address'],16),len(new))
   assert without_page[at:at+len(new)]==new and len(old)==len(new)
   without_page[at:at+len(old)]=old
  assert hashlib.sha256(without_page).hexdigest()==page['base_sha256']
  revert(bytes(without_page),integrated)
  negative=bytearray(candidate)
  for edit in integrated['edits']:
   at=offset(candidate,edit['address'],4)
   assert struct.unpack_from('<I',negative,at)[0]==edit['after']
   struct.pack_into('<I',negative,at,edit['before'])
  base=bytes(negative)
 else:
  base=revert(candidate,integrated) if integrated else candidate
 out=ROOT/'work/settings-descriptor-check'/str(time.time_ns());out.mkdir(parents=True)
 patched,composition=compose(base,out/'composition')
 if integrated:assert patched==candidate
 before,after=replay(base),replay(patched)
 assert before['home_request']==after['home_request']==[0x20106,0,0x61,0]
 assert before['templates'][0x61]['field21']==before['templates'][0x61]['field32']==10
 assert after['templates'][0x61]['field21']==after['templates'][0x61]['field32']==composition['target_count']
 assert [i for i in range(156) if before['templates'][i]!=after['templates'][i]]==[0x61]
 assert after['templates'][0x62]==before['templates'][0x62]
 assert before['selection_items']==after['selection_items']
 assert before['visible_selection_items']==after['visible_selection_items'][:10]
 assert len(after['visible_selection_items'])==composition['target_count']
 assert 0xf80000 in after['visible_selection_items'] and 0xf80000 not in before['visible_selection_items']
 if composition['target_count']==12:assert after['visible_selection_items'][10:]==[0xf80000,0xfd0000]
 failed=None;failed_hash=None
 if args.failed_firmware:
  sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack
  fp=private(args.failed_firmware);failed_hash=digest(fp);assert failed_hash=='de4a233023e4855cf4d94cd5a048f8c3aefaa40f86928724c718de4e32a3f1b1'
  _,parts=unpack(fp.read_bytes(),require_stock=False)
  with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:old=archive.extractfile('./usr/local/lib/x1000-player/SpiderApp').read()
  failed=replay(old);assert failed['templates'][0x61]['field21']==failed['templates'][0x61]['field32']==10 and not failed['media_builder_calls']
 report=dict(passed=True,kind='native-settings-descriptor-count',exact_host_composition_verified=bool(integrated),
  original_settings_request_generated=True,baseline_reproduces_ten=True,unchanged_template_count=155,
  original_index_lookup_executed=True,selection_category_supplied=True,
  constructor_cases=312+(156 if failed else 0),composition=composition,before=before,after=after,
  failed_candidate=failed,failed_candidate_sha256=failed_hash,native_pool_and_widget_records_executed=True,physical_gui_rendered=False,device_accessed=False,firmware_created=False,
  source_hashes={**composition['source_hashes'],'tools/test_native_settings_count.py':digest(ROOT/'tools/test_native_settings_count.py')},
  limits=['Japanese classification is supplied; original Home selection/list lookup generates the request and control ID.',
   'Original Pcs registration, manager/pool init, pool allocation and widget record construction execute; only standard memcpy/memset and queue transport are modeled.',
   'Selection category2 is supplied; original list state setter/index lookup execute. Page activation, full startup, touch/scroll, live Homebrew and hardware are not qualified.'])
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(passed=True,directory=out.relative_to(ROOT).as_posix(),constructor_cases=report['constructor_cases'],baseline_count=10,corrected_count=composition['target_count'],failed_candidate_reproduced=bool(failed),firmware_created=False),indent=2))

if __name__=='__main__':main()
