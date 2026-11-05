"""Original RF wrappers through source anchors/receiver; no RF/device/UPG."""
import contextlib,hashlib,io,json,runpy,struct,subprocess,time
from app_registry import ROOT
from native_rf_bridge import compose
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
out=ROOT/'work/native-rf-bridge'/str(time.time_ns());out.mkdir(parents=True)
with contextlib.redirect_stdout(io.StringIO()):base=runpy.run_path(str(ROOT/'tools/test_builtin_player_composition.py'))
candidate,composition=compose(base['artifact'].read_bytes(),out/'anchor')
fixture=out/'fixture.c';fixture.write_text('''
unsigned allowed=1,image_valid=1;int error=77;
int *__errno_location(void){return &error;}
int xw_native_rf_image_valid(void){return image_valid;}
int xw_native_rf_permission(void){error=91;return allowed?0:-1;}
''')
receiver=out/'receiver.elf'
source='runtime/platform/wireless/native_rf_dispatch.c'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-fno-builtin','-fno-pie','-fno-stack-protector','-ffreestanding','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x51000000,-e,xw_native_rf_dispatch',source,str(fixture),'-o',str(receiver)],cwd=ROOT,check=True)
symbol={s.name:s['st_value'] for s in ELFFile(io.BytesIO(receiver.read_bytes())).get_section_by_name('.symtab').iter_symbols()}
cases=[]
for entry in (0xb3458,0xb3784,0xb3538,0xb3ee4,0xb3f70,0xb3ffc):
 for allowed in (0,1):
  for image_valid in (0,1):
   for result in (0,16):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x50ff0000,0x40000)
    for raw in (candidate,receiver.read_bytes()):
     for s in ELFFile(io.BytesIO(raw)).iter_segments():
      if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
    u.mem_map(0x50000000,4096);u.mem_map(0x60000000,65536)
    def put(a,n):u.mem_write(a,struct.pack('<I',n))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    put(symbol['allowed'],allowed);put(symbol['image_valid'],image_valid);put(symbol['error'],77)
    targets=[int(x,16) for x in composition['original_targets']];requests=[];original=[];shim_return=[]
    def hook(uc,pc,size,unused):
     if pc==0x50000100:
      uc.reg_write(UC_ARM_REG_SP,uc.reg_read(UC_ARM_REG_SP)+8)
      uc.reg_write(UC_ARM_REG_PC,shim_return.pop());return
     args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
     if pc==0xda84:
      operation=args[0];caller=uc.reg_read(UC_ARM_REG_LR);requests.append(operation)
      assert caller==int(composition['request_callers'][operation-1],16)
      uc.reg_write(UC_ARM_REG_R0,operation);uc.reg_write(UC_ARM_REG_R1,args[1]);uc.reg_write(UC_ARM_REG_R2,args[2]);uc.reg_write(UC_ARM_REG_R3,uc.reg_read(UC_ARM_REG_R7))
      shim_return.append(caller);uc.reg_write(UC_ARM_REG_SP,uc.reg_read(UC_ARM_REG_SP)-8)
      put(uc.reg_read(UC_ARM_REG_SP),caller);uc.reg_write(UC_ARM_REG_LR,0x50000100)
      uc.reg_write(UC_ARM_REG_PC,symbol['xw_native_rf_dispatch']);return
     if pc in targets:
      assert allowed and image_valid;original.append(dict(target=hex(pc),arguments=args));answer=result
     elif pc==0xb3248:answer=7
     elif pc in (0x33b918,0x33b83c):answer=0
     else:return
     uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    for reg,n in ((UC_ARM_REG_R0,0x12345678),(UC_ARM_REG_R1,0x23456789),(UC_ARM_REG_R2,0x3456789a),(UC_ARM_REG_R7,0x55667788),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,n)
    u.emu_start(entry,0x50000000,count=30000)
    assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R7)==0x55667788
    assert word(symbol['error'])==77
    expected_ops={0xb3458:[1],0xb3784:[2],0xb3538:[3,4],0xb3ee4:[5,6],0xb3f70:[5,7],0xb3ffc:[5,8]}[entry]
    assert requests==expected_ops and len(original)==(len(requests) if allowed and image_valid else 0)
    assert u.reg_read(UC_ARM_REG_R0)==(result if allowed and image_valid else 1)
    if original and entry in (0xb3538,0xb3ee4,0xb3f70,0xb3ffc):
     count=1 if entry in (0xb3538,0xb3ffc) else 3
     assert original[-1]['arguments'][:count]==[0x12345678,0x23456789,0x3456789a][:count]
    cases.append(dict(entry=hex(entry),allowed=allowed,image_valid=image_valid,result=result))
artifact=out/'SpiderApp.rf-gate.analysis-only.elf';artifact.write_bytes(candidate)
report=dict(passed=True,device_accessed=False,firmware_created=False,ready_to_flash=False,arm_cases=len(cases),cases=cases,composition=composition,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (source,'tools/test_native_rf_bridge.py')},
 limits=['Request shim transfer, image qualification, permission and imported RF/loggers are fixture boundaries.',
 'Original wrappers, source ARM anchors and source C receiver execute together; no actual RF operation.',
 'The receiver is not installed in the production SDK dispatcher; worker provisioning remains unfinished.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,arm_cases=len(cases),report=(out/'report.json').relative_to(ROOT).as_posix()),indent=2))
