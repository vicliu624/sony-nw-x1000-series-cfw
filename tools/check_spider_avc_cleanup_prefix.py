"""Stock global AVC cleanup reader through native method dispatch; bounded before resource teardown."""
from pathlib import Path
import hashlib,io,json,struct,argparse
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R5,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--internal-work-prefix',action='store_true')
parser.add_argument('--state-request-prefix',action='store_true')
args=parser.parse_args()
assert not args.state_request_prefix or args.internal_work_prefix
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));rows=[]
for present,active in ((False,0),(True,0),(True,1)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segs:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000);obj=0x60001000
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 u.reg_write(UC_ARM_REG_R5,obj);u.emu_start(0x234314,0x234320,count=20)
 assert word(obj)==0x4833b8 and word(0x4833b8+8)==0x234234
 put(0x7faf1c,obj if present else 0);u.mem_write(obj+0xf8,bytes([active]))
 trace=[];services=[];status_a=[2,1,0];status_b=[1,0];component_calls=[]
 if args.internal_work_prefix and active:
  for p,v in ((obj+0xa0,0x60007000),(obj+0xa4,0x60008000),(obj+0xb0,0x60005000),
              (0x60007000,0x60009000),(0x60008000,0x60009000),(0x60005000,0x60006000),
              (0x60009000,0x60011000),(0x60009004,0x60011004)):
   put(p,v)
  for off in (0x18,0x1c,0x24,0x2c):put(0x60006000+off,0x60011000+off)
  for off in (0xf10,0xf14,0xf18,0xf1c,0xf24):put(obj+off,123)
  if args.state_request_prefix:
   put(obj+0x738,3);put(obj+0x74c,0x6000a000);put(obj+0x7bc,0x6000b000)
   put(0x6000a02c,0x60011100);put(0x6000a014,0x60011104)
 def hook(uc,pc,size,data):
  if args.internal_work_prefix and active:
   if args.state_request_prefix:
    if pc==0x60011100:
     assert uc.reg_read(UC_ARM_REG_R0)==0x6000a000
     put(uc.reg_read(UC_ARM_REG_R1),3);component_calls.append({'operation':'state_query','virtual_state':3})
     uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if pc==0x60011104:
     values=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
     assert values==[0x6000a000,0,2,0]
     component_calls.append({'operation':'command','args':values,'virtual_result':0})
     uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if pc==0x23d718:
     assert uc.reg_read(UC_ARM_REG_R0)==0x6000b000 and uc.reg_read(UC_ARM_REG_R1)==0xffffffff
     uc.emu_stop();return
   if pc in (0x60011000,0x60011004,0x60011018,0x6001101c,0x60011024,0x6001102c):
    owner=uc.reg_read(UC_ARM_REG_R0)
    if pc==0x60011024:result=status_a.pop(0)
    elif pc==0x6001102c:result=status_b.pop(0)
    else:result=0
    services.append({'target':hex(pc),'object':hex(owner),'virtual_result':result})
    uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   if pc==0x234c1c:
    assert uc.reg_read(UC_ARM_REG_R0)==obj and uc.reg_read(UC_ARM_REG_R1)==1
    if not args.state_request_prefix:uc.emu_stop();return
  if pc in (0x197fd4,0x234234,0x234268):trace.append(hex(pc))
  if pc in (0x197d38,0x197fd8) or (pc==0x2353fc and not args.internal_work_prefix):uc.emu_stop()
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 u.reg_write(UC_ARM_REG_SP,0x60018000)
 u.emu_start(0x197d28,0,count=10000)
 expected=0x197d38 if not present else (0x23d718 if args.state_request_prefix else 0x234c1c if args.internal_work_prefix else 0x2353fc) if active else 0x197fd8
 assert u.reg_read(UC_ARM_REG_PC)==expected
 assert trace==([] if not present else ['0x197fd4','0x234234','0x234268'] if active else ['0x197fd4','0x234234'])
 assert u.mem_read(obj+0xf8,1)==bytes(1)
 if args.internal_work_prefix and active:
  assert not status_a and not status_b
  assert [c['target'] for c in services]==['0x60011000','0x60011024','0x60011018','0x60011024','0x60011018','0x60011024','0x60011000','0x6001102c','0x6001101c','0x6001102c']
  assert all(word(obj+off)==0 for off in (0xf10,0xf14,0xf18,0xf1c,0xf24))
 if args.state_request_prefix and active:assert len(component_calls)==2 and word(obj+0x738)==1
 rows.append({'global_object_present_fixture':present,'active_flag_fixture':active,'original_dispatch_trace':trace,'stopped_before':hex(expected),'active_flag_after':0,'virtual_internal_services':services,'virtual_component_calls':component_calls})
report={'input_sha256':digest,'entry':'0x197d28','cases':rows,
 'finding':'Original global reader selects AVC object slot08; active cleanup clears flag then dispatches actual slot30 target2353fc. Inactive cleanup returns before destructor; null object skips cleanup.',
 'limits':['Object presence/activity supplied, only original constructor table-assignment prefix executed. No full object construction or APF caller proven.',
           'Starts at global-reader interior block, stops before other cleanup/destructor/internal work. No full resource teardown, close, kernel/device or hardware execution.']}
if args.internal_work_prefix:
 report['limits'].append('Internal lock/worker callback interfaces supplied. Status sequences2/1/0 and1/0 model two drain loops; original loops consume and reset bookkeeping before requesting state1. Stops before state transition implementation, unlocks and resource frees; no real worker execution.')
if args.state_request_prefix:
 report['limits'].append('Object current state3 and component query3 supplied; original request target1 dispatches component command0/state2, records requested target1 then reaches wait helper with timeout-1. Query/command success virtual; wait not executed, no completion inferred from object state.')
(ROOT/'sources'/('native-spider-avc-state-request-prefix.json' if args.state_request_prefix else 'native-spider-avc-internal-cleanup-prefix.json' if args.internal_work_prefix else 'native-spider-avc-cleanup-prefix.json')).write_text(json.dumps(report,indent=2)+'\n')
print('Three stock AVC global cleanup prefixes passed: null/inactive/active; native slot08 then slot30, no whole cleanup claim')
