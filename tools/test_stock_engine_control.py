"""Actual ARM engine-control binding/requests; CtrlInfo and queue primitives modeled."""
import hashlib,io,json,struct,subprocess,time,sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
out=ROOT/'work/stock-engine-control'/str(time.time_ns());out.mkdir(parents=True);binary=out/'engine.arm'
sources=['runtime/platform/player/stock_engine_control.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','tools/fixtures/player_engine_control.c']
provider_mode='--provider' in sys.argv
if provider_mode:sources+=['runtime/platform/player/client.c','runtime/platform/player/engine_provider.c']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*(['-DXW_ENGINE_PROVIDER_FIXTURE'] if provider_mode else []),*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
path=ROOT/'work/targets-jp/SpiderApp';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
stock_elf=ELFFile(io.BytesIO(raw));cancel_entry=next(s['st_value'] for s in stock_elf.get_section_by_name('.dynsym').iter_symbols() if s.name=='PltTicket_cancel')
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()};cases=[]
matrix=[('play',0,2,1),('pause',1,1,1),('next',2,1,1),('previous',3,2,1),('already-playing',0,1,1),('already-paused',1,2,1),('transition',0,3,-4),('error',0,2,-4),('no-track',0,2,-2),('no-controller',0,2,-2),('wrong-thread',0,2,-4),('allocation-failure',0,2,-9),('changed-code',0,2,-3)]
matrix += [('service-replaced-during-read',0,2,-4),('session-replaced-during-read',0,2,-4),('session-replaced-after-submit',0,2,-9)]
for case,op,primary,expected in matrix:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for image in (ELFFile(io.BytesIO(raw)),helper):
  for s in image.iter_segments():
   if s['p_type']!='PT_LOAD':continue
   a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00;allocations=[];native=[];recent=[]
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 put(0x6831dc,0);put(0x6922d8,area+0x1000);put(0x6922e8,6);put(area+0x1000,area+0x2000);put(area+0x1004,0x1234);put(area+0x2010,6);put(area+0x202c,area+0x2028);put(symbols['test_primary'],primary)
 if case=='error':put(symbols['test_error'],1)
 if case=='no-track':put(symbols['test_track'],0)
 if case=='no-controller':put(0x6922d8,0)
 if case=='changed-code':put(0x27d6a0,0)
 if case=='service-replaced-during-read':put(symbols['test_replace_session'],1)
 if case=='session-replaced-during-read':put(symbols['test_replace_session'],2)
 def hook(cpu,pc,size,context):
  recent.append(hex(pc));del recent[:-20]
  if pc==done:cpu.emu_stop();return
  if pc in (0x17c40,0x17c608):raise AssertionError('Unexpected UI dispatch')
  if pc in (0x27d6a0,0x27dacc,0x27db98):native.append(hex(pc));return
  def finish(value=0):cpu.reg_write(UC_ARM_REG_R0,value&0xffffffff);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  if pc==cancel_entry:finish();return
  if pc==0x27c378:
   assert cpu.reg_read(UC_ARM_REG_R0)==area+0x2000
   kind=cpu.reg_read(UC_ARM_REG_R2);assert kind==(0x12 if op<2 else 0x15 if op==2 else 0x16);allocations.append(kind)
   if case=='session-replaced-after-submit':put(area+0x1004,0x5678)
   if case=='allocation-failure':finish(1);return
   put(area+0x300c,kind);put(cpu.reg_read(UC_ARM_REG_R3),area+0x3000);finish();return
  if pc in (0x3c194,0xb6888,0x1542c):finish(area+0x4000);return
  if pc in (0x3cc14,0xb6b48,0x3cd34,0x116d4,0x33b83c,0x33b918,0x1764c,0x27d654,0x27d614,0x335788,0x3357e4,0x3354f4):finish()
 u.hook_add(UC_HOOK_CODE,hook)
 def call(name,*args):
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),list(args)+[0]*4):u.reg_write(reg,value)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
  try:u.emu_start(symbols[name],done+4,count=20000000)
  except Exception as error:raise AssertionError((case,name,hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)),native,allocations,recent)) from error
  assert u.reg_read(UC_ARM_REG_PC)==done;value=u.reg_read(UC_ARM_REG_R0);return value if value<0x80000000 else value-0x100000000
 bound=call('test_provider_bind') if provider_mode else call('xw_stock_engine_control_bind',symbols['engine'])
 if case=='changed-code':assert bound==expected;cases.append(dict(case=case,result=bound));continue
 assert bound==0
 if provider_mode:assert call('test_provider_invalid')==-1 and not native
 if case=='wrong-thread':put(symbols['test_thread'],8)
 rc=call('test_provider_command',op) if provider_mode else call('xw_stock_engine_control_command',symbols['engine'],op);assert rc==expected,(case,rc,native,allocations)
 attempted=case in ('play','pause','next','previous','allocation-failure','session-replaced-after-submit');assert len(native)==int(attempted) and len(allocations)==int(attempted)
 assert get(0x6831dc)==0 and get(0x6922e8)==6
 if case in ('play','pause','previous'):
  expected_options=[0,1] if op==0 else [1,1] if op==1 else [1,1000,1,1]
  assert [get(area+0x3028+i*4) for i in range(len(expected_options))]==expected_options
 if provider_mode:
  assert get(symbols['test_base_commands'])==0
  if case=='wrong-thread':assert call('test_provider_close')==-4
  put(symbols['test_thread'],7)
  assert call('test_provider_volume')==1 and get(symbols['test_base_commands'])==1
  assert call('test_provider_snapshot')==0 and get(symbols['test_base_snapshots'])==1
  assert call('test_provider_browse')==0 and get(symbols['test_base_browses'])==1
  assert call('test_provider_close')==0 and call('test_provider_base_alive')==1 and get(symbols['test_base_closes'])==0
 else:
  put(symbols['test_thread'],7);assert call('xw_stock_engine_control_unbind',symbols['engine'])==0
 cases.append(dict(case=case,result=rc,native_calls=native,allocations=allocations,audio_ui_actor_absent=True,ui_ticket_unchanged=True))
report=dict(passed=True,actual_arm_binding_and_native_request_construction=True,ctrl_info_and_queue_primitives_modeled=True,device_accessed=False,installed=False,cases=cases,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/stock_engine_control.h','runtime/platform/player/stock_info.h','tools/test_stock_engine_control.py']},limits=['Fresh CtrlInfo validation is a model here; original info reader has separate tests.','Native lifetime, actual owner identity, audio completion and post-handoff resource effects remain unqualified.','Existing stock provider/host do not select this binding; stable-track controls only, not PLAY from unloaded/stopped source.'])
report['engine_provider_adapter']=provider_mode
if provider_mode:report['source_hashes']['runtime/platform/player/engine_provider.h']=hashlib.sha256((ROOT/'runtime/platform/player/engine_provider.h').read_bytes()).hexdigest()
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
