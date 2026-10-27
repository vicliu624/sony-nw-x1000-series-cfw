"""Capture stock Responder SpiderApp lookup/switch requests; virtual IPC only."""
from pathlib import Path
import argparse,hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--consume-lookup-report',action='store_true',help='Use original manager lookup reply instead of hand-written success ID.')
options=parser.parse_args()
lookup_input=None
if options.consume_lookup_report:
    lookup_path='sources/native-walkman-lookup-service.json'
    lookup_raw=(ROOT/lookup_path).read_bytes();lookup=json.loads(lookup_raw)
    assert lookup['all_passed'] and lookup['sysmgrd_sha256']=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
    response=next(r['reply'] for r in lookup['cases'] if r['case']=='captured')
    assert response==[20,55,36,0,1]
    lookup_input={'path':lookup_path,'sha256':hashlib.sha256(lookup_raw).hexdigest(),'reply':response}
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:binary=tar.extractfile('./usr/local/bin/Responder').read()
digest=hashlib.sha256(binary).hexdigest()
assert digest=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
rows=[]
for name,query_error,switch_error in [('success',0,0),('lookup-error',0x1d04,0),('switch-error',0,0x1d04)]:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0xc00000)
    for segment in ELFFile(io.BytesIO(binary)).iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    u.mem_map(0x2000000,0x10000)
    ctx,end=0x6b2ccc,0x2001000
    put=lambda p,v:u.mem_write(p,struct.pack('<I',v))
    for offset,value in ((0,2),(4,2),(12,66),(16,77),(20,55),(40,88)):put(ctx+offset,value)
    requests=[];replies=[]
    def hook(uc,pc,size,unused):
        if pc==end:uc.emu_stop();return
        helpers=(0xfcd4,0x11d1c,0x1f3bf0,0x1f3b14,0x1f0068,0x1f00d0,0xb7c8,0x1f1a5c,0x183618,0x1836c4)
        if pc not in helpers:return
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
        if pc==0xfcd4:result=1 # supplied original branch-selection boundary, not physical USB status
        elif pc==0xb7c8:uc.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
        elif pc==0x1f1a5c:
            value=bytes(uc.mem_read(a[2],128)).split(b'\0',1)[0]
            assert value==b'SpiderApp' and len(value)+1<=a[1]
            uc.mem_write(a[0],value+b'\0')
        elif pc==0x183618:
            assert a[:2]==[77,55]
            packet=bytes(uc.mem_read(a[2],a[3]));words=list(struct.unpack('<'+str(min(a[3]//4,8))+'I',packet[:min(a[3],32)]))
            if not requests:
                assert a[3]==276 and words[:5]==[276,55,2,36,66]
                assert packet[20:].split(b'\0',1)[0]==b'SpiderApp'
            else:assert a[3]==1060 and words==[1060,56,2,6,66,1,1,0]
            requests.append({'words':words,'packet_sha256':hashlib.sha256(packet).hexdigest(),'packet_hex':packet.hex(),
                             'lookup_name':'SpiderApp' if words[3]==36 else None})
        elif pc==0x1836c4:
            op=requests[-1]['words'][3]
            response=[20,55,36,query_error,1] if op==36 else [16,56,6,switch_error]
            if op==36 and not query_error and lookup_input:response=lookup_input['reply']
            assert a[0]==77 and a[2]==len(response)*4
            uc.mem_write(a[1],struct.pack('<'+str(len(response))+'I',*response));put(a[3],len(response)*4);replies.append(response)
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    u.reg_write(UC_ARM_REG_SP,0x200f000);u.reg_write(UC_ARM_REG_LR,end)
    u.emu_start(0xff94,end,count=10000)
    assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==7
    assert [r['words'][3] for r in requests]==([36] if query_error else [36,6])
    rows.append({'case':name,'requests':requests,'supplied_replies':replies,'callback_return':7})
report={'responder_sha256':digest,'entry':'0xff94','cases':rows,'all_passed':True,'physical_device_access':False,
        'limits':['fcd4 branch selection returns1 as fixture; IPC, mutexes, logs and libc string/memory helpers virtual.',
                  'Originalff94/1209c/180e4c/182b64 execute, including real getter and request construction.',
                  'AppID1 is supplied by lookup reply; actual AppList lookup and management switching not executed.',
                  'Callback return7 is state progression, not proof of successful playback restoration.']}
if lookup_input:report['lookup_reply_input']=lookup_input
(ROOT/('sources/native-responder-walkman-lookup-reply.json' if lookup_input else 'sources/native-responder-walkman-request.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
