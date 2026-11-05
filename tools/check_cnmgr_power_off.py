"""Replay pinned Sony power-off client API; RAM IPC only, no device access."""
import hashlib
import io
import json
import re
import struct
import subprocess
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

path=ROOT/'work/qqmusic-wifi/libcnmgr.so.1'
raw=path.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1'
elf=ELFFile(io.BytesIO(raw))
symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
asm=subprocess.check_output(['arm-linux-gnueabi-objdump','-d',str(path)],text=True)
imports={int(a,16):n for a,n in re.findall(r'^([0-9a-f]+) <([^>]+)@plt>:',asm,re.M)}
rows=[]
for answer in (0,1,0xffffffff):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0,0x20000)
    for s in elf.iter_segments():
        if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
    u.mem_map(0x300000,0x20000);end=0x300100;requests=[]
    u.mem_write(0x12cf0+0x238,struct.pack('<I',1))
    def hook(uc,pc,size,unused):
        if pc==end:uc.emu_stop();return
        if pc not in imports:return
        name=imports[pc];a,b,c=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
        if name=='memset':assert c<=8192;uc.mem_write(a,bytes([b&255])*c);result=a
        elif name=='memcpy':assert c<=8192;uc.mem_write(a,bytes(uc.mem_read(b,c)));result=a
        elif name=='write':assert c==1020;requests.append(struct.unpack('<I',uc.mem_read(b,4))[0]);result=c
        elif name=='read':assert c==1012;uc.mem_write(b,struct.pack('<II',answer,0)+bytes(c-8));result=c
        elif name in ('lockf','pthread_mutex_lock','pthread_mutex_unlock'):pass
        else:raise AssertionError(name)
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    u.reg_write(UC_ARM_REG_SP,0x31f000);u.reg_write(UC_ARM_REG_LR,end)
    u.emu_start(symbols['cnmgr_power_off'],end,count=20000)
    assert u.reg_read(UC_ARM_REG_PC)==end and requests==[4]
    assert u.reg_read(UC_ARM_REG_R0)==answer,(hex(answer),hex(u.reg_read(UC_ARM_REG_R0)))
    rows.append(dict(daemon_answer=answer,returned=answer,request_kind=requests[0]))
report=dict(passed=True,original_arm_client_executed=True,daemon_and_ipc_modeled=True,
            device_accessed=False,rows=rows,
            response_status_word_offset=0,
            stock_library_sha256=hashlib.sha256(raw).hexdigest(),
            source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
            limits=['Client initialized flag supplied; actual daemon power-state transitions are not executed.',
                    'No physical RF power-off, current measurement or multi-client ownership qualification.'])
out=ROOT/'work/remote-settings-native';out.mkdir(exist_ok=True)
(out/'power-off-client-replay.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
