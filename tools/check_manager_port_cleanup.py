"""Stock IPC constructor/exit observer removes port registrations and returns pool slots."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from evidence_checks import verify_report
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];source=ROOT/'work/targets-jp/sysmgrd';raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
exit_source=ROOT/'sources/native-second-entry-manager-reap.json';exit_report=verify_report(ROOT,str(exit_source.relative_to(ROOT)))
exits=[p for row in exit_report['cases'] for p in row['core_observer_packets_before_return'] if p[:2]==[9,3]]
assert exits and all(p==exits[0] for p in exits) and exits[0]==[9,3,0x30001]
exit_packet=exits[0]
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
    if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x60000000,0x20000);u.mem_map(0x50000000,4096)
core,ipc,notification=0x60000000,0x60006000,0x60010000
put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
queued=[]
def hook(uc,pc,size,data):
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    if pc==0x16cb0:assert a[1:3]==[55,0];put(a[0],44)
    elif pc==0x19410:assert a[:2]==[52,32];put(a[2],77)
    elif pc==0x1967c:
        assert a[0]==77 and a[2:]==[52,0];queued.append(list(struct.unpack('<5I',uc.mem_read(a[1],20))))
    elif pc not in (0x1a458,0x1a4f0,0x1a508):return
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(pc,args):
    for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
    u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    u.emu_start(pc,0x50000000,count=30000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
    return u.reg_read(UC_ARM_REG_R0)
call(0xefd4,(ipc,core))
assert [word(core+i) for i in (0x51b4,0x51b8,0x51bc,0x51c0)]==[0xf298,ipc,0xf314,ipc]
assert word(ipc+12)==0x10cd4 and word(ipc+28+8)==32 and word(ipc+28+16)==12
for app,port in ((1,865),(0x30001,643),(0x30001,645)):
    node=call(0x1b858,(ipc+28,));assert node
    call(0x1679c,(node,port,app));assert call(0x1633c,(ipc+8,node))==0
def entries():
    pointer=word(ipc+24);result=[];seen=set()
    while pointer:
        assert pointer not in seen;seen.add(pointer);result.append([word(pointer+4),word(pointer+8)]);pointer=word(pointer)
    return result
rows=[]
for packet,remaining in (([9,2,0x30001],3),([9,3,2],3),(exit_packet,1),(exit_packet,1),([9,3,1],0)):
    before=entries();u.mem_write(notification,struct.pack('<3I',*packet));queued.clear()
    call(word(core+0x51b4),(notification,word(core+0x51b8)))
    assert len(entries())==remaining and word(ipc+28+12)==remaining
    assert queued==[[0xffffffff,0,*packet]]
    if remaining==1:assert entries()==[[1,865]]
    rows.append({'notification_words':packet,'notification_source':'captured-reaper/replayed' if packet==exit_packet else 'control-fixture','before':before,'after':entries(),'pool_used':remaining,'broadcast_queue_prefix':queued[0]})
report={'all_bounded_checks_passed':True,'constructor':'0xefd4','observer':'0xf298','release_callback':'0x10cd4','pool_capacity':32,'cases':rows,
        'exit_notification_input':{'path':str(exit_source.relative_to(ROOT)),'packet':exit_packet},
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),source,exit_source)},
        'limits':['Original constructor,observer registration,pool allocate,list insert/filter/remove and release execute.',
                  'Target exit packet captured from original reaper report; negative/control status notifications supplied.',
                  'Port/queue creation,mutex and queue delivery virtual; no socket or device operation.',
                  'Not yet integrated with saved lifecycle models; no real IPC/thread/cleanup qualification.']}
(ROOT/'sources/native-manager-port-cleanup.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original IPC constructor registers exit observer; target exit removes both port entries, returns slots, preserves Home')
