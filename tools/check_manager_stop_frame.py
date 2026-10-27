"""Stock manager notification queue/framing from captured change notification."""
from pathlib import Path
import argparse,hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from evidence_checks import verify_report
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--activation-return-report');args=parser.parse_args()
source=(ROOT/(args.activation_return_report or 'sources/native-manager-home-activation-exec.json')).resolve();assert source.is_relative_to(ROOT/'sources')
event=5 if args.activation_return_report else 6
up=verify_report(ROOT,str(source.relative_to(ROOT)))
inputs=[c['native_walkman_activation']['notifications'][0] for c in up['cases']] if args.activation_return_report else [c['notifications'][0] for c in up['cases']]
assert inputs and all(x=={'recipient':1,'packet':[event,0,0]} for x in inputs)
binary=ROOT/'work/targets-jp/sysmgrd';raw=binary.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
    if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x60000000,0x20000);u.mem_map(0x50000000,4096)
ipc,node,packet,end=0x60001000,0x60002000,0x60003000,0x50000000
put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
put(ipc+4,44);put(ipc+0x1b0,77);put(ipc+24,node)
u.mem_write(node,struct.pack('<3I',0,1,501));u.mem_write(packet,struct.pack('<3I',*inputs[0]['packet']))
queue=[];queued=[];frames=[];empty=False
def hook(uc,pc,size,data):
    global empty
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    if pc==0x1967c:
        assert a[0]==77 and a[2:]==[52,0]
        item=bytes(uc.mem_read(a[1],52));queue.append(item);queued.append(item)
    elif pc==0x1978c:
        assert a[0]==77 and a[2:]==[52,0]
        if not queue:empty=True;uc.emu_stop();return
        uc.mem_write(a[1],queue.pop(0))
    elif pc==0x16d18:
        assert a[:2]==[44,501] and a[3]==20
        frames.append(bytes(uc.mem_read(a[2],20)))
    elif pc not in (0x1a4f0,0x1a508):return
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def start(pc,args):
    for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):u.reg_write(r,v)
    u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,end)
    u.emu_start(pc,end,count=20000)
start(0xf314,(packet,1,ipc));assert u.reg_read(UC_ARM_REG_PC)==end and len(queue)==1
start(0xf0fc,(ipc,));assert empty and not queue
assert frames==[struct.pack('<5I',20,0,event,0,0)]
paths=[Path(__file__),source,binary]
report={'all_bounded_checks_passed':True,'source_notification':inputs[0],
        'queue_entry':'0xf314','framing_entry':'0xf0fc','queue_item_bytes':52,
        'notification_hex':frames[0].hex(),'destination_port_fixture':501,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'limits':['Upstream original-manager notification comes from separate modeled lifecycle.',
                  'Queue, event-port registry and transport are virtual fixtures; original framing/list filtering execute.',
                  'No real IPC thread/queue or device execution.']}
(ROOT/('sources/native-manager-return-frame.json' if args.activation_return_report else 'sources/native-manager-stop-frame.json')).write_text(json.dumps(report,indent=2)+'\n')
print(f'Captured manager notification{event} ->original queue/framing ->20-byte frame for port501')
