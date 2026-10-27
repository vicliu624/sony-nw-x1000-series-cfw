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
u.mem_map(0x50000000,0x10000);sp=0x50008000;parent=0x50001000;text_widget=0x50003000;captured=[];heights=[]
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def hook(uc,pc,size,_):
 if pc not in (0xf56b4,0xf577c,0xf3694,0xf3af8,0xee9e4,0x10a448,0x10a938,0x10a9a4,0x10a24c):return
 if pc==0x10a448:
  assert uc.reg_read(UC_ARM_REG_R0)==parent;heights.append(uc.reg_read(UC_ARM_REG_R1))
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
u.mem_write(parent+0xaf4,struct.pack('<I',1)) # explicit initial-line fixture
u.emu_start(0x10ac20,0x50009000,count=3000)
assert captured==['Homebrew unavailable.\nCheck HOMEBREW folder.'] and word(parent+0xafc)==text_widget
assert u.reg_read(UC_ARM_REG_PC)==0x50009000 and u.reg_read(UC_ARM_REG_SP)==sp
assert word(parent+0xaf4)==2 and heights==[80]
assert word(parent+0xae8)==1 and word(parent+0x4a0)==0x10a3ec
report={'passed':True,'main_layout_executed':True,'initial_line_count_fixture':1,'computed_line_count':2,'computed_height':heights[0],'stock_text_setup_executed':True,'raw_text_reached_setter':captured,'stack_restored':True,'graphics_boundaries_mocked':['0xf56b4','0xf577c','0xf3694','0xf3af8','0xee9e4','0x10a448','0x10a938','0x10a9a4','0x10a24c'],'screen_render_verified':False,'candidate_sha256':build['candidate_sha256'],'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(area/'main-layout-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
