"""Original AudioC mute policy -> original MixerIoctl; physical codec replaced."""
from pathlib import Path
import io,json,struct,hashlib
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from check_qqmusic_spider_pcm_lifecycle import raw,elf,imports,ROOT
kernel=(ROOT/'work/upg-jp/verified-1.bin').read_bytes()
assert hashlib.sha256(kernel).hexdigest()=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
with (ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').open('rb') as f:
    symbols={s.name:s['st_value'] for s in ELFFile(f).get_section_by_name('.symtab').iter_symbols()}
SETTINGS=0xc027a7cc

def replay(source,secondary,initial,codec_fail):
    k=Uc(UC_ARCH_ARM,UC_MODE_ARM);k.mem_map(0xc0008000,0x400000);k.mem_write(0xc0008000,kernel);k.mem_map(0x60000000,0x20000)
    k.mem_write(SETTINGS,struct.pack('<I',initial));calls=[]
    def kw(p):return struct.unpack('<I',k.mem_read(p,4))[0]
    def driver(command,value):
        ptr,end=0x60001000,0x6001f000;k.mem_write(ptr,struct.pack('<I',value))
        def hook(uc,pc,size,data):
            if pc==end:uc.emu_stop();return
            result=0
            if pc==symbols['__get_user_4']:assert uc.reg_read(UC_ARM_REG_R0)==ptr;uc.reg_write(UC_ARM_REG_R2,kw(ptr))
            elif pc==symbols['__put_user_4']:assert uc.reg_read(UC_ARM_REG_R0)==ptr;k.mem_write(ptr,struct.pack('<I',uc.reg_read(UC_ARM_REG_R2)))
            elif pc==symbols['DoMute']:
                mask=uc.reg_read(UC_ARM_REG_R0);wanted=uc.reg_read(UC_ARM_REG_R1);assert mask==31
                calls.append({'codec_mask':mask,'wanted':wanted,'failure':codec_fail})
                if codec_fail:result=0xfffffffb
                else:k.mem_write(SETTINGS,struct.pack('<I',(kw(SETTINGS)&~mask)|(wanted&mask)))
            else:return
            uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        token=k.hook_add(UC_HOOK_CODE,hook)
        for r,v in ((UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,command),(UC_ARM_REG_R3,ptr),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,end)):k.reg_write(r,v)
        k.emu_start(symbols['MixerIoctl'],0,count=10000);k.hook_del(token)
        assert k.reg_read(UC_ARM_REG_PC)==end
        return k.reg_read(UC_ARM_REG_R0),kw(ptr)
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
    for p in elf.iter_segments():
        if p['p_type']=='PT_LOAD':u.mem_write(p['p_vaddr'],p.data())
    u.mem_map(0x60000000,0x20000)
    def put(p,v):u.mem_write(p,struct.pack('<I',v))
    put(0xe17278,17);put(0xe17380,source);put(0xe1732c,secondary);end=0x6001f000
    def hook(uc,pc,size,data):
        if pc==end:uc.emu_stop();return
        if imports.get(pc)!='ioctl':return
        assert uc.reg_read(UC_ARM_REG_R0)==17
        command=uc.reg_read(UC_ARM_REG_R1);pointer=uc.reg_read(UC_ARM_REG_R2);value=struct.unpack('<I',uc.mem_read(pointer,4))[0]
        assert command in (0x80046102,0x40046101)
        result,returned=driver(command,value);uc.mem_write(pointer,struct.pack('<I',returned));uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,end);u.emu_start(0x328020,0,count=10000)
    assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==0
    expected=(initial&16)|(15 if source==10 else 9 if source<=5 else 2)|(3 if secondary else 0)
    final=kw(SETTINGS);assert final==(initial if codec_fail else (initial&~31)|expected)
    assert final&0x100==initial&0x100
    return {'source':source,'secondary_mute':secondary,'initial':initial,'expected_low5':expected,'final':final,'codec_failure':codec_fail,'wrapper_return':0,'readback_mismatch':(final&31)!=expected,'codec_calls':calls}

if __name__=='__main__':
    rows=[replay(s,m,i,f) for s in (0,5,6,10) for m in (0,1) for i in (0x10,0x110) for f in (False,True)]
    report={'passed':True,'cases':rows,'physical_device_accessed':False,'spider_sha256':hashlib.sha256(raw).hexdigest(),'limits':['Original AudioC policy and original kernel ioctl run in separate ARM machines; kernel user-copy and physical DoMute boundary are replaced.','Confirms mask policy/internal-bit preservation and silent failures, not electrical mute, AudioC power/thread completion or complete route restoration.','Successful AudioC return is insufficient: failed physical helper may leave the old state.']}
    (ROOT/'work/qqmusic-preview-audio/audioc-mute-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'cases':len(rows),'hardware_tested':False}))
