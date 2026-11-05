"""Differential ARM capsule ABI test; observer and APF call effects modeled."""
import argparse,io,json,struct,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',required=True);a=p.parse_args()
rp,r=receipt(a.review);candidate=ROOT/r['artifact'];base=ROOT/r['base_artifact']
assert digest(candidate)==r['sha256'] and digest(base)==r['base_sha256']
out=ROOT/'work/parent-entry-trace-tests'/str(time.time_ns());out.mkdir(parents=True)
volatile=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12)
regs=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP)
launch=next(e['address'] for e in r['edits'] if e['target']==r['symbols']['parent_trace_launch'])
cases=[]
for scenario,arg in [('launch',0),('lookup',0),('lookup-return',0),('lookup-return',1),('lookup-return',0xffffffff),('switch',0),('switch',0xfffffff9)]:
 for observer_result in (123,0xffffffff,0x58575052):
  results=[]
  for traced,path in ((False,base),(True,candidate)):
   u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x71000000,0x10000)
   for s in ELFFile(io.BytesIO(path.read_bytes())).iter_segments():
    if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
   stack=0x7100e000;observed=[];native=[]
   for i,reg in enumerate(regs):u.reg_write(reg,0x11110000+i*0x100)
   u.reg_write(UC_ARM_REG_SP,stack);u.reg_write(UC_ARM_REG_LR,0x7100ff00)
   u.reg_write(UC_ARM_REG_CPSR,(u.reg_read(UC_ARM_REG_CPSR)&0x0fffffff)|0xa0000000)
   if scenario=='launch':entry=launch;stop=0xb0464
   elif scenario=='lookup':entry=0xb04f8;stop=0xb04fc
   elif scenario=='lookup-return':entry=0xb0504;stop=0xb0508;u.reg_write(UC_ARM_REG_R0,arg)
   else:
    entry=0xb0554;stop=0xb0558
    for reg,value in zip(volatile[:4],(0x820f68,0x30001,0,1)):u.reg_write(reg,value)
   expected_frame=[u.reg_read(reg) for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R12,UC_ARM_REG_LR)]
   if scenario=='switch':expected_frame[-1]=0xb0558 # The callsite BL sets LR.
   def hook(cpu,pc,size,unused):
    if pc==0xda84:
     tag=cpu.reg_read(UC_ARM_REG_R0);frame=cpu.reg_read(UC_ARM_REG_R1);target=cpu.reg_read(UC_ARM_REG_LR)
     assert tag&0xffffff00==0x48425000 and target in r['observer_callers']
     assert cpu.reg_read(UC_ARM_REG_SP)%8==0
     saved=list(struct.unpack('<8I',bytes(cpu.mem_read(frame,32))));observed.append(dict(stage=tag&255,frame=saved))
     for i,reg in enumerate(volatile):cpu.reg_write(reg,observer_result if i==0 else 0xdead0000+i)
     cpu.reg_write(UC_ARM_REG_CPSR,(cpu.reg_read(UC_ARM_REG_CPSR)&0x0fffffff)|0x50000000)
     cpu.reg_write(UC_ARM_REG_LR,0xdead9998);cpu.reg_write(UC_ARM_REG_PC,target)
    elif pc==0x2681e8:
     native.append([cpu.reg_read(reg) for reg in volatile[:4]]);target=cpu.reg_read(UC_ARM_REG_LR)
     for i,reg in enumerate(volatile):cpu.reg_write(reg,arg if i==0 else 0xabcd0000+i)
     cpu.reg_write(UC_ARM_REG_CPSR,(cpu.reg_read(UC_ARM_REG_CPSR)&0x0fffffff)|0x30000000)
     cpu.reg_write(UC_ARM_REG_PC,target)
   handle=u.hook_add(UC_HOOK_CODE,hook);u.emu_start(entry,stop,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==stop
   if traced:
    assert [x['stage'] for x in observed]=={'launch':[1],'lookup':[2],'lookup-return':[3],'switch':[4,5]}[scenario]
    assert observed[0]['frame']==expected_frame,(scenario,observed[0]['frame'],expected_frame)
    if scenario=='switch':assert observed[1]['frame'][:4]==[arg,0xabcd0001,0xabcd0002,0xabcd0003]
   else:assert not observed
   results.append(([u.reg_read(reg) for reg in regs],u.reg_read(UC_ARM_REG_CPSR)&0xf0000000,native))
   u.hook_del(handle);del u
  assert results[0]==results[1],(scenario,arg,observer_result,results)
  cases.append(dict(scenario=scenario,argument=arg,observer_result=observer_result,registers_stack_and_flags_equal=True))
report=dict(passed=True,cases=cases,actual_arm_capsules_executed=True,original_and_traced_boundary_states_equal=True,observer_and_apf_effects_modeled=True,storage_writes_implemented=False,firmware_created=False,device_accessed=False,source_hashes={p:digest(ROOT/p) for p in ['tools/test_parent_entry_trace.py','runtime/platform/player/parent_entry_trace.S']},limits=['No observer backend, file capture, real APF request or original GUI/hardware executes.','Comparison covers registers0..12, SP and NZCV; LR after a BL is caller-volatile.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(cases),report=(out/'report.json').relative_to(ROOT).as_posix()),indent=2))
