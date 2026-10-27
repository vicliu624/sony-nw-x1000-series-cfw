"""Original module registry initialization and 16 stock descriptor registrations; no module handlers."""
from pathlib import Path
import hashlib,io,json,struct,argparse
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--active-parent-prefix',action='store_true');parser.add_argument('--remove-parent-record',action='store_true');parser.add_argument('--paired-parent-actions',action='store_true');parser.add_argument('--native-parent-insert',action='store_true');args=parser.parse_args()
assert not args.remove_parent_record or args.active_parent_prefix
assert not args.paired_parent_actions or args.remove_parent_record
assert not args.native_parent_insert or args.paired_parent_actions
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
u.mem_map(low,high-low)
for s in segs:u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x60000000,0x20000);registry=0xe601e0;clears=[];parent_calls=[];attach_calls=[];insert_services=[]
def put(p,v):u.mem_write(p,struct.pack('<I',v))
def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
def hook(uc,pc,size,data):
 if args.native_parent_insert and pc in (0xe87f4,0xe9690,0x1124b4):
  if pc==0xe87f4:result=0x60008000;insert_services.append('manager_getter')
  elif pc==0xe9690:
   assert uc.reg_read(UC_ARM_REG_R0)==0x60008000;result=0;insert_services.append('frame_dispatch')
  else:
   assert uc.reg_read(UC_ARM_REG_R0)==0x60004000;result=0;insert_services.append('invalidate_parent')
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 if args.active_parent_prefix and pc==0x112cc0:
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  assert a==[0x60004000,0x60005000,0],a
  parent_calls.append(a)
  if not args.remove_parent_record:uc.emu_stop()
  return
 if args.remove_parent_record and not args.paired_parent_actions and pc==0xbe5d0:uc.emu_stop();return
 if args.paired_parent_actions and pc==0x112a8c:
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  assert a==[0x60004000,0x60005000,0];attach_calls.append(a)
  if not args.native_parent_insert:uc.emu_stop()
  return
 if pc==symbols['memset']:
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  assert a[1:]==[0,76] and registry<=a[0] and a[0]+76<=registry+0x130c
  clears.append(a[0]);uc.mem_write(a[0],bytes(76))
  uc.reg_write(UC_ARM_REG_R0,a[0]);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x60018000)
u.emu_start(0x14d0c,0x14d40,count=100000)
assert u.reg_read(UC_ARM_REG_PC)==0x14d40 and word(registry)==16 and len(clears)==54
assert word(0x14d60)==0x4de800
rows=[]
for mid in range(16):
 descriptor=word(registry+4+mid*4);assert descriptor==0x4de800+mid*28
 values=list(struct.unpack('<7I',u.mem_read(descriptor,28)))
 u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
 u.emu_start(values[1],0x6001f000,count=1000)
 assert u.reg_read(UC_ARM_REG_PC)==0x6001f000
 object_address=u.reg_read(UC_ARM_REG_R0);assert low<=object_address<high
 rows.append({'id':mid,'descriptor':hex(descriptor),'flags':values[0],
              'object_getter':hex(values[1]),'parameter_converter':hex(values[4]),
              'stop_handler':hex(values[6]),'object_address_from_native_getter':hex(object_address),'all_words':[hex(v) for v in values]})
report={'input_sha256':digest,'native_range':['0x14d0c','0x14d40 exclusive'],'registry':hex(registry),
 'registered_count':16,'descriptors':rows,'limits':['Original manager init and ordered registration execute; memset memory service simulated. No descriptor pointer is supplied by test.',
 'Stops before later event registration; original getters subsequently return object addresses but no module handlers or object initialization execute. No module identity inferred solely from id/address; no initialized runtime objects or APF/hardware qualification.']}
if args.active_parent_prefix:
 report['limits'][-1]='Registration stops before later event registration; original getters return object addresses. Extra active descriptor0 prefix scope is described separately below; no complete initialized runtime or APF/hardware qualification.'
 obj=int(rows[0]['object_address_from_native_getter'],16)
 put(obj,1);put(registry+0x12f8,0x60004000);put(registry+0x1300,0);put(0x69c7cc+0x24,0x60005000)
 if args.remove_parent_record:
  put(0x60004000,0x60006000);put(0x60004004,0x60005000);put(0x60004044,1);put(0x60004048,0)
  put(0x60005000+0x460,0x08000008 if args.native_parent_insert else 0x08000000);put(0x60006000+0x460,0x10)
  if args.paired_parent_actions:
   put(0x60005000+0x4c8,0x60007000);put(0x60007000+0xae4,14)
   if args.native_parent_insert:
    put(0x60005000+0x4f4,1);put(0x60007000+0x4f4,1)
 u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
 u.emu_start(0x14dfc,0x6001f000 if args.paired_parent_actions else 0,count=30000)
 assert u.reg_read(UC_ARM_REG_PC)==(0x6001f000 if args.paired_parent_actions else 0xbe5d0 if args.remove_parent_record else 0x112cc0) and parent_calls==[[0x60004000,0x60005000,0]]
 report['active_descriptor0_prefix']={'entry':'0x14dfc(module_id0)','native_handler':'0x25bd4','native_service_getter':'0xbdbe8','service_object':'0x69c7cc',
                                     'parent_from_registry_12f8':'0x60004000','child_from_service_object_24':'0x60005000',
                                     'native_target':'0x112cc0','args':parent_calls[0]}
 report['limits'].append('Module0 activity1, runtime parent pointer and service child pointer supplied. Native descriptor/getter/state check/handler forward parent and child to112cc0. Stops before target; no real object initialization, control removal, video/DSP stop or hardware qualification. Registry12f8 is passed as context pointer, not merely a Boolean gate.')
 if args.remove_parent_record:
  assert word(0x60004004)==0 and word(0x60004044)==0
  assert word(0x60005000+0x460)==(8 if args.native_parent_insert else 0) and word(0x60006000+0x460)==0
  report['active_descriptor0_prefix']['native_parent_remove_result']={'parent_slot_after':0,'parent_count_after':0,'child_flags_after':word(0x60005000+0x460),'root_flags_after':0,'stopped_before':'0xbe5d0'}
  report['limits'][-1]='Module0 activity and parent/child/root records supplied. Actual descriptor handler ->be5bc ->112cc0 removes child slot, decrements count and clears flags, then stops before remaining be5d0/be4ec. No object initialization, rendering, video/DSP stop or hardware qualification.'
 if args.paired_parent_actions:
  assert word(0x60007000+0x460)==0x8000
  u.reg_write(UC_ARM_REG_R0,registry);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_R2,0)
  # e0010's third parameter is0; original wrapper supplies parent context.
  u.reg_write(UC_ARM_REG_R3,0);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
  u.emu_start(0xdf8a4,0x6001f000 if args.native_parent_insert else 0,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==(0x6001f000 if args.native_parent_insert else 0x112a8c) and attach_calls==[[0x60004000,0x60005000,0]]
  assert word(0x60007000+0x460)==0 and word(0x60004044)==int(args.native_parent_insert)
  report['paired_parent_actions']={'remove_entry':'0x14dfc','remove_handler_returned':True,'descendant_type_fixture':14,
                                  'descendant_flag_after_remove':'0x8000','prepare_attach_entry':'0xdf8a4',
                                  'descendant_flag_before_attach':'0x0','attach_target':'0x112a8c','attach_args':attach_calls[0]}
  del report['active_descriptor0_prefix']['native_parent_remove_result']['stopped_before']
  report['active_descriptor0_prefix']['native_parent_remove_result']['returned_to']='0x6001f000'
  report['limits'][-1]='Module0 active parent/root/child and one type14 descendant tree supplied. Original removal/collection traversal sets descendant flag8000 and returns; original paired+14 handler clears it and reaches insertion112a8c. Stops before insertion/rendering; no complete UI reattach, object initialization, audio/DSP stop or hardware qualification.'
  if args.native_parent_insert:
   assert u.reg_read(UC_ARM_REG_R0)==0 and word(0x60004004)==0x60005000
   assert word(0x60005000+0x460)==0x08000008 and word(0x60006000+0x460)==0x80
   assert insert_services==['manager_getter','frame_dispatch','invalidate_parent']
   report['paired_parent_actions']['native_insertion_result']={'parent_count_after':1,'slot_after':'0x60005000','child_flags_after':'0x08000008','root_flags_after':'0x80','return':0,'virtual_services':insert_services}
   report['limits'][-1]='Module0 active parent/child/root/descendant and valid-child flag8/initialized callback markers supplied. Original paired callbacks, collection traversal, input packet formatter and insertion record/flags execute; manager getter, frame dispatch and parent invalidation virtual. Both callbacks return, but no real rendering, module initialization, APF or hardware qualification.'
(ROOT/'sources'/('native-spider-descriptor-parent-roundtrip.json' if args.native_parent_insert else 'native-spider-descriptor-paired-parent.json' if args.paired_parent_actions else 'native-spider-descriptor-parent-remove.json' if args.remove_parent_record else 'native-spider-descriptor-parent-prefix.json' if args.active_parent_prefix else 'native-spider-module-registry.json')).write_text(json.dumps(report,indent=2)+'\n')
print('Original registry registered16 descriptors; active descriptor0 parent operation checked' if args.active_parent_prefix else 'Original registry init registered16 stock descriptors and native getters resolved objects; no synthetic descriptor or handler execution')
for r in rows:print(r['id'],r['object_getter'],r['stop_handler'])
