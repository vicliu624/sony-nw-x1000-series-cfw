"""Execute the original raw-UCS2 text setup; graphics factory/setter are fixtures."""
from pathlib import Path
import io,json,hashlib,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];area=ROOT/'work/home-feedback-build-review-1'
b=(area/'SpiderApp.feedback.analysis-only.elf').read_bytes();build=json.loads((area/'build.json').read_text());assert hashlib.sha256(b).hexdigest()==build['candidate_sha256']
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x780000)
for s in ELFFile(io.BytesIO(b)).iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x50000000,0x10000);sp=0x50008000;parent=0x50001000;text_widget=0x50003000;captured=[]
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def hook(uc,pc,size,_):
 if pc not in (0xf56b4,0xf577c,0xf3694,0xf3af8,0xee9e4):return
 if pc==0xf577c:
  assert uc.reg_read(UC_ARM_REG_R1)==parent and uc.reg_read(UC_ARM_REG_R3)==59
  uc.mem_write(word(uc.reg_read(UC_ARM_REG_SP)+4),struct.pack('<I',text_widget))
 if pc==0xf3694:
  assert uc.reg_read(UC_ARM_REG_R0)==text_widget
  pointer=uc.reg_read(UC_ARM_REG_R1);raw=bytearray()
  for n in range(100):
   x=bytes(uc.mem_read(pointer+2*n,2))
   if x==b'\0\0':break
   raw.extend(x)
  else:raise AssertionError('Text not terminated')
  captured.append(raw.decode('utf-16le'))
 uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,parent);u.reg_write(UC_ARM_REG_R1,build['symbols']['hb_error_descriptor']);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50009000)
u.emu_start(0x10a6d8,0x50009000,count=500)
assert captured==['Homebrew unavailable.\nCheck HOMEBREW folder.'] and word(parent+0xafc)==text_widget
assert u.reg_read(UC_ARM_REG_PC)==0x50009000 and u.reg_read(UC_ARM_REG_SP)==sp
report={'passed':True,'stock_text_setup_executed':True,'raw_text_reached_setter':captured,'stack_restored':True,'graphics_boundaries_mocked':['0xf56b4','0xf577c','0xf3694','0xf3af8','0xee9e4'],'screen_render_verified':False,'candidate_sha256':build['candidate_sha256'],'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(area/'text-setup-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
