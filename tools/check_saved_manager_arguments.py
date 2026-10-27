"""Original argv client/service using preserved launch-model registry, not rebuilt record."""
from pathlib import Path
import argparse,contextlib,hashlib,io,json,runpy,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from evidence_checks import verify_report
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--return-report',default='sources/native-home-activation-manager-return.json')
    parser.add_argument('--report',default='sources/native-saved-manager-arguments.json')
    options=parser.parse_args()
    return_report=options.return_report;output_report=options.report
else:
    return_report=globals().get('return_report','sources/native-home-activation-manager-return.json')
    output_report=globals().get('output_report','sources/native-saved-manager-arguments.json')
source=(ROOT/return_report).resolve();assert source.is_relative_to(ROOT/'sources')
output=(ROOT/output_report).resolve();assert output.is_relative_to(ROOT/'sources') and output.suffix=='.json'
launch=verify_report(ROOT,str(source.relative_to(ROOT)))
state=launch['returned_manager_state'];ram_path=ROOT/state['path'];ram=ram_path.read_bytes()
assert len(ram)==state['bytes']==0x20000 and hashlib.sha256(ram).hexdigest()==state['sha256']
assert state['base']=='0x60000000' and state['home_record']=='0x60010000'
assert state['current_app']==1 and state['home_record_state']==2
binary=ROOT/'work/targets-jp/sysmgrd';raw=binary.read_bytes()
assert hashlib.sha256(raw).hexdigest()==launch['sysmgrd_sha256']=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
manager=Uc(UC_ARCH_ARM,UC_MODE_ARM);manager.mem_map(0x8000,0x40000)
elf=ELFFile(io.BytesIO(raw))
for s in elf.iter_segments():
    if s['p_type']=='PT_LOAD':manager.mem_write(s['p_vaddr'],s.data())
manager.mem_map(0x60000000,0x20000);manager.mem_write(0x60000000,ram);manager.mem_map(0x50000000,4096)
region_paths=[]
expected=[(s['p_vaddr'],s['p_memsz']) for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_flags']&2]
assert [(int(r['address'],0),r['bytes']) for r in state['module_regions']]==expected
for region in state['module_regions']:
    p=ROOT/region['path'];data=p.read_bytes();assert len(data)==region['bytes'] and hashlib.sha256(data).hexdigest()==region['sha256']
    manager.mem_write(int(region['address'],0),data);region_paths.append(p)
base=ROOT/'tools/check_spider_restore_dispatch.py'
with contextlib.redirect_stdout(io.StringIO()):model=runpy.run_path(str(base))
client=model['u'];call=model['call'];g=call.__globals__;g['intercept_actions']=False;g['deactivate_probe']=False
service,request=0x6001a000,0x6001a100
manager.mem_write(service,struct.pack('<2I',0x60000000,44));responses=[];requests=[]
before=bytes(manager.mem_read(0x60010000,256))
assert struct.unpack_from('<I',before,12)[0]==2
def manager_hook(uc,pc,size,data):
    if pc==0x16d18:
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        assert a[:2]==[44,55] and a[3]==1044;responses.append(bytes(uc.mem_read(a[2],1044)))
    elif pc not in (0x1a4f0,0x1a508):return
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
manager_hook_id=manager.hook_add(UC_HOOK_CODE,manager_hook)
def client_hook(uc,pc,size,data):
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];value=0
    if pc==0xd85c:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));value=a[0]
    elif pc==0x268c9c:
        packet=bytes(uc.mem_read(a[2],a[3]));assert list(struct.unpack('<5I',packet))==[20,4,1,35,55];requests.append(packet)
        manager.mem_write(request,packet)
        for r,v in ((UC_ARM_REG_R0,service),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,0x50000000)):manager.reg_write(r,v)
        manager.emu_start(0x10750,0x50000000,count=30000);assert manager.reg_read(UC_ARM_REG_PC)==0x50000000
    elif pc==0x268d48:
        assert a[2]==1044 and len(responses)==1;uc.mem_write(a[1],responses[0]);uc.mem_write(a[3],struct.pack('<I',1044))
    elif pc not in (0x337a80,0x337ae8):return
    uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
client.hook_add(UC_HOOK_CODE,client_hook)
ctx,out=0x60012000,0x60013000;data=bytearray(44)
for offset,value in ((0,1),(4,1),(12,55),(16,500),(20,4),(40,88)):struct.pack_into('<I',data,offset,value)
client.mem_write(ctx,bytes(data));assert call(0x2665dc,(ctx,out,0,0))==0
assert list(struct.unpack('<5I',responses[0][:20]))==[1044,4,35,0,0]
assert list(struct.unpack('<2I',client.mem_read(out,8)))==[0,0]
assert bytes(manager.mem_read(0x60010000,256))==before
paths=[Path(__file__),source,ram_path,*region_paths,base,binary,ROOT/'work/targets-jp/SpiderApp']
report={'all_bounded_checks_passed':True,'saved_state_path':state['path'],'source_phase':'after_native_walkman_confirmation',
        'home_record_imported_not_rebuilt':True,'home_record_prefix_unchanged':True,
        'home_record_words':list(struct.unpack('<6I',before[:24])),
        'request_words':list(struct.unpack('<5I',requests[0])),
        'reply_header':list(struct.unpack('<5I',responses[0][:20])),
        'client_argc':0,'client_first_argv':0,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'limits':['Imports modeled launch memory and writable module regions, not a device dump.',
                  'Original argv query/client/registry search execute; locks/libc/transport virtual.',
                  'Initial Home record itself originates in upstream launch fixture; no full boot/registration proof.',
                  'Separate emulators, no device execution or storage writes; not integrated into Home instance.']}
output.write_text(json.dumps(report,indent=2)+'\n')
print('Preserved manager after native Walkman return ->original argv service/client ->argc0; no record reconstruction')
