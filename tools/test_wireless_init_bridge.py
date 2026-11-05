"""Execute composed native initialization, including object replacement."""
import contextlib, io, json, runpy, struct, time
from itertools import product
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from wireless_callback_bridge import compose as confirm, offset
from wireless_init_bridge import compose

out=ROOT/'work/wireless-init'/str(time.time_ns());out.mkdir(parents=True)
with contextlib.redirect_stdout(io.StringIO()):
    base=runpy.run_path(str(ROOT/'tools/test_builtin_player_composition.py'),init_globals={'native_settings_profile':True})['artifact'].read_bytes()
paired, callback=confirm(base,out/'confirm')
patched, report=compose(paired,out/'init')
choice_descriptor=0x4e692c+0x1d*132
assert struct.unpack_from('<I',patched,offset(patched,choice_descriptor+26*4,4))[0]==13900
assert [struct.unpack_from('<I',patched,offset(patched,choice_descriptor+i*4,4))[0] for i in (21,22,32)]==[3,3,3], 'Three rows need matching native count/capacity descriptors'
from test_native_settings_count import replay
before_controls,after_controls=replay(paired)['templates'],replay(patched)['templates']
assert [i for i in range(156) if before_controls[i]!=after_controls[i]]==[0x1d]
assert after_controls[0x1d]['field21']==after_controls[0x1d]['field32']==after_controls[0x1d]['capacity']==3
assert patched[offset(base,0x405438,4):offset(base,0x405438,4)+4]==paired[offset(base,0x405438,4):offset(base,0x405438,4)+4]
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x60000000,0x20000)
for segment in ELFFile(io.BytesIO(patched)).iter_segments():
    if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
root=0x60001000;view=0x60008000;replacement=0x60009000;stop=0x6001e000
def put(address,value):u.mem_write(address,struct.pack('<I',value))
def get(address):return struct.unpack('<I',u.mem_read(address,4))[0]
slot=root+0x2b18+0x1d*8;calls=[];posts=[];replace=False;present=True;response=0
def hook(uc,pc,size,unused):
    if pc==0x2a984:answer=root if present else 0
    elif pc==0x10a118:
        uc.mem_write(uc.reg_read(UC_ARM_REG_R1),bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0)+0x18,60)));answer=0
    elif pc==0x10a0d4:
        uc.mem_write(uc.reg_read(UC_ARM_REG_R0)+0x18,bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R1),60)));answer=0
    elif pc==0x88400:
        calls.append(get(view+0x18+13*4))
        if replace:put(slot,replacement)
        answer=0x12345678
    elif pc==0xda84:
        assert uc.reg_read(UC_ARM_REG_R0)==5 and uc.reg_read(UC_ARM_REG_R1)==0
        answer=response
    elif pc==0xa57f0:
        posts.append([uc.reg_read(reg) for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)])
        if replace:put(slot,replacement)
        answer=0
    elif pc==0x7461c:answer=90
    elif pc==0x74608:answer=17
    elif pc==0x74668:
        assert posts and [uc.reg_read(reg) for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]==[90,154,0,17]
        answer=0x12345678
    else:return
    uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
cases=0
for present in (False,True):
 for replace in (False,True):
  for count,response in product((0,1,2,3,4),(0,0x574d0001,0x574e0000,0x574e0001,0x574e0002,0x574e0003)):
   initial=[0x9000+i for i in range(15)];initial[13]=count
   for address in (view,replacement):u.mem_write(address+0x18,struct.pack('<15I',*initial))
   put(slot,view);put(0x4ee5d8,99);calls.clear();posts.clear()
   for reg,value in ((UC_ARM_REG_SP,0x6001d000),(UC_ARM_REG_LR,stop)):u.reg_write(reg,value)
   u.emu_start(int(report['entry'],16),stop,count=10000)
   valid=response in (0x574e0000,0x574e0001,0x574e0002)
   assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_R0)==0x12345678
   assert len(calls)==(0 if valid else 1)
   assert get(0x4ee5d8)==(response&0xffff if valid else 99)
   assert posts==([[0x20106,0,0x1d,response&0xffff]] if valid else [])
   for address in (view,replacement):
    expected=initial[:]
    if present and count==2 and (address==view or replace):expected[13]=3
    assert tuple(expected)==struct.unpack('<15I',u.mem_read(address+0x18,60))
   cases+=1
refused=False
try:compose(patched,out/'duplicate')
except ValueError:refused=True
assert refused
print(json.dumps(dict(passed=True,arm_cases=cases,duplicate_refused=True,confirmation_preserved=True,initializer=report,device_accessed=False,firmware_created=False),indent=2))
