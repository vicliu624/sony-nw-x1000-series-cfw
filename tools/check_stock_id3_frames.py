"""Original stock frame retrieval over PC-generated ID3; synthetic read-only file callbacks."""
from pathlib import Path
import argparse,hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_SP
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True,type=Path);args=parser.parse_args()
tag_path=args.tag.resolve();assert tag_path.is_relative_to((ROOT/'work').resolve())
tag=tag_path.read_bytes();assert 10<=len(tag)<=1048576 and tag[:6]==b'ID3\3\0\0'
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));frames=[];pos=10
while pos<len(tag):
    name=tag[pos:pos+4];size=int.from_bytes(tag[pos+4:pos+8],'big')
    assert size and pos+10+size<=len(tag)
    frames.append((name,tag[pos+10:pos+10+size]));pos+=10+size
cases=[(name,expected,tag,len(expected)+32,True,'full') for name,expected in frames]
cases += [(b'ZZZZ',b'',tag,32,False,'missing-frame'),
          (b'TIT2',frames[0][1][:8],tag,8,True,'small-buffer'),
          (b'APIC',b'',tag[:-3],1024,False,'truncated-image')]
rows=[]
for name,expected,file_bytes,capacity,success,label in cases:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x900000)
    for segment in elf.iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x200000)
    context=0x60001000;length=context+256;output=context+512;stack=0x601ff000
    u.mem_write(length,struct.pack('<I',capacity));u.mem_write(stack,struct.pack('<I',output))
    u.mem_write(output+capacity,b'CANARY!!')
    u.reg_write(UC_ARM_REG_R0,context);u.reg_write(UC_ARM_REG_R1,int.from_bytes(name,'big'))
    u.reg_write(UC_ARM_REG_R2,0);u.reg_write(UC_ARM_REG_R3,length)
    u.reg_write(UC_ARM_REG_SP,stack);u.reg_write(UC_ARM_REG_LR,0x50000000)
    state={'position':0,'reads':0,'seeks':0,'swaps':0}
    def ret(value=0):u.reg_write(UC_ARM_REG_R0,value&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,address,size,unused):
        a,b,c,d=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if address==0x50000000:uc.emu_stop()
        elif address in (0x318d6c,0x318d54):ret()
        elif address==0x31984c:
            assert b<=len(tag);state['position']=b;state['seeks']+=1;ret()
        elif address==0x3197f0:
            assert c<=1048576;chunk=file_bytes[state['position']:state['position']+c]
            if chunk:uc.mem_write(b,chunk)
            uc.mem_write(d,struct.pack('<I',len(chunk)));state['position']+=len(chunk);state['reads']+=1
            ret(0 if len(chunk)==c else 2)
        elif address==0xd85c:uc.mem_write(a,bytes(uc.mem_read(b,c)));ret(a)
        elif address==0xe1e0:ret(0 if bytes(uc.mem_read(a,c))==bytes(uc.mem_read(b,c)) else 1)
        elif address==0x319ca0:state['swaps']+=1 # keep original routine executing
    def interrupt(uc,number,unused):raise AssertionError('Unexpected syscall/interrupt')
    u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,interrupt)
    u.emu_start(0x31a848,0x50000004,count=1000000)
    result=u.reg_read(UC_ARM_REG_R0);actual_length=struct.unpack('<I',u.mem_read(length,4))[0]
    assert u.reg_read(UC_ARM_REG_PC)==0x50000000,(name,result,state)
    assert bytes(u.mem_read(output+capacity,8))==b'CANARY!!'
    if success:
        assert result==0 and actual_length<=capacity,(name,result,state)
        actual=bytes(u.mem_read(output,actual_length))
        assert actual==expected,(name,actual.hex(),expected.hex(),state)
    else:
        assert result!=0,(label,name,result,state)
        actual=b''
    rows.append({'case':label,'frame':name.decode(),'return_code':result,'bytes':actual_length,
                 'sha256':hashlib.sha256(actual).hexdigest() if success else None,**state})
report={'passed':True,'device_access':False,'stock_function':'0x31a848','tag':str(tag_path.relative_to(ROOT)),
        'tag_sha256':hashlib.sha256(tag).hexdigest(),'stock_sha256':hashlib.sha256(raw).hexdigest(),'cases':rows,
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits':['Original stock header/frame search and retrieval execute; file callbacks/logging/libc copy/compare simulated.',
                  'Byte-level retrieval only, not GUI text conversion, image decode, library registration or physical playback.']}
(tag_path.parent/'stock-frame-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
