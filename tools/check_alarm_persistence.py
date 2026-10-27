"""Stock alarm DB serialization to virtual file; never opens a host/device file."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'work/targets-jp/sysmgrd';raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
rows=[]
for count in (0,1,16,17,32):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
    for s in ELFFile(io.BytesIO(raw)).iter_segments():
        if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
    u.mem_map(0x1000000,0x20000)
    obj,name,end=0x1001000,0x1007000,0x1000100
    u.mem_write(name,b'/var/apfalarm.db\0')
    records=[bytes([i+1])*120 for i in range(count)]
    for i,record in enumerate(records):
        next_node=0x1009000+256*(i+1) if i+1<count else 0
        u.mem_write(0x1009000+256*i,struct.pack('<I',next_node)+record)
    u.mem_write(obj+12,struct.pack('<2I',0x1006000,0x1009000 if count else 0))
    state={'file':b'X'*4096,'position':0,'open':False};calls=[]
    def hook(uc,pc,size,data):
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
        if pc==0x16498:
            sp=uc.reg_read(UC_ARM_REG_SP)
            capacity,out=struct.unpack('<2I',uc.mem_read(sp,8));assert capacity==16
            calls.append({'collect_capacity':capacity,'input_list_nodes':count,'original_collector_executed':True})
            return
        elif pc==0x9ca8:
            path=bytes(uc.mem_read(a[0],128)).split(b'\0',1)[0].decode()
            assert path=='/var/apfalarm.db' and a[1]==0xa41 and a[2]==0x180
            assert not state['open'];state.update(file=b'',position=0,open=True)
            calls.append({'open':path,'flags':a[1],'permissions':a[2]});result=77
        elif pc==0x9924:
            assert a[0]==77 and state['open']
            piece=bytes(uc.mem_read(a[1],a[2]));state['file']+=piece;state['position']+=len(piece)
            calls.append({'write_bytes':len(piece)});result=len(piece)
        elif pc==0x9960:
            assert a[0]==77 and state['open'];state['open']=False;calls.append({'close':77})
        elif pc not in (0x9b40,0x1a4f0,0x1a508):return
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,name),(UC_ARM_REG_SP,0x101e000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
    u.emu_start(0x143ec,end,count=20000)
    assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==0
    assert state['file']==b'\x01\x00'+b''.join(records[:16]) and not state['open']
    for i,record in enumerate(records):
        assert bytes(u.mem_read(0x1009000+256*i+4,120))==record
    rows.append({'input_list_nodes':count,'serialized_records':min(count,16),'prior_virtual_file_bytes':4096,
                 'result_bytes':len(state['file']),'calls':calls,
                 'file_sha256':hashlib.sha256(state['file']).hexdigest()})
report={'all_bounded_checks_passed':True,'entry':'0x143ec','cases':rows,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),source)},
        'limits':['Original collector executes over supplied linked lists0/1/16/17/32; locks virtual, no insertion/expiry.',
                  'Original serializer/open flags/write/close wrappers execute, syscall responses virtual.',
                  'Full writes only; short writes, disk-full, power loss and durability not qualified.',
                  '16 is collector request capacity here, not proof of global record/list upper limit.',
                  'No host file or device storage writes.']}
(ROOT/'sources/native-alarm-persistence.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original collector/serializer:0/1/16/17/32 nodes ->2/122/1922/1922/1922 bytes; virtual file only')
