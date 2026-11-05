"""Execute native confirmation bridge ARM instructions; no firmware/device."""
import hashlib,io,json,struct,subprocess,time
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
out=ROOT/'work/native-wireless-callback'/str(time.time_ns());out.mkdir(parents=True)
source='runtime/platform/wireless/native_callback.c'
ld=out/'callback.ld'
ld.write_text('''ENTRY(xw_wireless_native_confirm)
SECTIONS { . = 0x4d8500; .text : { *(.text*) *(.rodata*) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
xw_native_mode_request = 0xda84;
xw_native_stock_confirm = 0x88494;
xw_native_selected_row = 0x4ee5d8;
''')
image=out/'callback.elf'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffreestanding','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(ld),source,'-o',str(image)],cwd=ROOT,check=True)
elf=ELFFile(io.BytesIO(image.read_bytes()));u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for segment in elf.iter_segments():
 if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
u.mem_map(0x50000000,4096);u.mem_map(0x60000000,65536)
requests=[];delegated=[];native_rows=[];response=0;stock_result=0x1234
def hook(uc,pc,size,unused):
 if pc==0xda84:
  requests.append([uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1),uc.reg_read(UC_ARM_REG_LR)])
  answer=response
 elif pc==0x88494:
  native_rows.append(struct.unpack('<I',uc.mem_read(0x4ee5d8,4))[0])
  delegated.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]);answer=stock_result
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
cases=0;callers=set()
for row in (0,1,2,3,0xffffffff):
 for event in (0xff0000,0xff0001,0x123456):
  for response in (4321,0x574d0000,0x574d0001,0x574dfffb,0x574dfffc,0x574dfffd):
   requests.clear();delegated.clear();native_rows.clear();u.mem_write(0x4ee5d8,struct.pack('<I',row))
   for reg,value in ((UC_ARM_REG_R0,0x1111),(UC_ARM_REG_R1,0x2222),(UC_ARM_REG_R2,event),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
   u.emu_start(elf['e_entry'],0x50000000,count=1000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
   if event==0x123456:
    assert not requests and delegated==[[0x1111,0x2222,event]];expected=0x1234
   elif row>2:
    assert not requests and not delegated;expected=0x5a01 if event==0xff0001 else 0x9a01
   else:
    assert len(requests)==1 and requests[0][:2]==[2 if event==0xff0000 else 4,row]
    applied=event==0xff0000 and response==0x574d0000
    assert delegated==([[0x1111,0x2222,event]] if applied else [])
    assert native_rows==([0 if row==0 else 1] if applied else [])
    callers.add(requests[0][2]);expected=0x1234 if applied else 0x5a01 if event==0xff0001 else 0x9a01
    if event==0xff0000 and response==0x574d0001:expected=0x9a02
   assert u.reg_read(UC_ARM_REG_R0)==expected
   assert struct.unpack('<I',u.mem_read(0x4ee5d8,4))[0]==row
   cases+=1
assert len(callers)==1
for stock_result in (0x5a01,4,0x1234):
 requests.clear();delegated.clear();native_rows.clear();response=0x574d0000
 u.mem_write(0x4ee5d8,struct.pack('<I',2))
 for reg,value in ((UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,0xff0000),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
 u.emu_start(elf['e_entry'],0x50000000,count=1000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 assert u.reg_read(UC_ARM_REG_R0)==(0x9a01 if stock_result==0x5a01 else stock_result)
 assert native_rows==[1] and struct.unpack('<I',u.mem_read(0x4ee5d8,4))[0]==2
 cases+=1
report=dict(passed=True,device_accessed=False,firmware_created=False,arm_cases=cases,
 request_caller=hex(next(iter(callers))),callback_bytes=len(elf.get_section_by_name('.text').data()),
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (source,'tools/test_native_wireless_callback.py')},
 limits=['Request target and unexpected-event delegation are modeled; host dispatcher is not installed.',
 '0x9a01 stays on native page0x9a by transition encoding; actual rendering/progress UI is not qualified.',
 'No original ELF patch, authority registration, persistence, radio or hardware operation.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
