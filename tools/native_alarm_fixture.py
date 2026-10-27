"""Host-only stock alarm/cached-battery services; no device refresh or writes."""
import hashlib,io,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

def create(root):
    raw=(root/'work/targets-jp/sysmgrd').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
    for s in ELFFile(io.BytesIO(raw)).iter_segments():
        if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
    u.mem_map(0x1000000,0x20000)
    core,service,request,end=0x1001000,0x1007000,0x1008000,0x1000100
    put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
    word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
    replies=[];persistence=[];state=1;calendar=200
    def hook(uc,pc,size,data):
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
        if pc==0x12034:pass # Physical battery refresh excluded; cached fields supplied.
        elif pc==0x13930:result=100
        elif pc==0x98a0:result=calendar
        elif pc==0x99d8:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
        elif pc==0x143ec:persistence.append(bytes(uc.mem_read(a[1],128)).split(b'\0',1)[0].decode())
        elif pc==0x16d18:
            assert a[:2]==[44,55];length=uc.reg_read(UC_ARM_REG_R3);assert length in (16,20,24,84,1044)
            replies.append(bytes(uc.mem_read(a[2],length)))
        elif pc not in (0x1a458,0x1a4f0,0x1a508,0xa188,0x1c5ac):return
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    def call(pc,args):
        for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):u.reg_write(r,v)
        u.reg_write(UC_ARM_REG_SP,0x101e000);u.reg_write(UC_ARM_REG_LR,end)
        u.emu_start(pc,end,count=30000);assert u.reg_read(UC_ARM_REG_PC)==end
    alarm=core+0x4214;call(0x137e0,(alarm,))
    assert word(alarm+20+8)==16 and word(alarm+20+12)==0
    # Declared empty-argv Walkman record, not a full registration/startup.
    call(0x162b4,(core+8,));record=0x1009000
    put(record+4,432);put(record+8,1);put(record+12,2);put(record+20,0)
    call(0x1633c,(core+8,record))
    def process(packet,state_input=1,calendar_input=200):
        nonlocal state,calendar
        operation=struct.unpack_from('<I',packet,12)[0]
        assert (operation,len(packet)) in ((7,20),(20,128),(22,24),(27,20),(35,20))
        state,calendar=state_input,calendar_input
        replies.clear();persistence.clear()
        put(core+0x503c,state);put(core+0x41c8+20,1);put(service,core);put(service+4,44);u.mem_write(request,packet)
        call({7:0xfb1c,20:0x10088,22:0x10168,27:0x10390,35:0x10750}[operation],(service,request));assert len(replies)==1
        return replies[0],{'native_pool_constructor':True,'native_allocation_and_list':True,
                       'used_slots':word(alarm+20+12),'head':hex(word(alarm+16)),
                       'persistence_captured':persistence.copy(),'core_state_fixture':state,
                       'calendar_result_fixture':calendar,'cached_battery_fixture':1,'physical_battery_refresh_executed':False,
                       'argument_record_fixture':{'id':1,'pid':432,'state':2,'argc':0}}
    return process

def reply(root,packet,state=1,calendar=200):
    return create(root)(packet,state,calendar)
