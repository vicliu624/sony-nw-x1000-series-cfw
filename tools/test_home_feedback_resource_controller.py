"""Execute stock message allocation and duplicate suppression with GUI boundaries mocked."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
import argparse
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',required=True);args=parser.parse_args()
area=(ROOT/args.candidate).resolve()
assert area.is_relative_to(ROOT/'work')
b=(area/'SpiderApp.resource.analysis-only.elf').read_bytes();report=json.loads((area/'build.json').read_text());assert hashlib.sha256(b).hexdigest()==report['candidate_sha256']
e=ELFFile(io.BytesIO(b));u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x700000)
for s in e.iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x50000000,0x40000);controller=0x50010000;slot=controller+8;sp=0x50008000;calls=[]
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def hook(uc,pc,size,_):
 if pc not in (0x14e9c,0x28140,0xc6880,0x28214,0xecb5c,0x3700c,0xd574,0x14ea0,0xc69cc,0x15114):return
 calls.append(pc);a=uc.reg_read(UC_ARM_REG_R0)
 if pc==0x28140:
  assert a==slot;uc.mem_write(a,bytes(0x2c30))
 elif pc==0xc6880:
  assert a==slot+12;d=uc.reg_read(UC_ARM_REG_R1);assert word(d)==745 and word(d+4)==99999 and word(d+20)==0
  uc.mem_write(a+36,struct.pack('<I',0x50030000))

 elif pc==0x3700c:
  uc.reg_write(UC_ARM_REG_R0,controller);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 elif pc==0xd574:
  value=uc.reg_read(UC_ARM_REG_R1)&255;n=uc.reg_read(UC_ARM_REG_R2);uc.mem_write(a,bytes([value])*n)
 elif pc==0x28214:
  assert a==slot;uc.mem_write(slot+4,struct.pack('<I',1))
 uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def invoke():
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50007000);u.reg_write(UC_ARM_REG_R0,controller);u.reg_write(UC_ARM_REG_R1,745)
 u.emu_start(0x37090,0x50007000,count=2000);assert u.reg_read(UC_ARM_REG_SP)==sp and u.reg_read(UC_ARM_REG_PC)==0x50007000
invoke();assert word(slot)==745 and word(controller)==1 and struct.unpack('<H',u.mem_read(controller+4,2))[0]==1
first=list(calls);invoke();assert calls==first,'Duplicate message must not allocate another slot'
# Drive the original close callback -> manager removal -> slot reset.
# GUI teardown remains a boundary fixture; slot ownership is stock code.
cycles=32
for cycle in range(cycles):
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50007000);u.reg_write(UC_ARM_REG_R0,slot)
 u.emu_start(0x28264,0x50007000,count=3000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50007000 and u.reg_read(UC_ARM_REG_SP)==sp
 assert word(slot)==0 and word(slot+4)==0 and word(controller)==0
 assert struct.unpack('<H',u.mem_read(controller+4,2))[0]==0
 if cycle+1<cycles:invoke()
# Feed GUI events to the original complete per-slot event processor.
# The event collection and widget are fixtures; no physical key claim.
widget=0x50030000;event=0x50032000;child=0x50034000;event_results=[]
for kind,children,param,foreign in ((19,0,745,False),(38,0,745,False),(19,1,745,False),(38,1,745,False),(19,1,0,False),(7,1,745,False),(38,1,745,True)):
 invoke();u.mem_write(slot+8,struct.pack('<I',widget));u.mem_write(slot+48,struct.pack('<I',widget))
 u.mem_write(widget+0x460,struct.pack('<I',8));u.mem_write(widget+0xae4,struct.pack('<I',1));u.mem_write(child+0xae4,struct.pack('<I',14));u.mem_write(child+0x460,struct.pack('<I',1));u.mem_write(child+0x4c4,struct.pack('<I',widget));u.mem_write(widget+0x4c8,struct.pack('<2I',child if children else 0,0));u.mem_write(slot+52,struct.pack('<I',widget))
 u.mem_write(slot+36,struct.pack('<I',745));u.mem_write(slot+0x118+8,struct.pack('<I',1));u.mem_write(slot+0x118+20,struct.pack('<I',event));u.mem_write(event,bytes(0x2b0));u.mem_write(event,struct.pack('<I',child if children else widget));u.mem_write(event+8,struct.pack('<I',kind));u.mem_write(event+0x5c,struct.pack('<I',param))
 if foreign:u.mem_write(child+0x4c4,struct.pack('<I',0))
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50007000);u.reg_write(UC_ARM_REG_R0,slot)
 u.emu_start(0x2837c,0x50007000,count=5000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50007000 and u.reg_read(UC_ARM_REG_SP)==sp
 if children:
  assert word(event+12)&14==2 and word(event+24)==0
 ignored=param==0 or kind==7 or foreign
 if ignored:
  assert word(slot)==745 and word(slot+4)==1 and word(controller)==1
  # Dispose the still-open fixture through the original callback for next case.
  u.reg_write(UC_ARM_REG_R0,slot);u.reg_write(UC_ARM_REG_LR,0x50007000);u.emu_start(0x28264,0x50007000,count=3000)
 elif kind==19:
  assert word(slot+4)==2  # original hide request, followed by GUI completion
  u.reg_write(UC_ARM_REG_R0,slot);u.reg_write(UC_ARM_REG_LR,0x50007000);u.emu_start(0x28264,0x50007000,count=3000)
 assert word(slot)==0 and word(controller)==0 and struct.unpack('<H',u.mem_read(controller+4,2))[0]==0
 event_results.append({'gui_event_type':kind,'child_count':children,'ignored_event':ignored,'foreign_parent':foreign,'slot_reclaimed_by_event':not ignored,'fixture_cleanup_for_ignored':ignored,'slot_empty_after_case':True,'animation_completion_injected':kind==19 and not ignored})
result={'passed':True,'gui_event_cases':event_results,'stock_widget_event_dispatch_executed':True,'stock_child_collection_executed':True,'child_layout_is_fixture':True,'close_callback_cycles':cycles,'stock_slot_reset_verified':True,'stock_control_destroy_and_clear_executed':True,'stock_controller_executed':True,'stock_id_mapping_and_descriptor_constructor_executed':True,'duplicate_suppression_verified':True,'boundaries_mocked':['0x14e9c','0x28140','0xc6880','0x28214','0xecb5c','0x3700c','0xd574','0x14ea0','0xc69cc','0x15114'],'visible_gui_verified':False,'close_callback_to_slot_reset_verified':True,'physical_key_to_close_verified':False,'candidate_sha256':report['candidate_sha256'],'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(area/'controller-cleanup-report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
