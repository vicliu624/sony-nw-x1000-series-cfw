"""Original X1060 audio_ioctl RESET and audio_release on synthetic kernel state."""
from pathlib import Path
import hashlib,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
with (ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').open('rb') as f:
    symbols={s.name:s['st_value'] for s in ELFFile(f).get_section_by_name('.symtab').iter_symbols()}

def run(allocated):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0xc0008000,0x400000);u.mem_write(0xc0008000,raw);u.mem_map(0x60000000,0x40000)
    file,state,out,fragments=0x60001000,0x60002000,0x60003000,0x60004000
    end=0x6003f000;events=[]
    def put(p,v):u.mem_write(p,struct.pack('<I',v))
    def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
    put(file+16,0x60007000);put(file+28,2);put(file+128,state);put(state,out);put(state+40,1)
    put(0x6003a00c,0x60005000);put(0x6003c00c,0x60005000);put(out+56,0x60006000);put(0x60006010,0x60006100)
    put(out+4,fragments if allocated else 0);put(out+8,4096);put(out+16,0);put(out+20,1);put(out+32,4)
    for offset in (48,52,80,84,116,120):put(out+offset,77)
    if allocated:put(fragments,512);put(fragments+16,1024)
    helpers={symbols[n]:n for n in ('memset','audio_stop_dma','dma_free_coherent','kfree','audio_free_irq','audio_request_irq','__down_failed','__up_wakeup','add_wait_queue','remove_wait_queue','schedule_timeout')}
    def hook(uc,pc,size,context):
        if pc==end:uc.emu_stop();return
        name=helpers.get(pc)
        if not name:return
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        if name=='memset':uc.mem_write(a[0],bytes([a[1]&255])*a[2])
        elif name in ('__down_failed','schedule_timeout'):raise AssertionError('unexpected wait after reset: '+name)
        elif name in ('add_wait_queue','remove_wait_queue'):pass
        else:events.append(name)
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    def call(name,args):
        for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
        u.reg_write(UC_ARM_REG_SP,0x6003c000);u.reg_write(UC_ARM_REG_LR,end);u.emu_start(symbols[name],0,count=20000)
        assert u.reg_read(UC_ARM_REG_PC)==end,(name,hex(u.reg_read(UC_ARM_REG_PC)))
    owner=word(symbols['mp200_audio_attach']+0x274)
    put(owner,1);call('mp200_audio_attach',(0,file,state,0));assert u.reg_read(UC_ARM_REG_R0)==0xfffffff0 and not events
    put(owner,0);call('mp200_audio_attach',(0,file,state,0));assert u.reg_read(UC_ARM_REG_R0)==0 and word(owner)==1 and word(file+128)==state
    events.clear();call('mp200_audio_attach',(0,file,state,0));assert u.reg_read(UC_ARM_REG_R0)==0xfffffff0 and not events
    call('audio_ioctl',(0,file,0x5000,0))
    assert u.reg_read(UC_ARM_REG_R0)==0
    assert all(word(out+o)==0 for o in (48,52,80,84,116,120))
    if allocated:assert word(fragments)==word(fragments+16)==0 and events==['audio_stop_dma']
    else:assert not events
    before=len(events)
    call('audio_release',(0,file,0,0))
    assert word(out+4)==0 and word(state+40)==1 and word(owner)==0
    tail=events[before:]
    if allocated:assert tail[:3]==['audio_stop_dma','dma_free_coherent','kfree'],tail
    assert tail[-1]=='audio_free_irq',tail
    return {'allocated_buffer':allocated,'events':events,'reset_clears_queue_counters':True,'release_reaches_end':True,'busy_before_dma_or_irq':True,'exclusive_attach_sets_owner_and_release_clears_it':True}

if __name__=='__main__':
    cases=[run(False),run(True)]
    report={'passed':True,'cases':cases,'kernel_sha256':hashlib.sha256(raw).hexdigest(),'physical_device_accessed':False,'limits':['Original ioctl/reset/sync/release/discard instructions execute; DMA stop/free, IRQ release and allocator effects substituted.','State uses ordinary mode0, exclusive semaphore and write-only file; special mode, active DMA races, blocked writer and actual interrupt scheduling are not qualified.','No proof of original application ownership, mute restoration or acoustic silence.']}
    p=ROOT/'work/qqmusic-preview-audio/stock-reset-release-report.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
