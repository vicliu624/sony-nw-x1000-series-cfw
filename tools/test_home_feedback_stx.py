"""Validate appended labels using stock ARM STX loader and lookup; virtual files only."""
from pathlib import Path
import hashlib,io,json,struct,sys,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.resources import append_stx,parse_stx
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));syms={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
archive=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
rows=[]
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
 for item in tar.getmembers():
    if not(item.name.startswith('./usr/local/share/gemini/res/stx/') and item.name.endswith('.stx')):continue
    original=(ROOT/'work/libc-product-review-0.1.0-dev.16-r4/system-overlay'/item.name.removeprefix('./')).read_bytes();modified=(ROOT/'work/home-feedback-resource-review-1/overlay'/item.name.removeprefix('./')).read_bytes();index=len(parse_stx(original))
    texts=parse_stx(original);assert parse_stx(modified)[:-1]==texts
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
    for segment in elf.iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
    rounded=(len(modified)+4095)&~4095;u.mem_map(0x70000000,rounded);u.mem_write(0x70000000,modified)
    mapping=[]
    def hook(uc,pc,size,data):
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
        if pc==0xec870:pass # Empty initial resource context; no previous mapping/fd.
        elif pc==syms['memset']:uc.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
        elif pc==syms['open']:result=3
        elif pc==syms['read']:assert a[0]==3 and a[2]==64;uc.mem_write(a[1],modified[:64]);result=64
        elif pc==syms['sysconf']:assert a[0]==30;result=4096
        elif pc==syms['__aeabi_uidivmod']:result=a[0]//a[1]
        elif pc==syms['mmap']:
            assert a[:4]==[0,rounded,1,1];mapping.append(a[:4]);result=0x70000000
        else:return
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    def call(pc,a,b):
        for reg,value in ((UC_ARM_REG_R0,a),(UC_ARM_REG_R1,b),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
        u.emu_start(pc,0x50000000,count=100000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
        return u.reg_read(UC_ARM_REG_R0)
    u.mem_write(0x60001000,item.name.encode()+b'\0')
    assert call(0xec8e4,0x60000000,0x60001000)==0 and len(mapping)==1
    for selected in (0,264,index-1,index):
        pointer=call(0xeca30,0x60000000,selected)
        expected='Homebrew unavailable.\nCheck HOMEBREW folder.' if selected==index else texts[selected]
        if expected:
            encoded=expected.encode('utf-16-le')+b'\0\0';assert bytes(u.mem_read(pointer,len(encoded)))==encoded
        else:assert pointer==0
    rows.append({'file':item.name,'new_index':index,'growth_bytes':len(modified)-len(original),'sha256':hashlib.sha256(modified).hexdigest(),'native_loader_lookup_passed':True,'mapped_bytes':rounded})
assert len(rows)==11
report={'scope':'Stock ARM STX loader/lookup; file/sysconf/mmap/division and empty cleanup virtual, no font rendering or hardware','cases':rows,'physical_device_access':False,'firmware_created':False,'passed':True,'new_tid':7309,'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(ROOT/'work/home-feedback-resource-review-1/stx-lookup-report.json').write_text(json.dumps(report,indent=2)+'\n')
print('11 feedback STX files: stock loader and old/new text lookup verified')
