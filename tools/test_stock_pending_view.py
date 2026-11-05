"""Actual ARM read-only pending inspector and digest guard; native data fixtures."""
import hashlib,io,json,struct,subprocess,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR
from app_registry import ROOT
out=ROOT/'work/stock-pending-view'/str(time.time_ns());out.mkdir(parents=True);binary=out/'view.arm'
sources=['runtime/platform/player/stock_pending.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','tools/fixtures/player_pending_view.c']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
stock=ROOT/'work/targets-jp/SpiderApp';raw=stock.read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()};cases=[]
for case,expected in [('valid',0),('missing',-2),('duplicate',-8),('overflow',-8),('wrong-command',-2),('wrong-table',-3),('changed-code',-3)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for image in (ELFFile(io.BytesIO(raw)),helper):
  for s in image.iter_segments():
   if s['p_type']!='PT_LOAD':continue
   a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 put(0x613e64,3);put(0x613e8c,0x66efe8);put(0x66efe8,1);put(0x66efec,0x123)
 if case=='missing':put(0x66efec,0x456)
 if case=='duplicate':put(0x66efe8,2);put(0x66eff0,0x123)
 if case=='overflow':put(0x66efe8,33)
 if case=='wrong-command':put(0x613e64,6)
 if case=='wrong-table':put(0x613e8c,0x66efec)
 if case=='changed-code':put(0x489dc,0)
 def call(name,args):
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,value)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(symbols[name],done,count=1000000);return u.reg_read(UC_ARM_REG_R0)
 put(area+0xf000,0x123) # uint64 argument aligns in r2/r3; token is on stack.
 result=call('xw_stock_pending_bind',[symbols['pending'],0,1,0]);assert result==expected&0xffffffff,(case,result)
 if case=='valid':
  assert call('xw_stock_pending_check',[symbols['pending'],0,1,0])==0
  assert call('xw_stock_pending_check',[symbols['pending'],0,2,0])==0xfffffffb
  put(symbols['test_thread'],8);assert call('xw_stock_pending_check',[symbols['pending'],0,1,0])==0xfffffffc
 cases.append(dict(case=case,result=expected))
report=dict(passed=True,actual_arm_inspector_and_digest=True,native_state_and_dladdr_thread_identity_modeled=True,read_only=True,device_accessed=False,cases=cases,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/stock_pending.h','tools/test_stock_pending_view.py']})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
