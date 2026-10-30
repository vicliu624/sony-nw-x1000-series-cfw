"""Original command0x28 and security/filter helper instructions, modeled MMIO.

Starts at the original switch, after command admission. No device configuration.
Registers are numeric evidence, not an undocumented silicon bit-field guarantee.
"""
from pathlib import Path
import hashlib,json,struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from marvell_firmware import parse
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-mac-control';OUT.mkdir(parents=True,exist_ok=True)
raw=(ROOT/'work/targets-jp/sd8686.bin').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
records=parse(raw)
def machine(privacy=0,feature=0,active=0,kind=0,adapter=0):
    cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    for address,size in [(0,0x20000),(0xc0000000,0x20000),(0x80000000,0x10000),(0x04000000,0x4000),(0x200000,0x10000),(0xffff0000,0x10000)]:cpu.mem_map(address,size)
    for r in records:
        if r.command==1:cpu.mem_write(r.address,r.data)
    def put(a,n):cpu.mem_write(a,struct.pack('<I',n))
    put(0xc000ee48,0x200400);put(0x200408,0x200800);cpu.mem_write(0x2008c0,bytes([privacy]))
    cpu.mem_write(0xc00146e0,bytes([feature]))
    cpu.mem_write(0xc0014684,bytes([active]));cpu.mem_write(0xc0014686,bytes([kind]));cpu.mem_write(0xc0007883,bytes([adapter]))
    put(0xc000dc0c+4,7);put(0xc000dc14,0x200a00);cpu.mem_write(0xc0014528,struct.pack('<H',0x8000));put(0xc000ee00,0);put(0x8000a300,0x10000000);put(0x8000200c,0x01000000)
    return cpu
def word(cpu,a):return struct.unpack('<I',cpu.mem_read(a,4))[0]
def run(cpu,flags):
    request=struct.pack('<6H',0x28,12,1,0,flags,0);cpu.mem_write(0x200100,request);trace=[];writes=[]
    def code(u,pc,size,unused):
        trace.append(pc)
        if pc in (0x9516,0x9a46):u.emu_stop()
        if pc==0x11c4: # Original hardware-status read replaced by fixed0.
            u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def written(u,access,address,size,value,unused):
        if address in (0xc0014528,0xc0014529,0xc000ee00,0x8000a300,0x8000200c,0x80002030):writes.append({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'address':hex(address),'size':size,'value':hex(value)})
    hooks=[cpu.hook_add(UC_HOOK_CODE,code),cpu.hook_add(UC_HOOK_MEM_WRITE,written)]
    for reg,value in [(UC_ARM_REG_R0,0x28),(UC_ARM_REG_R4,0x200108),(UC_ARM_REG_R5,0x200100),(UC_ARM_REG_SP,0x208000),(UC_ARM_REG_LR,0x1f001)]:cpu.reg_write(reg,value)
    try:cpu.emu_start(0x8133,0x9b40,count=10000)
    finally:
        for h in hooks:cpu.hook_del(h)
    assert cpu.reg_read(UC_ARM_REG_PC) in (0x9516,0x9a46),hex(cpu.reg_read(UC_ARM_REG_PC))
    assert 0x54c0 in trace and 0x6b6c in trace
    stored=struct.unpack('<H',cpu.mem_read(0xc0014528,2))[0];assert stored==(flags|0x8000)
    return {'flags':hex(flags),'stored_flags':hex(stored),'register_8000a300':hex(word(cpu,0x8000a300)),'register_8000200c':hex(word(cpu,0x8000200c)),'backup_c000ee00':hex(word(cpu,0xc000ee00)),'writes':writes,'executed_helpers':[hex(a) for a in (0x54c0,0xa674,0xa698,0xae68,0x6b6c,0xdc94,0xdd10) if a in trace]}
rows=[]
contexts=[(privacy,feature,active,kind,adapter) for privacy,feature in ((0,0),(1,0),(1,1)) for active,kind,adapter in ((0,0,0),(1,2,0),(1,2,2))]
for privacy,feature,active,kind,adapter in contexts:
    for flags in (0,3,8,0x80,0x100,0x88,0x180,0x188,0x400,0x203,0x283,0x303,0x38b):
        cpu=machine(privacy,feature,active,kind,adapter);result=run(cpu,flags);secured=bool(privacy or flags&8 or (active and kind==2));receive_control=bool(flags&8 or (privacy and feature) or (adapter==2 and active and kind==2))
        expected=0x10000000|(0xb if flags&0x80 else 0)|(0x40 if flags&0x100 else 0)|(0x200 if receive_control else 0)
        assert word(cpu,0x8000a300)==expected,(privacy,flags,result)
        assert word(cpu,0x8000200c)==0x01000000|(0x4300 if secured else 0)
        result['fixture_byte_2008c0']=privacy;result['fixture_byte_c00146e0']=feature;result['fixture_byte_c0014684']=active;result['fixture_byte_c0014686']=kind;result['fixture_byte_c0007883']=adapter;rows.append(result)
sequences=[]
for flags_list in ([0x80,0],[0x80,0x80,0]):
    cpu=machine();results=[run(cpu,f) for f in flags_list];final=word(cpu,0x8000a300)
    assert final==(0x1000000b if len(flags_list)==3 else 0x10000000)
    sequences.append({'commands':[hex(f) for f in flags_list],'final_register':hex(final),'results':results})
report={'passed':True,'stock_sha256':digest,'cases':rows,'promiscuous_backup_sequences':sequences,'original_switch_security_filter_instructions_executed':True,'command_admission_tested':False,'hardware_status_11c4_substituted':True,'mmio_side_effects_emulated':True,'hardware_unknown_key_admission_verified':False,'device_accessed':False,'radio_loaded':False,'sources':{'tools/test_radio_mac_control.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'single_command_cases':len(rows),'stateful_sequences':len(sequences),'report':str(OUT/'report.json'),'device_accessed':False},indent=2))
