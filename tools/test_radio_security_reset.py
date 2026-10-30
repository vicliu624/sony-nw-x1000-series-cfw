"""Actual software security-reset helper and its MAC refresh wrapper.

Context, MMIO and one hardware-status read are modeled. No player/key reset.
"""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-security-reset';OUT.mkdir(parents=True,exist_ok=True)
with contextlib.redirect_stdout(io.StringIO()):env=runpy.run_path(str(ROOT/'tools/test_radio_mac_control.py'))
machine,word=env['machine'],env['word'];A=0xc0014684;F=0xc0014528;Q=0xc00146e0;END=0x20f000
def invoke(cpu,entry,*args):
    trace=[];writes=[]
    def code(u,pc,size,unused):
        trace.append(pc)
        if pc==0x11c4:u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def write(u,access,address,size,value,unused):writes.append({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'address':hex(address),'size':size,'value':hex(value)})
    hooks=[cpu.hook_add(UC_HOOK_CODE,code),cpu.hook_add(UC_HOOK_MEM_WRITE,write)]
    for reg,value in [(UC_ARM_REG_SP,0x208000),(UC_ARM_REG_LR,END|1),*zip((UC_ARM_REG_R0,UC_ARM_REG_R1),args)]:cpu.reg_write(reg,value)
    try:cpu.emu_start(entry|1,END,count=2000)
    finally:
        for h in hooks:cpu.hook_del(h)
    assert cpu.reg_read(UC_ARM_REG_PC)==END;return trace,writes
rows=[]
for first,second in ((0,0),(1,0),(0,1),(1,1)):
    cpu=machine(1,1,1,2,2);cpu.mem_write(A,bytes([1,1,2,1]));sample=bytes([0x5a])*60;cpu.mem_write(A+4,sample);cpu.mem_write(F,bytes.fromhex('0884657a'))
    trace,writes=invoke(cpu,0xc5e4,first,second);after=bytes(cpu.mem_read(A,4));expected=bytes([0 if first else 1,0 if second else 1,0 if first else 2,0 if second else 1]);assert after==expected
    assert cpu.mem_read(Q,1)==bytes([0 if first else 1]);assert bytes(cpu.mem_read(A+4,60))==sample
    flags=struct.unpack('<H',cpu.mem_read(F,2))[0];assert flags==(0x8008 if first or second else 0x8408);assert bytes(cpu.mem_read(F+2,2))==bytes.fromhex('657a')
    hardware=[w for w in writes if 0x80000000<=int(w['address'],16)<0x80010000 or 0x04000000<=int(w['address'],16)<0x04004000];assert not hardware
    assert cpu.mem_read(0x2008c0,1)==b'\x01'
    rows.append({'args':[first,second],'activation_bytes':list(after),'q_byte':0 if first else 1,'flags':hex(flags),'sampled_other_context_bytes_preserved':True,'mmio_writes':0,'context_privacy_byte_preserved':True})
refresh=[]
for privacy in (0,1):
    cpu=machine(privacy,1,1,2,2);cpu.mem_write(F,struct.pack('<H',0x8203));cpu.mem_write(0x8000200c,struct.pack('<I',0x01004300));cpu.mem_write(0x8000a300,struct.pack('<I',0x10000200));trace,writes=invoke(cpu,0xc0006144)
    assert 0xc5e4 in trace and 0x54c0 in trace and 0x6b6c in trace
    assert bytes(cpu.mem_read(A,4))==bytes(4) and cpu.mem_read(Q,1)==b'\0' and cpu.mem_read(0x2008c0,1)==bytes([privacy])
    assert word(cpu,0x8000200c)==(0x01004300 if privacy else 0x01000000);assert word(cpu,0x8000a300)==0x10000000
    if privacy:assert word(cpu,0x8000a320)==7 and word(cpu,0x8000a350)==word(cpu,0x8000a354)==0xffffffff
    refresh.append({'context_privacy_byte':privacy,'software_activation_cleared':True,'register_8000200c':hex(word(cpu,0x8000200c)),'register_8000a300':hex(word(cpu,0x8000a300)),'writes':writes})
report={'passed':True,'reset_helper':'0xc5e4','refresh_wrapper':'0xc0006144','helper_cases':rows,'refresh_cases':refresh,'stock_sha256':env['digest'],'hardware_mmio_modeled':True,'hardware_status_11c4_substituted':True,'complete_key_memory_or_hardware_erasure_proven':False,'fresh_boot_path_executed':False,'device_accessed':False,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/test_radio_security_reset.py','tools/test_radio_mac_control.py']}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'helper_cases':len(rows),'refresh_cases':len(refresh),'hardware_key_erasure_proven':False,'report':str(OUT/'report.json'),'device_accessed':False},indent=2))
