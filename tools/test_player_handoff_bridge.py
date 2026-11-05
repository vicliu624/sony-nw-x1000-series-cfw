"""Production C command6 wait/view -> original coordinator, offline ARM only."""
import contextlib,hashlib,io,json,runpy,struct,subprocess,time
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
out=ROOT/'work/player-handoff-bridge'/str(time.time_ns());out.mkdir(parents=True)
with contextlib.redirect_stdout(io.StringIO()):base=runpy.run_path(str(ROOT/'tools/test_player_prepare_composition.py'))['artifact'].read_bytes()
sources=['runtime/platform/player/'+name for name in ('host_handoff_bridge.c','stock_prepare_view.c','stock_image.c')]+['runtime/native/sha256.c','tools/fixtures/player_handoff_bridge.c']
binary=out/'handoff.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
callbacks=(0x16b74,0x143c0,0xf32c,0x3b498,0x37f08,0x49d6c,0x4492c,0x499f8,0x4f3dc);rows=[]
for case in ('ready','radio-wait','sdk-wait','root-changed','code-changed','radio-failed','sdk-failed','wrong-owner','duplicate','resume-ok','resume-pending','resume-failed','resume-ack-error','resume-no-entry','resume-stale-sequence','resume-foreign','resume-wrong-client','resume-code'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 segments=[seg for elf in (ELFFile(io.BytesIO(base)),helper) for seg in elf.iter_segments() if seg['p_type']=='PT_LOAD']
 merged=[]
 for start,end in sorted((int(seg['p_vaddr'])&~4095,(int(seg['p_vaddr'])+int(seg['p_memsz'])+4095)&~4095) for seg in segments):
  if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
  else:merged.append((start,end))
 for start,end in merged:u.mem_map(start,end-start)
 u.mem_map(0x71000000,65536)
 for seg in segments:u.mem_write(seg['p_vaddr'],seg.data())
 done=0x7100ff00
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 for a,v in ((0x613e64,1),(0x613e68,0),(0x613eac,1),(0x613e8c,0x66efe8),(0x66efe8,0)):put(a,v)
 entered=[];components=[];completed=[]
 def hook(cpu,pc,size,unused):
  if pc==0x112fc:entered.append([cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]);return
  if pc in callbacks:
   assert cpu.reg_read(UC_ARM_REG_R1)==6;components.append(pc);put(cpu.reg_read(UC_ARM_REG_R2),0)
  elif pc==0x1fd30:put(cpu.reg_read(UC_ARM_REG_R2),0)
  elif pc==0x10ee4:completed.append(pc)
  elif pc not in (0xff5c,0x33b83c,0x33b918):return
  cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(name,*args):
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1),args):u.reg_write(reg,value&0xffffffff)
  u.reg_write(UC_ARM_REG_SP,0x7100f000);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(symbols[name],done,count=2000000);assert u.reg_read(UC_ARM_REG_PC)==done
  return u.reg_read(UC_ARM_REG_R0)
 assert call('test_other')==0
 if case=='wrong-owner':put(symbols['xw_test_thread'],18)
 assert call('test_start')==0x58575052 and not entered
 if case=='radio-wait':put(symbols['test_radio_wait'],2)
 if case=='sdk-wait':put(symbols['test_sdk_wait'],2)
 if case=='root-changed':put(0x613e68,1)
 if case=='code-changed':put(0x10d80,get(0x10d80)^1)
 if case=='radio-failed':put(symbols['test_radio_result'],-4)
 if case=='sdk-failed':put(symbols['test_sdk_result'],-2)
 call('xw_player_handoff_tick')
 if case in ('radio-wait','sdk-wait'):
  assert not entered;call('xw_player_handoff_tick');assert not entered
 for i in range(6):call('xw_player_handoff_tick')
 success=case in ('ready','radio-wait','sdk-wait','duplicate') or case.startswith('resume-')
 assert len(entered)==int(success) and len(completed)==int(success) and components==(list(callbacks) if success else [])
 if case.startswith('resume-'):
  client=0x820f68;put(client+4,1);put(client+20,7)
  if case=='resume-code':put(0x265510,get(0x265510)^1)
  if case!='resume-no-entry':assert call('test_resume_begin')==(0x58575052 if case=='resume-code' else 0)
  call('xw_player_handoff_tick');assert not get(symbols['test_resume_calls'])
  put(0x613e64,7);put(client+4,2);put(client+20,7 if case=='resume-stale-sequence' else 8)
  if case=='resume-foreign':put(symbols['xw_test_thread'],18)
  call('test_activation',0xdead0000 if case=='resume-wrong-client' else client,16 if case=='resume-ack-error' else 0)
  put(symbols['xw_test_thread'],17)
  if case=='resume-pending':put(symbols['test_resume_wait'],2)
  if case=='resume-failed':put(symbols['test_resume_result'],-4)
  for i in range(4):call('xw_player_handoff_tick')
  expected=3 if case=='resume-pending' else 1 if case in ('resume-ok','resume-failed') else 0
  assert get(symbols['test_resume_calls'])==expected,(case,get(symbols['test_resume_calls']))
  call('test_activation',client,0);call('xw_player_handoff_tick')
  if case in ('resume-ok','resume-pending'):
   assert get(symbols['test_resume_calls'])==expected
   assert call('test_start')==0x58575052;call('xw_player_handoff_tick');assert len(entered)==2
  rows.append(dict(case=case,original_calls=len(entered),resume_polls=get(symbols['test_resume_calls'])))
  continue
 assert call('test_start')==0x58575052
 for i in range(3):call('xw_player_handoff_tick')
 assert len(entered)==int(success)
 rows.append(dict(case=case,original_calls=len(entered),radio_polls=get(symbols['test_radio_calls']),sdk_polls=get(symbols['test_sdk_calls'])))
print(json.dumps(dict(passed=True,device_accessed=False,firmware_created=False,cases=rows,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in [*sources,'tools/test_player_handoff_bridge.py','runtime/platform/player/host_handoff_bridge.h','runtime/platform/player/stock_prepare_view.h']},limits=['Production C wait/view and original command6 coordinator execute; radio/SDK stop and component/finalizer effects are fixtures.','No native callsite binding, command7 completion/rearm, original OS scheduling, hardware sleep/USB or flash qualification.']),indent=2))
