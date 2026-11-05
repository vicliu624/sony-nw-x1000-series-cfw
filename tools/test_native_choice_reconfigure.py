"""Original Pcs allocation + reversible choice parameters/resource binding.

Proves property mechanics only. Resource pointers and inactive Root lifecycle
are fixtures; active rendering/close acknowledgement must be qualified later.
"""
import hashlib,io,json,struct,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
path=ROOT/'work/player-mode-refresh-fix-20261105-1/SpiderApp.player-prepare.analysis-only.elf'
raw=path.read_bytes();u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x70000000,0x10000)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
area=0x70000000;done=area+0xff00
put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
def hook(cpu,pc,size,unused):
 args=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
 if pc==0xd85c:u.mem_write(args[0],bytes(u.mem_read(args[1],args[2])));value=args[0]
 elif pc==0xd574:u.mem_write(args[0],bytes([args[1]&255])*args[2]);value=args[0]
 else:return
 cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
def reject_interrupt(*unused):raise AssertionError('Unexpected syscall')
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,reject_interrupt)
def call(address,args):
 sp=area+0xe000
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),[*args,0,0,0,0][:4]):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done)
 u.emu_start(address,done,count=200000);assert u.reg_read(UC_ARM_REG_PC)==done
 return u.reg_read(UC_ARM_REG_R0)
call(0x10e754,[0x4e692c,156])
assert word(0x75cef8)==0x4e692c and word(0x75cefc)==156
manager=call(0x1094f0,[]);call(0x109524,[manager])
put(area,0);assert call(0x10e558,[29,area])==0
view=word(area);assert manager+4<=view<manager+0x7644
assert word(view+32)==29 and word(view+0xa4)==3
root=call(0x2a984,[])
# The Root is not constructed here. Model only its existing pointer/flags slot.
put(root+0x2b18+29*8,view);put(root+0x2b18+29*8+4,0)
root_before=bytes(u.mem_read(root,0xea50))
stock_resource=area+0x8000;remote_resource=area+0x8100
call(0x10a1d4,[view,stock_resource])
view_before=bytes(u.mem_read(view,0xac))
parameters=area+0x1000
assert call(0x10a118,[view,parameters])==parameters
original=bytes(u.mem_read(parameters,60));assert word(parameters+52)==3
sid_address=0x4e692c+29*132+26*4
original_sid=word(sid_address)
assert original_sid==13900 and call(0x10e850,[29])==13900
assert call(0x10e858,[29])==2 # Wording-provider index, distinct from SWD SID.
put(sid_address,13901)
assert call(0x10e850,[29])==13901 and call(0x10e858,[29])==2
put(parameters+52,2);call(0x10a0d4,[view,parameters]);call(0x10a1d4,[view,remote_resource])
assert word(view+0x4c)==2 and word(view+0xa8)==remote_resource
assert word(view+0xa4)==3 # Existing allocated capacity is preserved.
# Restore through the same original setters. No Root-array growth or new ID.
u.mem_write(parameters,original);call(0x10a0d4,[view,parameters]);call(0x10a1d4,[view,stock_resource])
put(sid_address,original_sid)
assert call(0x10e850,[29])==13900
assert bytes(u.mem_read(view,0xac))==view_before
assert bytes(u.mem_read(root,0xea50))==root_before
report=dict(passed=True,input_player_sha256=hashlib.sha256(raw).hexdigest(),control=29,
 original_constructor_and_parameter_resource_setters=True,original_capacity=3,
 remote_count=2,restored_count=3,exact_view_bytes_restored=True,root_bytes_unchanged=True,
 dynamic_sid_getter_roundtrip=[13900,13901,13900],wording_provider_index_preserved=2,
 device_accessed=False,firmware_created=False,
 source_hashes={'tools/test_native_choice_reconfigure.py':hashlib.sha256((ROOT/'tools/test_native_choice_reconfigure.py').read_bytes()).hexdigest()},
 limits=['Wording-provider pointers and inactive Root view slot are supplied; no actual SWD parsing/rendering.',
         'No active display, view ownership, asynchronous close/restore timing, sleep or hardware qualification.'])
out=ROOT/'work/native-choice-reconfigure'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
