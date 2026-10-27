"""Feed captured SpiderApp query into original manager/name lookup, offline only."""
from pathlib import Path
import hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1]
client_raw=(ROOT/'sources/native-responder-walkman-request.json').read_bytes();client=json.loads(client_raw)
assert client['all_passed'] and client['responder_sha256']=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
query=client['cases'][0]['requests'][0];packet=bytes.fromhex(query['packet_hex'])
assert hashlib.sha256(packet).hexdigest()==query['packet_sha256'] and len(packet)==276
parser_raw=(ROOT/'sources/native-applist-full-config.json').read_bytes();parsed=json.loads(parser_raw)
assert parsed['sysmgrd_sha256']=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
records=next(r['records'] for r in parsed['cases'] if r['case']=='full-merged')
assert next(r['id'] for r in records if r['name']=='SpiderApp')=='0x1'
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:binary=tar.extractfile('./usr/local/bin/sysmgrd').read()
assert hashlib.sha256(binary).hexdigest()==parsed['sysmgrd_sha256']
rows=[]
for name,core_state,lookup_name,expected in [('captured',1,'SpiderApp',0),('missing-name',1,'MissingApp',0x111),('disallowed-state',4,'SpiderApp',0x1d03)]:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
    for segment in ELFFile(io.BytesIO(binary)).iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    u.mem_map(0x100000,0x20000)
    core,table,ipc,request,end=0x100000,0x108000,0x106000,0x106100,0x106300
    put=lambda p,v:u.mem_write(p,struct.pack('<I',v))
    put(core,len(records));put(core+4,table);put(core+0x503c,core_state)
    for index,record in enumerate(records):
        address=table+index*0x510;put(address,int(record['id'],0));u.mem_write(address+4,record['name'].encode()+b'\0')
    u.mem_write(ipc,struct.pack('<II',core,44));u.mem_write(request,packet)
    if lookup_name!='SpiderApp':u.mem_write(request+20,lookup_name.encode()+b'\0')
    replies=[];comparisons=[]
    def string(p):return bytes(u.mem_read(p,256)).split(b'\0',1)[0].decode()
    def hook(uc,pc,size,unused):
        if pc==end:uc.emu_stop();return
        if pc not in (0x9abc,0xa188,0x1c5ac,0x16d18):return
        result=0;a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        if pc==0x9abc:
            left,right=string(a[0]),string(a[1]);comparisons.append([left,right]);result=0 if left==right else 1
        elif pc==0x16d18:
            assert a[:2]==[44,66];replies.append(list(struct.unpack('<5I',uc.mem_read(a[2],20))))
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    for reg,value in ((UC_ARM_REG_R0,ipc),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x11f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
    u.emu_start(0x1084c,end,count=5000)
    assert u.reg_read(UC_ARM_REG_PC)==end and len(replies)==1 and replies[0][:4]==[20,55,36,expected]
    if not expected:assert replies[0][4]==1
    rows.append({'case':name,'initial_core_state':core_state,'name':lookup_name,'comparisons':comparisons,'reply':replies[0]})
report={'sysmgrd_sha256':parsed['sysmgrd_sha256'],'client_capture_sha256':hashlib.sha256(client_raw).hexdigest(),
        'parser_report_sha256':hashlib.sha256(parser_raw).hexdigest(),'entry':'0x1084c','cases':rows,'all_passed':True,'physical_device_access':False,
        'limits':['Record IDs/names seeded from original-parser report; full parser is not executed in this instance.',
                  'Original1084c/ca24/117d8/15ad0 execute; strcmp/logging/IPC virtual.',
                  'Only successful reply ID is meaningful; missing/rejected replies may contain unspecified trailing data.',
                  'No application switch, real IPC, playback or physical-device execution.']}
(ROOT/'sources/native-walkman-lookup-service.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
