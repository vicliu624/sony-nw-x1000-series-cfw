"""Original SpiderApp operation8 -> original manager USB ioctl translation; virtual driver only."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR
from native_lookup_fixture import lookup,request_in_session
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'tools/check_spider_restore_dispatch.py'
config=ROOT/'work/integration-0.1.0-dev.16/system-overlay/etc/AppList.conf'
bootstrap=struct.pack('<5I',276,0,1,36,864)+b'SpiderApp\0'+bytes(246)
assert len(bootstrap)==276
session={};parser={};reply,_=lookup(ROOT,bootstrap,config_bytes=config.read_bytes(),details=parser,session=session)
assert struct.unpack('<5I',reply)==(20,0,36,0,1)
manager=session['emulator'];core=session['core'];session['request_address']=0x6001b000
session['usb_fd_fixture']=91;manager.mem_write(core+0x41c8,struct.pack('<I',91))
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(base))
u=m['u'];call=m['call'];ctx=0x820f68;out=0x60013000;pending=None;requests=[];responses=[]

def hook(uc,pc,size,data):
    global pending
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];value=0
    if pc==0x337960:uc.mem_write(a[0],struct.pack('<I',88))
    elif pc==0x268c9c:
        assert a[:2]==[500,55] and a[3]==20
        packet=bytes(uc.mem_read(a[2],20));assert list(struct.unpack('<5I',packet))==[20,0,1,8,864]
        details={};pending,_=request_in_session(session,packet,details=details);requests.append(packet.hex());responses.append({'reply_hex':pending.hex(),'manager':details})
    elif pc==0x268d48:
        assert a[0]==500 and a[2]==20 and pending is not None
        uc.mem_write(a[1],pending);uc.mem_write(a[3],struct.pack('<I',20));pending=None
    elif pc not in (0x337a80,0x337ae8,0xb00bc,0x33b918,0x33b83c):return
    uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
rows=[]
for raw,expected in ((0,0),(1,2),(2,4),(3,3),(4,1)):
    assert call(0x2652e0,(ctx,))==0
    for offset,value in ((0,1),(4,1),(12,864),(16,500)):
        u.mem_write(ctx+offset,struct.pack('<I',value))
    session['usb_raw_state_fixture']=raw
    u.mem_write(out,bytes.fromhex('efbeadde'))
    assert call(0xb0764,(out,))==0
    result=struct.unpack('<I',u.mem_read(out,4))[0]
    assert result==expected and struct.unpack('<I',u.mem_read(ctx+20,4))[0]==1
    response=responses[-1];assert list(struct.unpack('<5I',bytes.fromhex(response['reply_hex'])))==[20,0,8,0,expected]
    assert response['manager']['usb_state_queries_virtual']==[{'fd_fixture':91,'request':'0x80046701','raw_state_fixture':raw}]
    rows.append({'driver_raw_state_fixture':raw,'client_result':result,'request_hex':requests[-1],**response})
paths=[Path(__file__),base,ROOT/'tools/native_lookup_fixture.py',config,ROOT/'work/targets-jp/SpiderApp',ROOT/'work/targets-jp/sysmgrd']
r={'all_bounded_checks_passed':True,'client_wrapper':'0xb0764','client_request':'0x267b94','manager_chain':['0xfb88','0xcf50','0x12250','0x175e4'],'ioctl':'0x80046701','native_config_parser':parser,'same_manager_for_all_cases':True,'cases':rows,
   'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
   'limits':['Registered client fields/PID/descriptor91 and raw ioctl states are fixtures; original client constructor/wrapper/request/reply and manager translation execute.',
             'Manager config parsed once by original1574c via bootstrap lookup; same query model reused, no process registration/full startup established.',
             'No actual ioctl/device driver execution. Zero query result does not prove USB physically disconnected: stock authority can mask status, per separate driver evidence.',
             'Core mode2 supplied; rejection modes4/5 and ioctl failures not covered here. No physical device, storage write or firmware output.']}
(ROOT/'sources/native-usb-state-query.json').write_text(json.dumps(r,indent=2)+'\n')
print('Original operation8 USB state client/manager translation passed5 raw-state cases')
