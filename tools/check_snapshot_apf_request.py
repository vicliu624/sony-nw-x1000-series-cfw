"""Original snapshot APF client packet construction; virtual transport only."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR
from evidence_checks import verify_report
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'sources/native-stop-event-consumer.json'
upstream=verify_report(ROOT,str(source.relative_to(ROOT)))
payload=bytes.fromhex(upstream['snapshot_present_path']['payload_hex']);assert len(payload)==108
base=ROOT/'tools/check_spider_restore_dispatch.py'
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(base))
call=m['call'];g=call.__globals__;u=g['u']
g['intercept_actions']=False;g['deactivate_probe']=False
client,buffer,result=0x60012000,0x60012200,0x60012300
packets=[];reply_status=0
def hook(uc,pc,size,data):
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    value=0
    if pc==0xd574:uc.mem_write(a[0],bytes([a[1]&255])*a[2]);value=a[0]
    elif pc==0xd85c:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));value=a[0]
    elif pc==0x268c9c:
        assert a[:2]==[500,55] and a[3]==128
        packet=bytes(uc.mem_read(a[2],128));assert packet[20:]==payload
        assert list(struct.unpack('<5I',packet[:20]))==[128,0,1,20,55]
        packets.append(packet)
    elif pc==0x268d48:
        assert a[0]==500 and a[2]==20 and len(packets)==1
        uc.mem_write(a[1],struct.pack('<5I',20,0,20,reply_status,77));uc.mem_write(a[3],struct.pack('<I',20))
    elif pc not in (0x337a80,0x337ae8):return
    uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
handle=u.hook_add(UC_HOOK_CODE,hook)
rows=[]
for state,reply_status in ((0,0),(1,0),(2,0),(3,0),(2,0x123)):
    data=bytearray(44)
    for offset,value in ((0,1),(4,state),(12,55),(16,500),(20,0),(40,88)):struct.pack_into('<I',data,offset,value)
    u.mem_write(client,bytes(data));u.mem_write(buffer,payload);u.mem_write(result,struct.pack('<I',0xdeadbeef));packets.clear()
    returned=call(0x266fd0,(client,buffer,result,0))
    admitted=state not in (0,1)
    assert returned==(reply_status if admitted else 0x1d09)
    sequence=struct.unpack('<I',u.mem_read(client+20,4))[0];assert sequence==int(admitted)
    output=struct.unpack('<I',u.mem_read(result,4))[0]
    assert output==(77 if admitted and reply_status==0 else 0xdeadbeef)
    assert len(packets)==int(admitted)
    rows.append({'client_state_fixture':state,'reply_status_fixture':reply_status,
                 'return':returned,'sequence_after':sequence,'output':output,
                 'packet_hex':packets[0].hex() if packets else None})
u.hook_del(handle)
inputs=[Path(__file__),base,source,ROOT/'work/targets-jp/SpiderApp']
report={'all_bounded_checks_passed':True,'client_entry':'0x266fd0','operation_decimal':20,
        'packet_bytes':128,'payload_bytes':108,'cases':rows,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'limits':['Payload is actual upstream modeled snapshot, not a physical player record.',
                  'Mutex/libc/IPC send/receive virtual; response status supplied.',
                  'Manager operation20 handler and persistence not executed.',
                  'No device or disk write, network, firmware package or hardware qualification.']}
(ROOT/'sources/native-snapshot-apf-request.json').write_text(json.dumps(report,indent=2)+'\n')
print('Five original APF snapshot client cases passed; operation20,128-byte request,108-byte payload')
