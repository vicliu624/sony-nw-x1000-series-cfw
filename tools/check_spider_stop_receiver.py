"""Original APF registration and stop receive loop, with virtual notification transport."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from evidence_checks import verify_report
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'tools/check_spider_restore_dispatch.py'
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(base))
u=m['u'];g=m['call'].__globals__;g['intercept_actions']=False;g['deactivate_probe']=False
ctx=0x820f68;received=0;returned_to_receive=False;callbacks=[]
notification_source=ROOT/'sources/native-manager-stop-frame.json'
frame=verify_report(ROOT,str(notification_source.relative_to(ROOT)))
notification=bytes.fromhex(frame['notification_hex'])
assert notification==struct.pack('<5I',20,0,6,0,0)
def put(a,v):u.mem_write(a,struct.pack('<I',v))
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def hook(uc,pc,size,data):
    global received,returned_to_receive
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    if pc==0xeb9c:callbacks.append(hex(pc));return
    if pc==0x268d48:
        if received:
            returned_to_receive=True;uc.emu_stop();return
        uc.mem_write(a[1],notification);put(a[3],len(notification));received+=1
    elif pc not in (0x337a80,0x337ae8,0xe5ac,0xb00bc,0x33b918):return
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_R7,0x60010000)
u.emu_start(0xfcb4,0xfd68,count=10000)
assert word(ctx+0x2c+6*4)==0xeb9c
for offset,value in ((4,2),(0x24,1),(0x1c,501),(0,1),(0x10,500),(0xc,55)):put(ctx+offset,value)
g['queued'].clear()
u.reg_write(UC_ARM_REG_R0,ctx);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
u.emu_start(0x26551c,0x50000000,count=100000)
assert returned_to_receive and received==1
assert callbacks==['0xeb9c'] and g['queued']==[[0x420024,0,0,0]]
inputs=[Path(__file__),base,notification_source,ROOT/'work/targets-jp/SpiderApp']
report={'all_bounded_checks_passed':True,'registration_range':['0xfcb4','0xfd68'],
        'receiver_entry':'0x26551c','client_initial_state_fixture':2,
        'client_state_after':word(ctx+4),'native_manager_notification_hex':notification.hex(),
        'callbacks':callbacks,'queued':[p.copy() for p in g['queued']],
        'returned_to_receive':returned_to_receive,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'limits':['Notification bytes captured from original-manager modeled framing, not live OS queue.',
                  'Original registration/setters/receive dispatch/callback execute; locks/logging/receive virtual.',
                  'Root queue captured, not consumed here; no device execution or hardware qualification.']}
(ROOT/'sources/native-spider-stop-receiver.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original stop receiver invoked registered slot6 and queued420024; state after:',word(ctx+4))
