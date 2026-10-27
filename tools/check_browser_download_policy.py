"""Offline replay of stock NetFront download-policy leaf; no device access."""
from pathlib import Path
import hashlib, io, json, struct, tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
    binary=tar.extractfile('./usr/local/bin/netfront').read()
assert hashlib.sha256(binary).hexdigest()=='fb027a1f3d86753d110b12827d0a462d46a79ff784e42018820f13e8fd4b2f4f'
elf=ELFFile(io.BytesIO(binary))
def at(addr,size):
    for s in elf.iter_segments():
        if s['p_type']=='PT_LOAD' and s['p_vaddr']<=addr and addr+size<=s['p_vaddr']+s['p_filesz']:
            off=s['p_offset']+addr-s['p_vaddr'];return binary[off:off+size]
    raise AssertionError(hex(addr))
assert at(0x30a7e4,20)==struct.pack('<5I',0xe3a02000,0xe59d3008,0xe5832000,0xe3a00001,0xe12fff1e)
assert at(0x2fbea0,4)==struct.pack('<I',0x615de4)
label=b'appExIsAllowedDownLoadPeer(Parameter Error!).'; assert at(0x615de4,len(label))==label
rows=[]
for initial in (0,1,0xffffffff):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x300000,0x10000);u.mem_map(0x900000,0x10000)
    u.mem_write(0x30a7e4,at(0x30a7e4,20));u.mem_write(0x900008,struct.pack('<I',0x900100));u.mem_write(0x900100,struct.pack('<I',initial))
    u.reg_write(UC_ARM_REG_SP,0x900000);u.reg_write(UC_ARM_REG_LR,0x900200)
    u.emu_start(0x30a7e4,0x900200,count=10)
    assert u.reg_read(UC_ARM_REG_PC)==0x900200
    result=u.reg_read(UC_ARM_REG_R0);value=struct.unpack('<I',u.mem_read(0x900100,4))[0]
    assert result==1 and value==0
    rows.append({'initial_output':initial,'return':result,'output':value})
report={'netfront_sha256':hashlib.sha256(binary).hexdigest(),'entry':'0x30a7e4','caller':'0x2fbe48','cases':rows,'all_passed':True,'physical_device_access':False,'limits':['Leaf stores zero to supplied output and returns one; policy meaning inferred from its named error string and caller.','No complete browser navigation, MIME dispatch, special URI handler or installation path is proven.','Plugin and download strings alone do not establish enabled support.','No vulnerability research or device payload is included.']}
(ROOT/'sources/native-browser-download-policy.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

