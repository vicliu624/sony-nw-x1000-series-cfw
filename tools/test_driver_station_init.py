"""Original relocated adapter defaults and post-download station command calls.

Command transport/responses are mocked; this is not actual kernel/module startup
or proof that radio hardware/key state is reset by firmware download.
"""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R12,UC_ARM_REG_FP,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-driver-station-init';OUT.mkdir(parents=True,exist_ok=True)
with contextlib.redirect_stdout(io.StringIO()):env=runpy.run_path(str(ROOT/'tools/test_espnow_driver_admission.py'))
base=env['text_base'];names=env['names'];external=env['external'];sections=env['sections']
PRIVATE,ADAPTER,STACK=0x30000000,0x30010000,0x3003e000
def put(cpu,a,n):cpu.mem_write(a,struct.pack('<I',n))
def word(cpu,a):return struct.unpack('<I',cpu.mem_read(a,4))[0]
def machine():
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    for address,data,size in sections.values():cpu.mem_map(address,size);cpu.mem_write(address,bytes(data))
    cpu.mem_map(0x900000,0x10000);cpu.mem_map(0x30000000,0x40000);cpu.mem_write(ADAPTER,b'\xa5'*0x2000);put(cpu,PRIVATE+4,ADAPTER);return cpu
rows=[]
for halfword_seed in (0,0xffff):
    cpu=machine();cpu.mem_write(ADAPTER+0x13c4,struct.pack('<H',halfword_seed))
    # IP is the verified adapter; R0 matches the preceding literal load1404.
    for reg,value in [(UC_ARM_REG_R12,ADAPTER),(UC_ARM_REG_R0,0x1404)]:cpu.reg_write(reg,value)
    cpu.emu_start(base+0x1ef4,base+0x1f04,count=10)
    assert cpu.reg_read(UC_ARM_REG_PC)==base+0x1f04 and struct.unpack('<H',cpu.mem_read(ADAPTER+0x13c4,2))[0]==0x203
    commands=[]
    def startup(u,pc,size,unused):
        if pc==external['memset']:
            dest,value,n=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];assert dest==ADAPTER+0x1219 and n==6;u.mem_write(dest,bytes([value&255])*n);u.reg_write(UC_ARM_REG_R0,dest);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
        elif pc==names['PrepareAndSendCommand']:
            private,command,action,wait=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];assert private==PRIVATE
            pointer=word(u,u.reg_read(UC_ARM_REG_SP)+4);row={'command':hex(command),'action':action,'wait':wait}
            if command==0x28:assert pointer==ADAPTER+0x13c4;row['flags']=hex(struct.unpack('<H',u.mem_read(pointer,2))[0]);assert row['flags']=='0x203'
            commands.append(row)
            if command==0x1e:u.emu_stop();return
            u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    h=cpu.hook_add(UC_HOOK_CODE,startup)
    for reg,value in [(UC_ARM_REG_R5,PRIVATE),(UC_ARM_REG_R6,ADAPTER),(UC_ARM_REG_R7,names['mfgmode']),(UC_ARM_REG_R4,0),(UC_ARM_REG_SP,STACK)]:cpu.reg_write(reg,value)
    put(cpu,names['mfgmode'],0);cpu.emu_start(base+0x1ae0,0x900100,count=3000);cpu.hook_del(h)
    assert [r['command'] for r in commands]==['0x3','0x28','0x74','0x76','0x1e']
    assert commands[1]['flags']=='0x203';rows.append({'old_filter_halfword':halfword_seed,'filter_offset':'0x13c4','filter_default':'0x203','commands_before_power_result':commands})
builders=[]
for flags in (0x203,0x283,3,0xffff):
    cpu=machine();target=PRIVATE+0x100;source=PRIVATE+0x20;before=bytes(range(0x90,0xa0));cpu.mem_write(target,before);cpu.mem_write(source,struct.pack('<H',flags))
    cpu.reg_write(UC_ARM_REG_R5,source);cpu.reg_write(UC_ARM_REG_R6,target);cpu.emu_start(base+0xc388,base+0xc3b8,count=20)
    after=bytes(cpu.mem_read(target,len(before)));expected=bytearray(before);expected[0:4]=bytes.fromhex('28000c00');expected[8:10]=struct.pack('<H',flags);assert after==expected
    builders.append({'flags':hex(flags),'command_bytes':12,'header_command':'0x28','reserved_and_sequence_result_preserved':True,'original_builder_block':'text+0xc388..0xc3b8'})
report={'passed':True,'module_sha256':hashlib.sha256(env['raw']).hexdigest(),'cases':rows,'mac_control_builder_cases':builders,'original_adapter_default_block':'text+0x1ef4..0x1f04','original_post_download_block':'text+0x1ae0..0x1bcc','original_relocated_arm_instructions':True,'transport_responses_mocked':True,'firmware_download_executed':False,'hardware_keys_cleared_verified':False,'device_accessed':False,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/test_driver_station_init.py','tools/test_espnow_driver_admission.py']}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
