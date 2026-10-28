"""Replay pinned Sony dsp_play instructions on PC; never opens device nodes.

Keeps original playback control and OSS wrapper instructions. WAV metadata,
stdio, allocation and hardware syscalls are explicit synthetic boundaries.
This proves call ordering/failure branches, not ownership or audible playback.
"""
from pathlib import Path
import hashlib, io, json, struct, tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1]
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin') as archive:
    raw=archive.extractfile('./usr/local/bin/dsp_play').read()
assert hashlib.sha256(raw).hexdigest()=='c7888a19db990a93209164ef848949b0ed8b1508c23bb79b32402d61eac5e95e'
elf=ELFFile(io.BytesIO(raw))
imports={s['st_value']:s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_info']['type']=='STT_FUNC'}
REGS=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)
wave={0xb630:'wave_construct',0xb2b8:'wave_open',0xb20c:'wave_close',0xb1e0:'wave_format',0xb1b4:'wave_bits',0xb118:'wave_channels',0xb0ac:'wave_rate',0xafec:'wave_bytes',0xafc0:'wave_average',0xaf84:'wave_read'}

def replay(case):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    pages=set()
    for p in elf.iter_segments():
        if p['p_type']!='PT_LOAD':continue
        for address in range(p['p_vaddr']&~4095,(p['p_vaddr']+p['p_memsz']+4095)&~4095,4096):
            if address not in pages:u.mem_map(address,4096);pages.add(address)
        u.mem_write(p['p_vaddr'],p.data())
    u.mem_map(0x60000000,0x40000)
    end=0x6003f000;heap=0x60010000;events=[];requests=[];writes=0
    u.mem_write(0x60001000,b'/dev/sound/dsp\0')
    u.mem_write(0x60001100,b'/contents/HOMEBREW/data/qqmusic/synthetic.wav\0')
    def getstr(p):return bytes(u.mem_read(p,1024)).split(b'\0',1)[0].decode('ascii')
    def integer(p):return struct.unpack('<I',u.mem_read(p,4))[0]
    def ret(v):u.reg_write(UC_ARM_REG_R0,v&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,pc,size,context):
        nonlocal heap,writes
        if pc==end:uc.emu_stop();return
        a=[uc.reg_read(r) for r in REGS]
        if pc in wave:
            name=wave[pc]
            if name in ('wave_open','wave_close'):events.append(name)
            value={'wave_construct':0,'wave_open':0,'wave_close':0,'wave_format':1,'wave_bits':16,'wave_channels':2,'wave_rate':44100,'wave_bytes':1536,'wave_average':176400}.get(name)
            if name=='wave_read':uc.mem_write(a[1],b'\0'*a[2]);value=a[2]
            ret(value);return
        name=imports.get(pc)
        if not name:return
        if name=='open':
            assert getstr(a[0])=='/dev/sound/dsp' and a[1]==1
            events.append('open');ret(-1 if case=='open_fail' else 17)
        elif name=='ioctl':
            assert a[0]==17
            request=a[1];requests.append(hex(request));events.append('ioctl:'+hex(request))
            fail={'reset_fail':0x5000,'format_fail':0xc0045005,'channels_fail':0xc0045006,'rate_fail':0xc0045002,'block_fail':0xc0045004,'drain_fail':0x5001}.get(case)==request
            if request==0xc0045004:uc.mem_write(a[2],struct.pack('<I',1024))
            elif request in (0xc0045005,0xc0045006,0xc0045002):
                wanted=integer(a[2]);assert wanted=={0xc0045005:16,0xc0045006:2,0xc0045002:44100}[request]
                if case=='format_mismatch' and request==0xc0045005:uc.mem_write(a[2],struct.pack('<I',8))
            else:assert request in (0x5000,0x5001)
            ret(-1 if fail else 0)
        elif name=='write':
            assert a[0]==17 and 0<a[2]<=1024
            events.append('write');writes+=1;ret(-1 if case=='write_fail' else a[2]-1 if case=='short_write' else a[2])
        elif name=='close':
            events.append('close');assert a[0]==17 or (a[0]==0xffffffff and case=='open_fail');ret(-1 if case=='close_fail' else 0)
        elif name=='malloc':heap=(heap+15)&~15;pointer=heap;heap+=a[0];assert heap<0x60030000;ret(pointer)
        elif name=='free':ret(0)
        elif name=='memset':uc.mem_write(a[0],bytes([a[1]&255])*a[2]);ret(a[0])
        elif name in ('printf','fprintf','perror'):ret(0)
        elif name in ('__aeabi_i2d','__aeabi_dadd','__aeabi_ddiv'):
            if name=='__aeabi_i2d':value=float(struct.unpack('<i',struct.pack('<I',a[0]))[0])
            else:
                x=struct.unpack('<d',struct.pack('<II',a[0],a[1]))[0];y=struct.unpack('<d',struct.pack('<II',a[2],a[3]))[0]
                value=x+y if name=='__aeabi_dadd' else x/y
            lo,hi=struct.unpack('<II',struct.pack('<d',value));uc.reg_write(UC_ARM_REG_R1,hi);ret(lo)
        else:raise AssertionError(('unexpected import',name,hex(pc)))
    u.hook_add(UC_HOOK_CODE,hook)
    for reg,value in ((UC_ARM_REG_R0,0x60001000),(UC_ARM_REG_R1,0x60001100),(UC_ARM_REG_R2,0),(UC_ARM_REG_SP,0x6003d000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
    u.emu_start(0x9bfc,0,count=100000)
    assert u.reg_read(UC_ARM_REG_PC)==end,(case,hex(u.reg_read(UC_ARM_REG_PC)))
    assert events[-1]=='close',(case,events)
    if case=='normal':
        assert requests==['0x5000','0xc0045005','0xc0045006','0xc0045002','0xc0045004','0x5001']
        assert writes==2 and events.index('ioctl:0x5001')>events.index('write')
    if case in ('write_fail','short_write'):assert writes==1 and '0x5001' in requests
    return {'case':case,'return_u32':u.reg_read(UC_ARM_REG_R0),'events':events,'requests':requests,'writes':writes}

if __name__=='__main__':
    cases=[replay(c) for c in ('normal','open_fail','reset_fail','format_fail','format_mismatch','channels_fail','rate_fail','block_fail','write_fail','short_write','drain_fail','close_fail')]
    report={'passed':True,'original_binary_sha256':hashlib.sha256(raw).hexdigest(),'original_entry':'0x9bfc','cases':cases,'physical_device_accessed':False,'limits':['WAV metadata, heap, libc and device syscalls are synthetic; original playback control and device wrapper instructions execute.','Normal EOF uses OSS sync0x5001 before close; this is not proof of bounded stop/reset, mixer restoration or framework ownership.','The stock diagnostic tool is not the complete SpiderApp music playback path; no acoustic or hardware timing evidence.']}
    out=ROOT/'work/qqmusic-preview-audio';out.mkdir(exist_ok=True);(out/'stock-dsp-play-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(cases),'hardware_tested':False}))
