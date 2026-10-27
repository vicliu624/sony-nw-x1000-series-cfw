"""Stock alarm16-slot pool/list init, exhaustion, removal and reuse."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];source=ROOT/'work/targets-jp/sysmgrd';raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
    if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x1000000,0x20000);u.mem_map(0x50000000,4096)
obj=0x1001000;pool=obj+20;end=0x50000000
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
release_calls=[]
def hook(uc,pc,size,data):
    if pc==0x1450c:release_calls.append(hex(uc.reg_read(UC_ARM_REG_R0)));return
    if pc not in (0x1a458,0x1a4f0,0x1a508):return
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(pc,args):
    for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
    u.reg_write(UC_ARM_REG_SP,0x101e000);u.reg_write(UC_ARM_REG_LR,end)
    u.emu_start(pc,end,count=20000);assert u.reg_read(UC_ARM_REG_PC)==end
    return u.reg_read(UC_ARM_REG_R0)
call(0x137e0,(obj,))
assert word(obj+4)==0x1450c and word(obj+8)==obj
assert word(pool+8)==16 and word(pool+12)==0 and word(pool+16)==124
nodes={}
for identifier in range(16):
    pointer=call(0x1b858,(pool,));assert pointer and pointer not in nodes.values()
    assert obj+40<=pointer<obj+40+16*124
    put(pointer+4,identifier)
    assert call(0x1633c,(obj,pointer))==0
    nodes[identifier]=pointer
assert word(pool+12)==16
assert call(0x1b858,(pool,))==0 and word(pool+12)==16
assert call(0x13ae4,(obj,7))==0 and word(pool+12)==15
assert release_calls==[hex(nodes[7])]
reused=call(0x1b858,(pool,));assert reused==nodes[7] and word(pool+12)==16
put(reused+4,100);assert call(0x1633c,(obj,reused))==0
for identifier in [i for i in range(16) if i!=7]+[100]:
    assert call(0x13ae4,(obj,identifier))==0
assert word(obj+16)==0 and word(pool+12)==0 and len(release_calls)==17
assert call(0x13ae4,(obj,100))==0x111 and word(pool+12)==0
free_nodes=[];pointer=word(pool)
while pointer:
    assert pointer not in free_nodes;free_nodes.append(pointer);pointer=word(pointer)
assert len(free_nodes)==16 and set(free_nodes)==set(nodes.values())
report={'all_bounded_checks_passed':True,'constructor':'0x137e0',
        'pool_capacity':16,'slot_bytes':124,'initial_allocator_used':0,
        'exhausted_allocation':0,'native_release_callback':'0x1450c',
        'freed_slot_reused':True,'release_calls':release_calls,
        'final_used':word(pool+12),'final_free_slots':len(free_nodes),
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),source)},
        'limits':['Original constructor/pool allocate/list insert/delete/release/reallocate execute; mutex services virtual.',
                  'Record IDs supplied directly; no timing, expiry, APF transport, file persistence or hardware test.',
                  'Bound applies to this stock alarm pool, not every system service or partition.']}
(ROOT/'sources/native-alarm-native-pool.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original alarm16-slot pool: full rejects, deletion returns slot, exact slot reused, all16 recovered')
