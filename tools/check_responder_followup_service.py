"""Replay captured Responder op19 through stock service/core; stopping effects virtual."""
from pathlib import Path
import hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1]
capture_path='sources/native-responder-usb-cycle.json'
capture_raw=(ROOT/capture_path).read_bytes();capture=json.loads(capture_raw)
assert capture['all_passed'] and capture['responder_sha256']=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
packet=capture['cases'][0]['cycle_restore_requests'][-1]
assert packet==[24,58,2,19,66,2]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
    binary=tar.extractfile('./usr/local/bin/sysmgrd').read()
digest=hashlib.sha256(binary).hexdigest()
assert digest=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
rows=[]
for name,initial,argument,count,expected in [('captured',1,2,0,0),('pending-records',1,2,1,0),
                                         ('invalid-argument',1,3,0,0x102),('disallowed-state',3,2,0,0x1d03)]:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
    for segment in ELFFile(io.BytesIO(binary)).iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    u.mem_map(0x100000,0x10000)
    core,ipc,request,end=0x100000,0x106000,0x106100,0x106200
    put=lambda p,v:u.mem_write(p,struct.pack('<I',v))
    word=lambda p:struct.unpack('<I',u.mem_read(p,4))[0]
    put(core+0x503c,initial);put(core+0x51a8,0xaaaaaaaa)
    put(core+0x51ac,0xaaaaaaaa);put(core+0x51b0,0xaaaaaaaa)
    u.mem_write(ipc,struct.pack('<II',core,44))
    words=packet.copy();words[-1]=argument;u.mem_write(request,struct.pack('<6I',*words))
    trace=[];replies=[]
    def hook(uc,pc,size,unused):
        result=0
        if pc==end:uc.emu_stop();return
        if pc not in (0xa188,0x1c4d0,0x1c5ac,0x16594,0x14720,0xae68,0x16d18):return
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        if pc==0x16594:result=count;trace.append('virtual-list-count:'+str(count))
        elif pc==0x14720:trace.append('virtual-changer-operation:14720')
        elif pc==0xae68:
            assert a[:2]==[core,0];trace.append('virtual-stop-enumeration:ae68')
        elif pc==0x16d18:
            assert a[:2]==[44,66];replies.append(list(struct.unpack('<4I',uc.mem_read(a[2],16))))
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    for reg,value in ((UC_ARM_REG_R0,ipc),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x10f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
    u.emu_start(0x1001c,end,count=3000)
    assert u.reg_read(UC_ARM_REG_PC)==end and replies==[[16,58,19,expected]]
    if expected==0:
        assert word(core+0x503c)==6 and word(core+0x51a8)==2
        assert word(core+0x51ac)==word(core+0x51b0)==0
        assert word(core+0x4214+0x95c)==1
        assert trace==['virtual-list-count:'+str(count),'virtual-changer-operation:14720','virtual-stop-enumeration:ae68']
    else:
        assert word(core+0x503c)==initial and not trace
    rows.append({'case':name,'initial_core_state':initial,'request':words,'supplied_list_count':count,
                 'trace':trace,'replies':replies,'final_core_state':word(core+0x503c),
                 'stored_request_mode':word(core+0x51a8)})
report={'sysmgrd_sha256':digest,'client_capture':{'path':capture_path,'sha256':hashlib.sha256(capture_raw).hexdigest()},
        'entry':'0x1001c','native_core_function':'0xd860','cases':rows,'all_passed':True,'physical_device_access':False,
        'limits':['Core state and list count are fixtures; actual service/d860/14030/13c44 execute.',
                  'Changer operation14720, stop enumerationae68, logging and IPC reply transport are virtual.',
                  'State6 and mode2 are observed values, not a proven return-to-Walkman or power-state semantic.',
                  'No application is stopped, no filesystem/device is accessed and no final suspend/reboot path executes.']}
(ROOT/'sources/native-responder-followup-service.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
