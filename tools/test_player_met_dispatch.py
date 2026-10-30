"""ARM stub -> argument-preserving PID shim -> guarded Met dispatch."""
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R7
from build_player_host import ROOT,CORE_SOURCES,patch_owner_anchor
from build_player_met_anchor import build
stock,report=build();stock,_=patch_owner_anchor(stock);report['tested_composite_sha256']=hashlib.sha256(stock).hexdigest();w=ROOT/'work/player-met-anchor';app=w/'dispatch.arm';fixture='tools/fixtures/player_host_anchor.c'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*CORE_SOURCES,fixture,'-lgcc','-o',str(app)],cwd=ROOT,check=True)
helper=app.read_bytes();symbols={s.name:s['st_value'] for s in ELFFile(io.BytesIO(helper)).get_section_by_name('.symtab').iter_symbols()};cases=[]
for scenario in ('valid','second-met-thread','changed-stub','changed-call','wrong-image','ordinary'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for binary in (stock,helper):
  for seg in ELFFile(io.BytesIO(binary)).iter_segments():
   if seg['p_type']!='PT_LOAD':continue
   a=int(seg['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(seg['p_memsz'])+4095)&~4095);u.mem_write(a,seg.data())
 area=0x71000000;u.mem_map(area,65536);session=area;player=area+0x1000;cancel=0x12345678;stops=[area+0xff00]
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(session+0x20,player)
 def hook(uc,pc,size,ctx):
  if pc in stops:uc.emu_stop();return
  if pc==0xda84:uc.reg_write(UC_ARM_REG_PC,symbols['getpid']);return
  if pc==0x27b404:
   assert uc.reg_read(UC_ARM_REG_R0)==player and uc.reg_read(UC_ARM_REG_R1)==cancel
   uc.reg_write(UC_ARM_REG_R0,0x106);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,done):
  stops[:]=[done];u.reg_write(UC_ARM_REG_R0,session);u.reg_write(UC_ARM_REG_R1,cancel);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(address,done+4,count=30000000);assert u.reg_read(UC_ARM_REG_PC)==done;return u.reg_read(UC_ARM_REG_R0)
 call(symbols['host_initialize'],area+0xff00)
 if scenario=='changed-stub':put(0x4d6004,0)
 if scenario=='changed-call':put(0x27c610,0)
 if scenario=='wrong-image':put(symbols['xw_test_loaded'],0)
 if scenario in ('valid','second-met-thread'):
  original=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
  def guard(address,length):
   digest=hashlib.sha256(original[address-0x8000:address-0x8000+length]).digest();u.mem_write(area+0x2000,digest)
   done=area+0xff00;stops[:]=[done];u.reg_write(UC_ARM_REG_R0,address);u.reg_write(UC_ARM_REG_R1,length)
   from unicorn.arm_const import UC_ARM_REG_R2
   u.reg_write(UC_ARM_REG_R2,area+0x2000);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
   u.emu_start(symbols['xw_stock_image_match'],done+4,count=1000000);assert u.reg_read(UC_ARM_REG_PC)==done;return u.reg_read(UC_ARM_REG_R0)
  for address,length in ((0x27c300,0x2000),(0x27b400,0x2200)):
   assert guard(address,length)==0
   prior=get(address);put(address,prior^1);assert guard(address,length)==0xfffffffd;put(address,prior)
   prior=get(0x4d6004);put(0x4d6004,prior^1);assert guard(address,length)==0xfffffffd;put(0x4d6004,prior)
  put(0x612c48,0);assert call(0xff3c,0xff40)==0 and get(symbols['test_initialized'])==1
  u.reg_write(UC_ARM_REG_R7,0x12340000)
  assert call(0x27c610,0x27c614)==0x106
  assert get(symbols['test_met_calls'])==1 and get(symbols['test_met_session'])==session and get(symbols['test_met_cancel'])==cancel
  assert get(symbols['test_errno'])==1234 and get(symbols['test_met_list'])==0x12340000
  if scenario=='second-met-thread':put(symbols['xw_test_thread'],18);assert call(0x27c610,0x27c614)==0x106 and get(symbols['test_met_calls'])==2
 else:
  done=area+0xff00 if scenario=='ordinary' else 0x4d600c
  assert call(symbols['getpid'],done)==4321 and get(symbols['test_met_calls'])==0 and get(symbols['test_errno'])==1234
 cases.append(dict(case=scenario,dispatches=get(symbols['test_met_calls']),pid_calls=get(symbols['test_pid_calls'])))
report.update(passed=True,explicit_alternative_profile=True,extra_code_and_stub_mutations_rejected=True,composed_gui_provider_binding=True,cases=cases,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in CORE_SOURCES+[fixture,'runtime/platform/player/host_hook.h','tools/test_player_met_dispatch.py']},limits=['Real ARM stub, bridge, checksum gates and session wrapper execute; dladdr, thread identity, real PID target and player maintenance are modeled.','The isolated fixture supplies a diagnostic callback instead of the production queue adapter; no full loader boot or device qualification.'])
(w/'dispatch-test.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


