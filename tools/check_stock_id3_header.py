"""Execute original JP SpiderApp ID3 header routine with synthetic file callbacks."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_SP
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));rows=[]
for label,header,expected,read_error in [
 ('v2.2',b'ID3\x02\0\0\0\0\x01\0',0,False),
 ('v2.3',b'ID3\x03\0\0\0\0\x01\0',0,False),
 ('v2.4',b'ID3\x04\0\0\0\0\x01\0',7,False),
 ('v2.3-revision1',b'ID3\x03\x01\0\0\0\x01\0',7,False),
 ('invalid-major',b'ID3\x01\0\0\0\0\x01\0',7,False),
 ('missing-marker',b'BAD\x03\0\0\0\0\x01\0',9,False),
 ('v2.3-flags',b'ID3\x03\0\xe0\0\0\x01\0',0,False),
 ('file-read-error',b'ID3\x03\0\0\0\0\x01\0',2,True),
]:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x900000)
    for segment in elf.iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
    context=0x60001000;output=context+256;reads=[]
    u.reg_write(UC_ARM_REG_R0,context);u.reg_write(UC_ARM_REG_R1,output)
    u.reg_write(UC_ARM_REG_SP,0x6001f000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    def ret(value=0):
        u.reg_write(UC_ARM_REG_R0,value&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,address,size,unused):
        a,b,c,d=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if address==0x50000000:uc.emu_stop()
        elif address in (0x318d6c,0x318d54):ret()
        elif address==0x31984c:ret() # seek callback only
        elif address==0x3197f0:
            assert c==10;reads.append(c)
            if read_error:ret(2)
            else:uc.mem_write(b,header);uc.mem_write(d,struct.pack('<I',len(header)));ret()
        elif address==0xd85c:uc.mem_write(a,bytes(uc.mem_read(b,c)));ret(a)
        elif address==0xe1e0:
            left=bytes(uc.mem_read(a,c));right=bytes(uc.mem_read(b,c));ret(0 if left==right else 1)
    def interrupt(uc,number,unused):raise AssertionError('Unexpected syscall/interrupt')
    u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,interrupt)
    u.emu_start(0x319a44,0x50000004,count=10000)
    assert u.reg_read(UC_ARM_REG_PC)==0x50000000
    result=u.reg_read(UC_ARM_REG_R0);fields=struct.unpack('<7I',u.mem_read(output,28))
    assert result==expected,(label,result,expected,fields)
    if result==0:assert fields[1]==128,(label,fields)
    rows.append({'case':label,'return_code':result,'header_fields':fields,'read_calls':reads})
report={'passed':True,'function':'0x319a44','input_sha256':hashlib.sha256(raw).hexdigest(),
        'cases':rows,'device_access':False,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits':['Original header routine executes; file seek/read, logging and libc memcpy/memcmp callbacks simulated.',
                  'Header acceptance only: no text encoding, APIC image, frame traversal, stock library scan or physical playback qualification.']}
(ROOT/'sources/native-stock-id3-header-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'cases':rows},indent=2))
