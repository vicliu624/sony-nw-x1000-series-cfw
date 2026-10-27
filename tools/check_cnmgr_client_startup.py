"""Replay original PIC cnmgr init/power-on with virtual FIFO/thread helpers only."""
from pathlib import Path
import hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:binary=tar.extractfile('./usr/lib/libcnmgr.so.1.0').read()
digest=hashlib.sha256(binary).hexdigest()
assert digest=='688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1'
elf=ELFFile(io.BytesIO(binary));base=0x100000;rows=[]
for name,second_argument in [('second-argument-null',0),('second-argument-present',0x210100)]:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(base,0x20000);u.mem_map(0x200000,0x30000)
    for segment in elf.iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(base+segment['p_vaddr'],segment.data())
    for relocation in elf.get_section_by_name('.rel.dyn').iter_relocations():
        if relocation['r_info_type']==23:
            address=base+relocation['r_offset'];value=struct.unpack('<I',u.mem_read(address,4))[0]
            u.mem_write(address,struct.pack('<I',(value+base)&0xffffffff))
    end=0x210000;requests=[];threads=[];opened=[];phase='init'
    def hook(uc,pc,size,unused):
        if pc==end:uc.emu_stop();return
        offset=pc-base
        helpers=(0x671c,0x6bb8,0x63b8,0x6cc4,0x1edc,0x1e7c,0x1ec4,0x1ee8,0x1d2c,0x1d20,0x1d98,0x2224,0x2440)
        if offset not in helpers:return
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
        if offset==0x1ec4:opened.append(a[0]);result=40+len(opened)
        elif offset==0x1d2c:threads.append(a[2])
        elif offset==0x1d20:uc.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
        elif offset==0x1d98:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
        elif offset in (0x2224,0x2440):
            packet=bytes(uc.mem_read(a[0],1020));kind=struct.unpack('<I',packet[:4])[0]
            requests.append({'phase':phase,'kind':kind,'packet_sha256':hashlib.sha256(packet).hexdigest()})
            uc.mem_write(a[1],b'\0'*1012)
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    def call(entry,values):
        for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1),values):u.reg_write(reg,value)
        u.reg_write(UC_ARM_REG_SP,0x22f000);u.reg_write(UC_ARM_REG_LR,end)
        u.emu_start(base+entry,end,count=10000)
        assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==0
    call(0x2b24,(0x210200,second_argument))
    init_kinds=[r['kind'] for r in requests]
    assert init_kinds==([1,29] if not second_argument else [1,15,29]) and len(threads)==1
    phase='power-on';call(0x3a60,())
    assert requests[-1]['kind']==3 and len(requests)==len(init_kinds)+1
    rows.append({'case':name,'initialization_request_kinds':init_kinds,'requests':requests,
                 'thread_entries_requested':threads,'virtual_open_count':len(opened)})
report={'library_sha256':digest,'cases':rows,'all_passed':True,'physical_device_access':False,
        'limits':['Original cnmgr_init/power_on execute with relative relocations; common module init, FIFO/thread/libc helpers virtual.',
                  'IPC helpers2224/2440 capture actual request bytes but inject successful replies; no FIFO or daemon executes.',
                  'Library arguments are fixtures; callbacks not run and actual SpiderApp startup call sequence is not established.',
                  'No inference that missing kind3 in init excludes later automatic caller requests.']}
(ROOT/'sources/native-cnmgr-client-startup.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
