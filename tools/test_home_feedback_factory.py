"""Run stock message factory routing with explicit graphics/layout boundaries."""
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
u.mem_map(0x50000000,0x20000);sp=0x50018000;control=0x50001000;window=0x50003000;content=0x50006000;descriptor=build['symbols']['hb_error_descriptor'];calls=[];boundaries=(0xe87f4,0xe9300,0x1090b4,0xedea8,0xf56b4,0xf577c,0x1334f8,0x10ac20)
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def hook(uc,pc,size,_):
 if pc not in boundaries:return
 calls.append(pc);result=0
 if pc==0xe9300:result=window
 elif pc==0xf577c:
  assert uc.reg_read(UC_ARM_REG_R3)==57 and uc.reg_read(UC_ARM_REG_R1)==window
  uc.mem_write(word(uc.reg_read(UC_ARM_REG_SP)+4),struct.pack('<I',content))
 elif pc==0x10ac20:
  assert uc.reg_read(UC_ARM_REG_R0)==content and uc.reg_read(UC_ARM_REG_R1)==descriptor
 uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);before=bytes(u.mem_read(descriptor,48));u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000);u.reg_write(UC_ARM_REG_R0,control);u.reg_write(UC_ARM_REG_R1,descriptor)
u.emu_start(0xc6880,0x50019000,count=3000)
assert u.reg_read(UC_ARM_REG_PC)==0x50019000 and u.reg_read(UC_ARM_REG_SP)==sp
assert word(control+24)==745 and word(control+32)==descriptor and word(control+36)==window and word(control+40)==content
assert word(window+0xae8)==control and word(window+0x464)==30 and word(window+0x468)==30
assert calls==list(boundaries) and bytes(u.mem_read(descriptor,48))==before
report={'passed':True,'stock_message_factory_and_normal_creation_branch_executed':True,'message_id':745,'descriptor_retained_unchanged':True,'ordinary_window_fields_verified':True,'graphics_and_layout_boundaries_mocked':[hex(x) for x in boundaries],'main_layout_executed':False,'screen_render_verified':False,'candidate_sha256':build['candidate_sha256'],'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(area/'factory-routing-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
