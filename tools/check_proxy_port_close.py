"""Original proxy transport close/unlink/pool-return with virtual libc only."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];source=ROOT/'work/targets-jp/appproxy';raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
rows=[]
for ports in ((642,643),(644,645)):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x20000)
    elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
    for s in elf.iter_segments():
        if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
    u.mem_map(0x60000000,0x20000);u.mem_map(0x50000000,4096)
    ctx,first,second,mutex,pool=0x1ca5c,0x60001000,0x60002000,0x60003000,0x60004000
    put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
    word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
    string=lambda p:bytes(u.mem_read(p,128)).split(b'\0',1)[0].decode()
    events=[]
    def hook(uc,pc,size,data):
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
        if pc==symbols['close']:assert a[0] in (101,102);events.append({'close':a[0]})
        elif pc==symbols['snprintf']:
            assert string(a[2])=='%s.%d' and string(a[3])=='/tmp/apfsock/apfsock'
            port=word(uc.reg_read(UC_ARM_REG_SP));text=(string(a[3])+'.'+str(port)).encode();assert len(text)<a[1]
            uc.mem_write(a[0],text+b'\0');result=len(text)
        elif pc==symbols['unlink']:events.append({'unlink':string(a[0])})
        elif pc==symbols['free']:assert a[0]==mutex;events.append({'free_mutex':hex(a[0])})
        elif pc not in (symbols['pthread_mutex_destroy'],symbols['pthread_mutex_lock'],symbols['pthread_mutex_unlock'],symbols['pthread_cond_signal']):return
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    def call(pc,args):
        for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
        u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
        u.emu_start(pc,0x50000000,count=20000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
    for obj,port,fd in ((first,ports[0],101),(second,ports[1],102)):
        call(0xd214,(obj,port,0,0))
        # Actual open routine assigns this readonly callback to object+4.
        assert word(0xd7e0)==0xd594;put(obj+4,word(0xd7e0));put(obj+40,fd)
    put(ctx+16,first);put(ctx+28,second);put(ctx+40,mutex);put(0x1cb10,pool);put(pool+88,2)
    call(0x9a0c,(ctx,))
    assert events==[{'free_mutex':hex(mutex)},{'close':101},{'unlink':'/tmp/apfsock/apfsock.'+str(ports[0])},{'close':102},{'unlink':'/tmp/apfsock/apfsock.'+str(ports[1])}]
    assert word(pool+88)==0 and word(pool+80)==second and word(second)==first and word(first)==0
    rows.append({'port_fixture':list(ports),'events':events,'pool_used_after':word(pool+88),'returned_objects':2})
report={'all_bounded_checks_passed':True,'entry':'0x9a0c','cases':rows,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),source)},
        'limits':['Original transport object constructor, close dispatch, unlink formatting and pool return execute.',
                  'Object bindings/fds/mutex/pool used-count supplied; native socket open not executed.',
                  'Libc close/unlink/free/pthread interfaces virtual; no host or device files changed.',
                  'Does not remove manager event-registry entries or prove real socket/IPC cleanup and error handling.']}
(ROOT/'sources/native-proxy-port-close.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original proxy closes/unlinks both socket endpoints and returns two transport objects; virtual libc only')
