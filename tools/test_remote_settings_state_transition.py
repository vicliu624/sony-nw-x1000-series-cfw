"""Replay Settings callback results through the original Sony FSM.

Original registration and event routing execute; the select callback result
and navigation leaf effects are fixtures. No GUI, radio or device operation.
"""
import hashlib
import io
import json
import struct
import time
import argparse
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from app_registry import ROOT

raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
rows=[]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--host-review');args=parser.parse_args()
cases=[(0x0201,raw),(0x0202,raw)]
candidate=None
if args.host_review:
    from review_managed_remote_profile import receipt,digest
    path,review=receipt(args.host_review)
    candidate=(path.parent/'SpiderApp.player-prepare.analysis-only.elf').read_bytes()
    assert hashlib.sha256(candidate).hexdigest()==review['candidate_sha256']
    cases.append((0x0202,candidate))
for returned,current in cases:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
    for segment in ELFFile(io.BytesIO(current)).iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    area=0x70000000;u.mem_map(area,0x10000);context=area+0x100;done=area+0xff00
    selected=[];navigation=[];ignored=[]
    def hook(cpu,pc,size,unused):
        if current is candidate and pc==0x4d8040:selected.append(pc);return
        if current is candidate and pc==0x74634:value=0xfd0000
        elif current is candidate and pc==0xda84:value=0 # Refused/no-op request fixture.
        elif pc==0x950f0:selected.append(pc);value=returned
        elif pc==0x74518:navigation.append(pc);value=0
        elif pc in (0x74510,0x7377c):
            ignored.append(pc);return # Execute the original no-op handler body.
        elif pc in (0x17c42c,0x33b918):value=0
        else:return
        cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    def call(address,args,extra=0):
        sp=area+0xe000;u.mem_write(sp,struct.pack('<I',extra))
        for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(register,value)
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done)
        u.emu_start(address,done,count=200000)
        assert u.reg_read(UC_ARM_REG_PC)==done
        return u.reg_read(UC_ARM_REG_R0)
    assert call(0x17c494,[context,193,0x3f55d8,2],2)==0
    assert bytes(u.mem_read(context,2))==bytes([2,2])
    assert call(0x17c608,[context,0x4a0111,11,0])==0
    after=list(u.mem_read(context,2))
    assert after==[2,returned&255]
    assert call(0x17c608,[context,0x4a0101,0,0])==0
    assert len(navigation)==int(returned==0x0202)
    assert call(0x17c608,[context,0x4a0111,11,0])==0
    assert len(selected)==(2 if returned==0x0202 else 1)
    rows.append(dict(callback_result=hex(returned),actual_remote_callback=current is candidate,state_after_selection=after,
                     navigation_leaf_calls=len(navigation),selection_calls=len(selected),
                     ignored_native_handlers=[hex(v) for v in ignored]))
report=dict(passed=True,cases=rows,device_accessed=False,firmware_created=False,
            original_registration_and_fsm_executed=True,
            source_hashes={'tools/test_remote_settings_state_transition.py':hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest()},
            limits=['Baseline select return is supplied; optional candidate executes its actual Remote callback with row/request fixtures.',
                    'Navigation leaf is intercepted. This proves route loss, not a rendered GUI freeze.'])
out=ROOT/'work/remote-settings-transition'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
