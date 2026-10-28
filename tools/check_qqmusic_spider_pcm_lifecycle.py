"""Pinned original SpiderApp PCM open/cancel/drain/close, PC-only replay."""
from pathlib import Path
import io,hashlib,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));imports={s['st_value']:s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_info']['type']=='STT_FUNC'}
def run(case):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
    for p in elf.iter_segments():
        if p['p_type']=='PT_LOAD':u.mem_write(p['p_vaddr'],p.data())
    u.mem_map(0x60000000,0x40000);obj,state,config,path,end=0x60001000,0x60002000,0x60003000,0x60004000,0x6003f000;events=[]
    def put(p,v):u.mem_write(p,struct.pack('<I',v))
    def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
    put(obj,state);put(state,0xffffffff);put(state+80,0x60005000);put(0x60006000,5)
    u.mem_write(path,b'/dev/sound/dsp\0');u.mem_write(config,struct.pack('<6I',path,2,16,44100,2,0))
    def ret(v):u.reg_write(UC_ARM_REG_R0,v&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,pc,size,data):
        if pc==end:uc.emu_stop();return
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if pc==0x336be8:put(a[3],0x60008000);ret(0);return
        if pc==0x336dd4:put(a[3],0x60009000);ret(0);return
        if pc==0x3371e4:
            if case=='cancel_wait':put(state+84,1);events.append({'call':'modeled_cancel_during_wait'})
            ret(0);return
        if pc in (0x337334,0x336dc8):ret(0);return
        if pc==0x3373a4:ret(1);return
        if pc==0x337224:events.append({'call':'unregister_wait'});ret(0);return
        if pc==0x336aa0:events.append({'call':'cancel_wakeup','args':a});ret(0);return
        if pc in (0x324e88,0x33d8c0,0x33b83c):ret(0);return
        name=imports.get(pc)
        if name=='strcmp':
            x=bytes(uc.mem_read(a[0],128)).split(b'\0')[0];y=bytes(uc.mem_read(a[1],128)).split(b'\0')[0];ret(0 if x==y else 1)
        elif name=='open':
            assert bytes(uc.mem_read(a[0],15)).split(b'\0')[0]==b'/dev/sound/dsp' and a[1]==0x801
            events.append({'call':'open','flags':a[1]});ret(-1 if case=='open_fail' else 17)
        elif name=='ioctl':
            assert a[0]==17;request=a[1];events.append({'call':'ioctl','request':hex(request)})
            if request in (0xc0045005,0xc0045006,0xc0045002):assert word(a[2])=={0xc0045005:16,0xc0045006:2,0xc0045002:44100}[request]
            else:assert request in (0x5000,0x5001)
            fail={'format_fail':0xc0045005,'channels_fail':0xc0045006,'rate_fail':0xc0045002,'drain_fail':0x5001,'reset_fail':0x5000}.get(case)==request
            ret(-1 if fail else 0)
        elif name=='write':
            assert a[0]==17 and 0<a[2]<=256;events.append({'call':'write','requested':a[2]});ret(-1 if case=='write_fail' else min(a[2],64))
        elif name=='close':assert a[0]==17;events.append({'call':'close'});ret(-1 if case=='close_fail' else 0)
        elif name=='__errno_location':ret(0x60006000)
    u.hook_add(UC_HOOK_CODE,hook)
    def call(entry,args):
        for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),list(args)+[0]*4):u.reg_write(r,v)
        u.reg_write(UC_ARM_REG_SP,0x6003d000);u.reg_write(UC_ARM_REG_LR,end);u.emu_start(entry,0,count=50000)
        assert u.reg_read(UC_ARM_REG_PC)==end,(case,hex(u.reg_read(UC_ARM_REG_PC)))
        return u.reg_read(UC_ARM_REG_R0)
    opened=call(0x3251fc,(obj,config))
    if case in ('open_fail','format_fail','channels_fail','rate_fail'):
        assert opened!=0 and word(state)==0xffffffff
        assert sum(x['call']=='close' for x in events)==(case!='open_fail')
    else:
        assert opened==0 and word(state)==17
        call(0x325840,(obj,));assert word(state+84)==1 and events[-1]['call']=='cancel_wakeup'
        before=len(events);assert call(0x325584,(obj,0x60007000,256))==0x106 and len(events)==before
        call(0x325878,(obj,));assert word(state+84)==0
        if case in ('short_writes','cancel_wait','write_fail'):
            result=call(0x325584,(obj,0x60007000,256));assert events[-1]['call']=='unregister_wait'
            if case=='short_writes':assert result==0 and [x['requested'] for x in events if x['call']=='write']==[256,192,128,64]
            elif case=='cancel_wait':assert result==0x106 and not any(x['call']=='write' for x in events)
            else:assert result==0xc02
            call(0x325878,(obj,))
        call(0x325888,(obj,));assert [x['request'] for x in events if x['call']=='ioctl'][-2:]==['0x5001','0x5000']
        call(0x325518,(obj,));assert word(state)==0xffffffff and events[-1]['call']=='close'
    return {'case':case,'open_return':opened,'events':events,'stored_fd':hex(word(state))}

def renderer(case):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
    for p in elf.iter_segments():
        if p['p_type']=='PT_LOAD':u.mem_write(p['p_vaddr'],p.data())
    u.mem_map(0x60000000,0x40000);obj,state,buffers,end=0x60001000,0x60002000,0x60004000,0x6003f000;events=[]
    def put(p,v):u.mem_write(p,struct.pack('<I',v))
    def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
    put(obj,state);put(state+0x70,buffers);put(state+0x74,2);put(state+0x78,case=='already_quiesced');put(state+0x7c,0x60008000)
    for n in (0x10,0xa0,0x2c):put(state+0x118+n,99)
    component=0x60016000;callback=0x60017000
    put(component+0x3c,callback)
    for port in range(2):
        slot=buffers+port*200;meta=0x60010000+port*128;headers=0x60011000+port*128
        put(slot+0xa0,meta);put(slot+0x88,component);put(meta,headers);put(meta+8,2);put(meta+12,port)
        put(headers+4,0x60018000+port*256);put(headers+28,0x60018080+port*256)
    def hook(uc,pc,size,context):
        if pc==end:uc.emu_stop();return
        value=0;a=uc.reg_read(UC_ARM_REG_R0)
        if pc==0x2c9a40:assert a in (buffers,buffers+200);events.append('clear_link:'+hex(a));return
        if pc==callback:
            assert a==component;events.append('OMX_FreeBuffer');value=0x80001001 if case=='free_buffer_fail' else 0
        elif imports.get(pc)=='OMX_FreeHandle':
            assert a==0x60008000;events.append('OMX_FreeHandle');value=0x80001001 if case=='free_handle_fail' else 0
        elif pc not in (0x2c5cd8,0x2e890c,0x33b83c,0x33d8c0):return
        uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    for reg,v in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_SP,0x6003d000),(UC_ARM_REG_LR,end)):u.reg_write(reg,v)
    u.emu_start(0x2c0c20,0,count=50000);assert u.reg_read(UC_ARM_REG_PC)==end,(case,hex(u.reg_read(UC_ARM_REG_PC)),events)
    assert events[-1]=='OMX_FreeHandle' and events[-3:-1]==['clear_link:'+hex(buffers),'clear_link:'+hex(buffers+200)]
    assert word(state+0x7c)==0 and all(word(state+0x118+n)==0 for n in (0x10,0xa0,0x2c))
    if case=='already_quiesced':assert events.count('OMX_FreeBuffer')==0
    else:assert events.count('OMX_FreeBuffer')==4
    assert word(buffers+0x88)==word(buffers+200+0x88)==0
    return {'case':case,'events':events,'handle_cleared_even_on_free_error':case=='free_handle_fail'}

if __name__=='__main__':
    rows=[run(c) for c in ('normal','open_fail','format_fail','channels_fail','rate_fail','drain_fail','reset_fail','close_fail','short_writes','cancel_wait','write_fail')]
    renderers=[renderer(c) for c in ('normal','already_quiesced','free_handle_fail','free_buffer_fail')]
    report={'passed':True,'binary_sha256':hashlib.sha256(raw).hexdigest(),'cases':rows,'lpcm_renderer_close_cases':renderers,'physical_device_accessed':False,'limits':['Actual open/scalar ioctl/cancel/clear/drain-reset/close instructions run; OS calls, wake transport and logging substituted.','Original write retry loop and waiter cleanup execute; wake/fd registration and wait completion are supplied. Cancellation during wait is modeled; no real concurrent live writer or DMA completion is proved.','Close wrapper marks fd=-1 even when close fails; that state alone cannot certify resource release.','Original LPCM close calls the original per-port FreeBuffer loop, clears links (not a wait), then FreeHandle; callback errors are logged and swallowed. Only component callbacks/logging are substituted; no thread-retirement proof.','Wake request/flag change is not an acknowledgement; call-site ownership and in-flight completion still require proof.']}
    out=ROOT/'work/qqmusic-preview-audio/spider-pcm-lifecycle-report.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'cases':len(rows),'hardware_tested':False}))
