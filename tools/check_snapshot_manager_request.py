"""Replay captured snapshot request in stock manager; persistence captured only."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from evidence_checks import verify_report
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'sources/native-snapshot-apf-request.json';up=verify_report(ROOT,str(source.relative_to(ROOT)))
packet=bytes.fromhex(next(c['packet_hex'] for c in up['cases'] if c['client_state_fixture']==2 and c['reply_status_fixture']==0))
raw=(ROOT/'work/targets-jp/sysmgrd').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
rows=[]
for state,future,available,repetitions in ((1,200,True,2),(1,50,True,1),(1,200,False,1),(4,200,True,1)):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
    for s in ELFFile(io.BytesIO(raw)).iter_segments():
        if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
    u.mem_map(0x1000000,0x20000)
    core,service,request,end=0x1001000,0x1007000,0x1008000,0x1000100
    put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
    word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
    put(core+0x503c,state);put(core+0x4214+0x950,9);put(service,core);put(service+4,44)
    u.mem_write(request,packet);allocations=[];insertions=[];persist=[];replies=[];calendar_inputs=[]
    def hook(uc,pc,size,data):
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
        if pc==0x13930:result=100
        elif pc==0x98a0:
            calendar_inputs.append(bytes(uc.mem_read(a[0],44)).hex());result=future
        elif pc==0x1b858:
            result=0x1009000+len(allocations)*256 if available else 0
            if result:allocations.append(result)
        elif pc==0x99d8:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
        elif pc==0x1633c:insertions.append(a[:2])
        elif pc==0x143ec:
            name=bytes(uc.mem_read(a[1],128)).split(b'\0',1)[0].decode()
            persist.append({'object':hex(a[0]),'name':name})
        elif pc==0x16d18:
            assert a[:2]==[44,55];replies.append(list(struct.unpack('<5I',uc.mem_read(a[2],20))))
        elif pc not in (0x16b7c,0xa188,0x1c5ac):return
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    for iteration in range(repetitions):
        for reg,value in ((UC_ARM_REG_R0,service),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x101e000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
        u.emu_start(0x10088,end,count=10000);assert u.reg_read(UC_ARM_REG_PC)==end
    expected=0x1d03 if state==4 else 0x102 if future<=100 else 0x1d01 if not available else 0
    assert len(replies)==repetitions and all(r[:4]==[20,0,20,expected] for r in replies)
    count=repetitions if expected==0 else 0
    assert len(allocations)==count and len(insertions)==count and len(persist)==count
    assert word(core+0x4214+0x950)==9+count
    nodes=[list(struct.unpack('<4I',u.mem_read(p+4,16))) for p in allocations]
    if count:assert nodes==[[9+i,1,100,0] for i in range(count)]
    rows.append({'core_state_fixture':state,'calendar_result_fixture':future,'allocation_available':available,
                 'repeated_identical_requests':repetitions,'replies':replies,'allocated_nodes':nodes,
                 'calendar_inputs':calendar_inputs,'persistence_calls':persist,
                 'record_counter_after':word(core+0x4214+0x950)})
inputs=[Path(__file__),source,ROOT/'work/targets-jp/sysmgrd']
report={'all_bounded_checks_passed':True,'entry':'0x10088','operation_decimal':20,'cases':rows,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'limits':['Exact captured request; sender authentication and outer dispatch not executed.',
                  'Clock/calendar/allocation/list insertion/reply/persistence boundaries virtual.',
                  'Persistence filename captured, contents/open mode/partition growth not established.',
                  'No actual disk or device writes; record cleanup/expiry not replayed.']}
(ROOT/'sources/native-snapshot-manager-request.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'cases':len(rows),'persistence':rows[0]['persistence_calls'],'nodes':rows[0]['allocated_nodes']}))
