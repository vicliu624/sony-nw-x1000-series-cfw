"""Stock record-ID deletion with original list traversal/unlink; virtual release."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];source=ROOT/'work/targets-jp/sysmgrd';raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
    if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x1000000,0x20000);u.mem_map(0x50000000,4096)
obj=0x1001000;end=0x50000000
put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
nodes={9:0x1009000,10:0x1009100,11:0x1009200}
for index,(identifier,pointer) in enumerate(nodes.items()):
    put(pointer,list(nodes.values())[index+1] if index<2 else 0);put(pointer+4,identifier)
put(obj+4,0x50000100);put(obj+8,0x1006000);put(obj+12,0x1007000);put(obj+16,nodes[9])
released=[]
def hook(uc,pc,size,data):
    if pc==0x50000100:
        pointer=uc.reg_read(UC_ARM_REG_R0);assert pointer in nodes.values()
        assert pointer not in released;released.append(pointer)
    elif pc not in (0x1a4f0,0x1a508):return
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def ids():
    result=[];seen=set();pointer=word(obj+16)
    while pointer:
        assert pointer not in seen and pointer in nodes.values();seen.add(pointer)
        result.append(word(pointer+4));pointer=word(pointer)
    return result
rows=[]
for identifier,expected_ids,expected in ((10,[9,11],0),(9,[11],0),(11,[],0),(11,[],0x111),(999,[],0x111)):
    before=ids();released_before=len(released)
    for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,identifier),(UC_ARM_REG_SP,0x101e000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
    u.emu_start(0x13ae4,end,count=10000)
    assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==expected
    assert ids()==expected_ids
    assert len(released)-released_before==int(expected==0)
    rows.append({'requested_id':identifier,'before_ids':before,'after_ids':ids(),'return':expected,
                 'release_callbacks':len(released)-released_before})
report={'all_bounded_checks_passed':True,'entry':'0x13ae4','cases':rows,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),source)},
        'limits':['List/record IDs and release callback supplied; original search/comparison/unlink execute.',
                  'Mutex and release callback virtual; actual allocator reclamation not established.',
                  'No expiry scheduling, automatic cancellation, outer authorization or persistence replay.',
                  'No host or device storage writes.']}
(ROOT/'sources/native-alarm-record-delete.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original alarm delete: middle/head/last removed once; repeated/missing IDs rejected without release')
