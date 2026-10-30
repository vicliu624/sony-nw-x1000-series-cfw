"""Execute original radio init routine that reclaims its scatter-input memory."""
import hashlib
import json
from pathlib import Path
import struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from marvell_firmware import parse

ROOT=Path(__file__).resolve().parents[1];blob=(ROOT/'work/targets-jp/sd8686.bin').read_bytes()
assert hashlib.sha256(blob).hexdigest()=='08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for base,size in ((0,0x20000),(0xc0000000,0x20000),(0x04000000,0x2000),(0x200000,0x10000)):u.mem_map(base,size)
for record in parse(blob):
    if record.command==1:u.mem_write(record.address,record.data)
before=bytes(u.mem_read(0x17320,32));writes=[]
def stop(cpu,pc,size,unused):
    if pc==0x1f000:cpu.emu_stop()
def watch(cpu,access,address,size,value,unused):
    if cpu.reg_read(UC_ARM_REG_PC)==0x11f4:writes.append((address,size,value))
u.hook_add(UC_HOOK_CODE,stop);u.hook_add(UC_HOOK_MEM_WRITE,watch)
u.reg_write(UC_ARM_REG_SP,0x208000);u.reg_write(UC_ARM_REG_LR,0x1f000)
u.emu_start(0x11e0,0x1f004,count=10000)
assert u.reg_read(UC_ARM_REG_PC)==0x1f000
assert len(writes)==0x33f and writes==[(0x17304+i*4,4,0) for i in range(0x33f)]
assert struct.unpack('<I',u.mem_read(0x17300,4))[0]==0xf0f0f0f0
after=bytes(u.mem_read(0x17320,32));assert before!=after and after==bytes(32)
out=ROOT/'work/espnow-scatter-lifetime';out.mkdir(parents=True,exist_ok=True)
report={'passed':True,'original_image_sha256':hashlib.sha256(blob).hexdigest(),
        'original_entry':'0x11e0','zeroing_instruction':'0x11f4','zero_start':'0x17304','zero_end_exclusive':'0x18000',
        'zero_word_count':len(writes),'scatter_before':before.hex(),'scatter_after':after.hex(),
        'scatter_is_not_runtime_immutable':True,'full_boot_order_qualified':False,'device_accessed':False}
(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
