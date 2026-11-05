"""Pinned main-loop instruction -> PID shim -> actual provider owner binding."""
from pathlib import Path
import hashlib,io,json,struct,subprocess,sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from build_player_host import ROOT,CORE_SOURCES,ENGINE_SOURCES,PREPARE_SOURCES,build
engine_provider='--engine-provider' in sys.argv
native_prepare='--native-prepare' in sys.argv
native_settings='--native-settings' in sys.argv
native_wireless='--native-wireless-settings' in sys.argv
native_rf='--native-rf-gate' in sys.argv
native_sleep='--native-sleep-analysis' in sys.argv
if native_sleep:native_rf=True
remote_profile=Path(sys.argv[sys.argv.index('--remote-profile')+1]) if '--remote-profile' in sys.argv else None
if native_rf:native_wireless=True
if native_wireless:native_settings=True
if native_settings:native_prepare=engine_provider=True
SOURCES=CORE_SOURCES+(ENGINE_SOURCES if engine_provider else [])+(PREPARE_SOURCES if native_prepare else [])
_,candidate,build_report=build(engine_provider=engine_provider,native_prepare=native_prepare,builtin_localization=native_settings,native_remote_settings=native_settings,native_wireless_settings=native_wireless,native_rf_gate=native_rf,remote_profile=remote_profile,native_sleep_analysis=native_sleep);work=candidate.parent;artifact=work/'anchor-consumer.arm'
if native_wireless:SOURCES+=['runtime/platform/wireless/mode_policy.c','runtime/platform/wireless/native_setting.c']
if native_rf:SOURCES+=['runtime/platform/wireless/native_rf_dispatch.c','runtime/platform/wireless/native_rf_guard.c','runtime/platform/player/host_handoff_bridge.c']
fixture='tools/fixtures/player_host_anchor.c'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*(['-DXW_PLAYER_ENGINE_PROVIDER'] if engine_provider else []),*(['-DXW_PLAYER_NATIVE_PREPARE','-DXW_PLAYER_CAPTURE_ARG2'] if native_prepare else []),*(['-DXW_PLAYER_NATIVE_REMOTE_SETTINGS'] if native_settings else []),*(['-include',str(work/'wireless-profile.h')] if native_wireless else []),*(['-include',str(work/'rf-profile.h')] if native_rf else []),*(['-include',str(work/'remote_factory_profile.h')] if remote_profile else []),*SOURCES,fixture,'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
stock=candidate.read_bytes();helper=artifact.read_bytes();elf=ELFFile(io.BytesIO(helper));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
cases=[]
scenarios=('anchor','wrong-thread','bind-incompatible','unmodified','wrong-image','changed-following','fallback')+ (('native-factory','early-native-factory','foreign-native') if native_prepare else ())
if native_settings:scenarios+=('settings','settings-wrong-thread','settings-changed-code','settings-changed-pointer','settings-changed-rows')
if native_wireless:scenarios+=('wireless','wireless-unbound','wireless-wrong-thread','wireless-changed-code','wireless-changed-pointer')
if native_wireless:scenarios+=('mode-open','mode-open-unbound','mode-open-foreign','mode-open-code','mode-open-pointer')
if native_rf:scenarios+=('rf','rf-denied','rf-changed-code','rf-changed-site','rf-worker','rf-worker-changed-pointer','rf-worker-changed-code')
if native_rf:scenarios+=('rf-queue','rf-queue-changed-site','rf-queue-changed-code','rf-queue-foreign-thread')
if native_rf:scenarios+=('rf-queue-early','rf-queue-early-foreign')
if native_rf:scenarios+=('rf-off','rf-off-changed-code','rf-off-denied','rf-off-sealed','rf-cleanup','rf-cleanup-denied','rf-cleanup-sealed')
if native_rf:scenarios+=('rf-dispatch','rf-dispatch-nonstop','rf-dispatch-changed-code')
if native_rf:scenarios+=('handoff','handoff-changed-site','handoff-wrong-owner','handoff-activation-failed')
if native_sleep:scenarios+=('sleep','sleep-code','sleep-foreign','sleep-early','sleep-unbound-idle','sleep-unbound-busy','sleep-restore-entry','sleep-restore-complete','sleep-inactive-idle','sleep-inactive-busy','sleep-state-seven','sleep-initial-main')
if '--sleep-routing-only' in sys.argv:
 assert native_sleep
 scenarios=tuple(name for name in scenarios if name.startswith('sleep'))
if '--cold-routing-only' in sys.argv:
 assert native_rf
 scenarios=('handoff-cold-idle','handoff-cold-unbound','handoff-cold-busy','handoff-cold-resume-unbound','handoff-cold-resume-idle')
for scenario in scenarios:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 segments=[s for raw in (stock,helper) for s in ELFFile(io.BytesIO(raw)).iter_segments() if s['p_type']=='PT_LOAD'];merged=[]
 for start,end in sorted((int(s['p_vaddr'])&~4095,(int(s['p_vaddr'])+int(s['p_memsz'])+4095)&~4095) for s in segments):
  if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
  else:merged.append((start,end))
 for start,end in merged:u.mem_map(start,end-start)
 for s in segments:u.mem_write(int(s['p_vaddr']),s.data())
 stack,done=0x70000000,0x72000000;u.mem_map(stack,65536);u.mem_map(done,4096)
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(0x612c48,0)
 if scenario=='unmodified':put(0xff3c,0xeb025a89)
 if scenario=='changed-following':put(0xff40,0)
 if scenario=='wrong-image':put(symbols['xw_test_loaded'],0)
 if scenario=='bind-incompatible':u.mem_write(0x275e00,bytes([u.mem_read(0x275e00,1)[0]^1]))
 if scenario=='fallback':put(symbols['test_resolve'],0)
 stops=[done];fallbacks=[];plt_calls=[];native_calls=[];rf_calls=[];stock_worker_calls=[];stock_queue_calls=[];stock_dispatch_calls=[];rf_result=16
 def hook(uc,pc,size,data):
  if pc in stops:uc.emu_stop();return
  if pc==0xda84:plt_calls.append(pc);uc.reg_write(UC_ARM_REG_PC,symbols['getpid'])
  if native_sleep and pc in (0xb174c,0xb03e8,0xb17c4,0xf5c8):
   if pc==0xb03e8:native_calls.append(pc)
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if native_wireless and pc==0x88494:
   assert get(0x4ee5d8) in (0,1)
   uc.reg_write(UC_ARM_REG_R0,0x5a01);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if native_rf and pc==0x3b9a8:
   stock_worker_calls.append(uc.reg_read(UC_ARM_REG_R0));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if native_rf and pc==0x3b994:
   stock_queue_calls.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)])
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if native_rf and pc==0x61db4:
   stock_dispatch_calls.append(uc.reg_read(UC_ARM_REG_R0));put(symbols['test_errno'],909)
   uc.reg_write(UC_ARM_REG_R0,0x2468);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if native_rf and pc==0x2680a8:
   assert scenario in ('handoff','handoff-activation-failed') and uc.reg_read(UC_ARM_REG_R0)==0x820f68 and uc.reg_read(UC_ARM_REG_R1)==0
   put(0x820f68+20,8)
   if scenario=='handoff':put(0x820f68+4,2)
   put(symbols['test_errno'],909);uc.reg_write(UC_ARM_REG_R0,0 if scenario=='handoff' else 16);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if native_rf and pc in (0xda9c,0xe108,0xda3c,0xe2ac,0xe030,0xd640,0xd880,0xdf4c,0xd4fc,0xd958,0xd8bc,0xddfc):
   rf_calls.append((pc,[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]))
   put(symbols['test_errno'],909);uc.reg_write(UC_ARM_REG_R0,rf_result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if native_rf and pc==0xb3248:
   uc.reg_write(UC_ARM_REG_R0,7);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if native_rf and pc in (0x33b918,0x33b83c):
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if native_settings and pc==0x74634:
   uc.reg_write(UC_ARM_REG_R0,0xfd0000);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==symbols['dladdr']:put(symbols['test_errno'],987)
  if native_prepare and pc==0x112fc:
   if scenario=='sleep-restore-entry':
    assert uc.reg_read(UC_ARM_REG_R0)==0x613e60 and uc.reg_read(UC_ARM_REG_R1)==15
    native_calls.append(15);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   if scenario.startswith('handoff'):
    assert uc.reg_read(UC_ARM_REG_R0)==0x613e60 and uc.reg_read(UC_ARM_REG_R1) in (6,7)
    put(0x613e64,uc.reg_read(UC_ARM_REG_R1))
    native_calls.append(uc.reg_read(UC_ARM_REG_R2));put(symbols['test_errno'],909)
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   assert uc.reg_read(UC_ARM_REG_R0)==0x613e60 and uc.reg_read(UC_ARM_REG_R1)==3,('native-args',hex(uc.reg_read(UC_ARM_REG_R0)),hex(uc.reg_read(UC_ARM_REG_R1)))
   assert get(symbols['test_errno'])==77,('errno',get(symbols['test_errno']),get(symbols['test_exit_events']),get(symbols['test_prepare_decisions']))
   native_calls.append(uc.reg_read(UC_ARM_REG_R2));put(symbols['test_errno'],909)
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def syscall(uc,number,data):
  assert get(uc.reg_read(UC_ARM_REG_PC)-4)==0xef900014
  fallbacks.append(number);uc.reg_write(UC_ARM_REG_R0,4321)
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,syscall)
 def call(address,return_to=done):
  stops[:]=[return_to];u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,return_to)
  # Deliberately invalid pointer-looking values: the argument-free fallback
  # must not interpret these as addresses or write through them.
  u.reg_write(UC_ARM_REG_R0,0xdead0001);u.reg_write(UC_ARM_REG_R1,0xbeef0001)
  try:u.emu_start(address,return_to+4,count=30000000)
  except Exception as error:raise AssertionError((scenario,hex(address),hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)))) from error
  assert u.reg_read(UC_ARM_REG_PC)==return_to
  return u.reg_read(UC_ARM_REG_R0)
 if native_rf:
  # Supply the native command3 view now required before radio retirement.
  put(0x613e64,1);put(0x613e68,0);put(0x613eac,1);put(0x613e8c,0x66efe8);put(0x66efe8,0)
 call(symbols['host_initialize'])
 if scenario.startswith('handoff-cold'):
  provider_ready=not scenario.endswith('unbound')
  if provider_ready:
   assert call(0xff3c,0xff40)==0
   put(symbols['test_sleep_unbound'],1)
   if scenario=='handoff-cold-busy':put(symbols['test_sleep_busy'],1)
  else:assert not call(symbols['xw_player_host_anchor_ready'])
  command=7 if 'resume' in scenario else 6
  entry=0x71cd8 if command==7 else 0x71f5c
  def cold_args(uc,pc,size,data):
   if pc==entry:
    for reg,value in ((UC_ARM_REG_R0,0x613e60),(UC_ARM_REG_R1,command),(UC_ARM_REG_R2,stack+128)):uc.reg_write(reg,value)
  handle=u.hook_add(UC_HOOK_CODE,cold_args)
  assert call(entry,entry+4)==0
  u.hook_del(handle)
  expected=int(scenario!='handoff-cold-busy')
  assert len(native_calls)==expected,('cold stock coordinator routing mismatch',scenario,native_calls)
  cases.append(dict(case=scenario,command=command,provider_ready=provider_ready,native_prepare_calls=len(native_calls),stock_startup_passthrough=bool(expected)))
  continue
 if scenario=='sleep-early':assert call(0x61c44)==0 and native_calls==[0xb03e8] and not get(symbols['test_sleep_begins'])
 assert call(symbols['xw_player_host_pid_resolved'])==int(scenario!='fallback')
 if scenario.startswith('rf-queue-early'):
  message=stack+0x100;context=stack+0x200;u.mem_write(message,struct.pack('<4I',0,0x4c0007,0x12345678,0x87654321))
  if scenario=='rf-queue-early-foreign':put(symbols['xw_test_thread'],18)
  def early_args(uc,pc,size,data):
   if pc in (0x10958,0x4d87fc):
    for reg,n in ((UC_ARM_REG_R0,context),(UC_ARM_REG_R1,message),(UC_ARM_REG_R2,0x13572468)):uc.reg_write(reg,n)
  handle=u.hook_add(UC_HOOK_CODE,early_args)
  assert call(0x10958,0x1095c)==0;u.hook_del(handle)
  assert not call(symbols['xw_player_host_anchor_ready']) and stock_queue_calls==[[context,message,0x13572468]]
  assert get(symbols['test_wireless_requests'])==int(scenario=='rf-queue-early') and get(symbols['test_errno'])==1234
  put(symbols['xw_test_thread'],17)
 if scenario=='early-native-factory':
  put(symbols['test_errno'],77);assert call(0x718c0)==0 and len(native_calls)==1 and get(symbols['test_errno'])==909
  assert get(symbols['test_exit_events'])==1 and not get(symbols['test_prepare_decisions'])
  put(symbols['test_errno'],1234)
 # The direct call covers a coincidental FF40 caller in an unmodified image.
 result=call(symbols['getpid'] if scenario=='unmodified' else 0xff3c,0xff40)
 active=scenario in ('anchor','wrong-thread','fallback','native-factory','early-native-factory','foreign-native') or scenario.startswith(('settings','wireless','rf','mode-open','handoff','sleep'))
 assert call(symbols['xw_player_host_anchor_ready'])==int(active),scenario
 assert get(symbols['test_errno'])==1234
 if scenario in ('native-factory','foreign-native'):
  put(symbols['test_errno'],77)
  if scenario=='foreign-native':put(symbols['xw_test_thread'],18)
  assert call(0x718c0)==0
  assert len(native_calls)==int(scenario=='native-factory') and get(symbols['test_errno'])==(909 if scenario=='native-factory' else 77)
  assert get(symbols['test_prepare_decisions'])==int(scenario=='native-factory')
  put(symbols['xw_test_thread'],17)
  put(symbols['test_errno'],1234)
 if active:
  assert result==0 and get(symbols['test_dispatch_calls'])==1 and get(symbols['test_initialized'])==1
  assert get(symbols['test_poll_result'])==0xfffffffe # uninitialized stock AudioC is unavailable
  if scenario=='wrong-thread':
   put(symbols['xw_test_thread'],18);assert call(0xff3c,0xff40)==0 and get(symbols['test_dispatch_calls'])==1
   put(symbols['xw_test_thread'],17)
  for _ in range(200):assert call(0xff3c,0xff40)==0
  assert get(symbols['test_dispatch_calls'])==201
  if native_sleep:assert get(symbols['test_sleep_polls'])==201
  if scenario in ('sleep','sleep-code','sleep-foreign','sleep-unbound-idle','sleep-unbound-busy','sleep-inactive-idle','sleep-inactive-busy','sleep-state-seven','sleep-initial-main'):
   if scenario=='sleep-code':put(0x61648,get(0x61648)^1)
   if scenario=='sleep-foreign':put(symbols['xw_test_thread'],18)
   if scenario.startswith('sleep-unbound'):
    put(symbols['test_sleep_unbound'],1)
    if scenario=='sleep-unbound-busy':put(symbols['test_sleep_busy'],1)
   if scenario.startswith('sleep-inactive'):
    put(symbols['test_sleep_inactive'],1)
    if scenario=='sleep-inactive-busy':put(symbols['test_sleep_busy'],1)
   entry,result=(0x61928,4) if scenario=='sleep-state-seven' else (0x614e4,2) if scenario=='sleep-initial-main' else (0x61c44,0)
   assert call(entry)==result
   assert len(native_calls)==int(scenario in ('sleep-unbound-idle','sleep-inactive-idle'))
   assert get(symbols['test_sleep_begins'])==int(scenario in ('sleep','sleep-state-seven','sleep-initial-main'))
   assert get(symbols['test_errno'])==1234
   put(symbols['xw_test_thread'],17)
  if scenario=='sleep-restore-entry':
   def restore_args(cpu,pc,size,unused):
    if pc==0x71e6c:
     cpu.reg_write(UC_ARM_REG_R0,0x613e60);cpu.reg_write(UC_ARM_REG_R1,15);cpu.reg_write(UC_ARM_REG_R2,stack+0x100)
   restore_hook=u.hook_add(UC_HOOK_CODE,restore_args)
   assert call(0x71e6c,0x71e70)==0;u.hook_del(restore_hook)
   assert native_calls==[15] and get(symbols['test_sleep_restore_begins'])==1 and get(symbols['test_errno'])==1234
  if scenario=='sleep-restore-complete':
   assert call(0x4d8940)==1
   assert get(symbols['test_sleep_restore_completes'])==1 and get(symbols['test_sleep_restore_result'])==1 and get(symbols['test_errno'])==1234
  if native_rf:assert get(symbols['test_wireless_ticks'])==201
  if scenario.startswith('rf-dispatch'):
   message=stack+0x100;event=0x4c0007 if scenario=='rf-dispatch-nonstop' else 0x4c0006
   payload=struct.pack('<4I',0,event,0x12345678,0x87654321);u.mem_write(message,payload)
   if scenario=='rf-dispatch-changed-code':put(0x4d8710,get(0x4d8710)^1)
   def dispatch_args(uc,pc,size,data):
    if pc==0x3b9e4:
     uc.reg_write(UC_ARM_REG_R0,message)
     for reg,n in ((UC_ARM_REG_R4,0x11223344),(UC_ARM_REG_R5,0x22334455),(UC_ARM_REG_R6,0x33445566)):uc.reg_write(reg,n)
   handle=u.hook_add(UC_HOOK_CODE,dispatch_args)
   assert call(0x3b9e4,0x3b9e8)==0x2468;u.hook_del(handle)
   assert stock_dispatch_calls==[message] and bytes(u.mem_read(message,16))==payload
   assert [u.reg_read(reg) for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6)]==[0x11223344,0x22334455,0x33445566]
   assert get(symbols['test_disable_checks'])==int(scenario=='rf-dispatch') and get(symbols['test_errno'])==909
   if scenario=='rf-dispatch':assert get(symbols['test_disable_event'])==event
   put(symbols['test_errno'],1234)
  if scenario.startswith('rf-off'):
   cleanup=2 if scenario=='rf-off-sealed' else 1 if scenario=='rf-off-denied' else 0
   put(symbols['test_rf_cleanup_mode'],cleanup)
   if scenario=='rf-off-changed-code':put(0x4d8710,get(0x4d8710)^1)
   put(symbols['xw_test_thread'],18)
   for rf_result in (0,16):
    put(symbols['test_errno'],1234)
    called=scenario=='rf-off';skipped=scenario=='rf-off-sealed'
    assert call(0xb34c8)==(rf_result if called else 0 if skipped else 1) and get(symbols['test_errno'])==(909 if called else 1234)
   assert [target for target,args in rf_calls]==([0xd4fc,0xd4fc] if scenario=='rf-off' else [])
   assert get(symbols['test_poweroff_notes'])==(2 if scenario in ('rf-off','rf-off-sealed') else 0)
   if scenario=='rf-off':assert get(symbols['test_poweroff_result'])==16
   put(symbols['xw_test_thread'],17);put(symbols['test_errno'],1234)
  if scenario.startswith('rf-cleanup'):
   cleanup=2 if scenario.endswith('sealed') else 1 if scenario.endswith('denied') else 0
   put(symbols['test_rf_cleanup_mode'],cleanup);put(symbols['xw_test_thread'],18)
   for entry in (0xb3624,0xb35b4,0xb4078):
    put(symbols['test_errno'],1234);u.reg_write(UC_ARM_REG_R7,0x55667788)
    assert call(entry)==(16 if cleanup==0 else 0 if cleanup==2 else 1)
    assert get(symbols['test_errno'])==(909 if cleanup==0 else 1234) and u.reg_read(UC_ARM_REG_R7)==0x55667788
   assert [target for target,args in rf_calls]==([0xd958,0xd8bc,0xddfc] if cleanup==0 else [])
   assert get(symbols['test_rf_cleanup_permissions'])==3
   put(symbols['xw_test_thread'],17);put(symbols['test_errno'],1234)
  if scenario.startswith('rf-queue') and not scenario.startswith('rf-queue-early'):
   message=stack+0x100;context=stack+0x200
   payload=struct.pack('<4I',0,0x4c0007,0x12345678,0x87654321);u.mem_write(message,payload)
   if scenario=='rf-queue-changed-site':put(0x10958,get(0x10958)^1)
   if scenario=='rf-queue-changed-code':put(0x4d8710,get(0x4d8710)^1)
   if scenario=='rf-queue-foreign-thread':put(symbols['xw_test_thread'],18)
   def queue_args(uc,pc,size,data):
    if pc in (0x10958,0x4d87fc):
     for reg,n in ((UC_ARM_REG_R0,context),(UC_ARM_REG_R1,message),(UC_ARM_REG_R2,0x13572468),(UC_ARM_REG_R7,0x55667788)):uc.reg_write(reg,n)
   handle=u.hook_add(UC_HOOK_CODE,queue_args)
   entry,return_to=(0x4d87fc,done) if scenario=='rf-queue-changed-site' else (0x10958,0x1095c)
   assert call(entry,return_to)==0
   u.hook_del(handle)
   assert stock_queue_calls==[[context,message,0x13572468]] and bytes(u.mem_read(message,16))==payload
   assert u.reg_read(UC_ARM_REG_R7)==0x55667788 and get(symbols['test_errno'])==1234
   assert get(symbols['test_wireless_requests'])==int(scenario=='rf-queue')
   if scenario=='rf-queue':assert get(symbols['test_wireless_event'])==0x4c0007
   put(symbols['xw_test_thread'],17)
  if scenario.startswith('rf-worker'):
   if scenario=='rf-worker-changed-pointer':put(0x3c138,get(0x3c138)^4)
   if scenario=='rf-worker-changed-code':put(0x4d8710,get(0x4d8710)^1)
   put(symbols['xw_test_thread'],18)
   assert call(0x4d87e0)==0 and stock_worker_calls==[0xdead0001]
   assert get(symbols['test_rf_worker_entries'])==int(scenario=='rf-worker')
   assert get(symbols['test_errno'])==1234
   put(symbols['xw_test_thread'],17)
  if scenario in ('rf','rf-denied','rf-changed-code','rf-changed-site'):
   put(symbols['test_rf_allowed'],int(scenario!='rf-denied'))
   if scenario=='rf-changed-code':put(0x4d8710,get(0x4d8710)^1)
   if scenario=='rf-changed-site':put(0xb3484,get(0xb3484)^1)
   put(symbols['xw_test_thread'],18) # Worker path does not touch GUI-owned state.
   for entry in (0xb3458,0xb3784,0xb3538,0xb3ee4,0xb3f70,0xb3ffc):
    if scenario=='rf-changed-site' and entry==0xb3458:continue
    def rf_args(uc,pc,size,data):
     if pc==entry:
      for reg,n in ((UC_ARM_REG_R0,0x12345678),(UC_ARM_REG_R1,0x23456789),(UC_ARM_REG_R2,0x3456789a),(UC_ARM_REG_R7,0x55667788)):uc.reg_write(reg,n)
    handle=u.hook_add(UC_HOOK_CODE,rf_args)
    put(symbols['test_errno'],1234)
    assert call(entry)==(16 if scenario=='rf' else 1)
    u.hook_del(handle);assert u.reg_read(UC_ARM_REG_R7)==0x55667788 and get(symbols['test_errno'])==(909 if scenario=='rf' else 1234)
   assert len(rf_calls)==(10 if scenario=='rf' else 0)
   assert get(symbols['test_rf_permissions'])==(10 if scenario in ('rf','rf-denied') else 0)
   if scenario=='rf':
    for target,args in rf_calls:
     if target in (0xe2ac,0xdf4c):assert args[0]==0x12345678
     if target in (0xd640,0xd880):assert args==[0x12345678,0x23456789,0x3456789a]
   put(symbols['xw_test_thread'],17)
   put(symbols['test_errno'],1234)
  if scenario.startswith('handoff'):
   if scenario=='handoff-changed-site':put(0x71f5c,get(0x71f5c)^1)
   if scenario=='handoff-wrong-owner':put(symbols['xw_test_thread'],18)
   entry=0x4d7fc0 if scenario=='handoff-changed-site' else 0x71f5c
   return_to=done if scenario=='handoff-changed-site' else 0x71f60
   def handoff_args(uc,pc,size,data):
    if pc==entry:
     for reg,value in ((UC_ARM_REG_R0,0x613e60),(UC_ARM_REG_R1,6),(UC_ARM_REG_R2,stack+128)):uc.reg_write(reg,value)
   handle=u.hook_add(UC_HOOK_CODE,handoff_args)
   assert call(entry,return_to)==0 and not native_calls
   u.hook_del(handle);put(symbols['xw_test_thread'],17)
   call(0xff3c,0xff40)
   accepted=scenario in ('handoff','handoff-activation-failed')
   assert len(native_calls)==int(accepted) and get(symbols['test_errno'])==1234
   call(0xff3c,0xff40)
   assert len(native_calls)==int(accepted)
   if accepted:
    put(0x820f68+4,1);put(0x820f68+20,7)
    def resume_args(uc,pc,size,data):
     if pc==0x71cd8:
      for reg,value in ((UC_ARM_REG_R0,0x613e60),(UC_ARM_REG_R1,7),(UC_ARM_REG_R2,stack+128)):uc.reg_write(reg,value)
    handle=u.hook_add(UC_HOOK_CODE,resume_args)
    assert call(0x71cd8,0x71cdc)==0 and len(native_calls)==2
    u.hook_del(handle)
    def activation_args(uc,pc,size,data):
     if pc==0xb0624:
      uc.reg_write(UC_ARM_REG_R0,0x820f68);uc.reg_write(UC_ARM_REG_R1,0)
    handle=u.hook_add(UC_HOOK_CODE,activation_args)
    assert call(0xb0624,0xb0628)==(0 if scenario=='handoff' else 16)
    u.hook_del(handle);assert get(symbols['test_errno'])==909
    call(0xff3c,0xff40)
    def next_handoff(uc,pc,size,data):
     if pc==0x71f5c:
      for reg,value in ((UC_ARM_REG_R0,0x613e60),(UC_ARM_REG_R1,6),(UC_ARM_REG_R2,stack+128)):uc.reg_write(reg,value)
    handle=u.hook_add(UC_HOOK_CODE,next_handoff)
    assert call(0x71f5c,0x71f60)==0
    u.hook_del(handle);call(0xff3c,0xff40)
    assert len(native_calls)==(3 if scenario=='handoff' else 2)
    put(symbols['test_errno'],1234)
  if scenario.startswith('mode-open'):
   if scenario!='mode-open-unbound':assert call(symbols['test_wireless_bind'])==0
   if scenario=='mode-open-foreign':put(symbols['xw_test_thread'],18)
   for name,address in (('mode-open-code',0x4d8100),('mode-open-pointer',0x405304)):
    if scenario==name:put(address,get(address)^1)
   caller=int(build_report['wireless_composition']['initializer']['request_caller'],16)
   u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,caller)
   u.reg_write(UC_ARM_REG_R0,5);u.reg_write(UC_ARM_REG_R1,0);stops[:]=[caller]
   u.emu_start(symbols['getpid'],caller+4,count=30000000)
   expected=0x574e0001 if scenario=='mode-open' else 0x574dfffa if scenario=='mode-open-foreign' else 0x574dfffd if scenario in ('mode-open-code','mode-open-pointer') else 0x574dffff
   assert u.reg_read(UC_ARM_REG_R0)==expected and get(symbols['test_errno'])==1234
   put(symbols['xw_test_thread'],17)
  if scenario.startswith('wireless'):
   if scenario!='wireless-unbound':assert call(symbols['test_wireless_bind'])==0
   if scenario=='wireless-wrong-thread':put(symbols['xw_test_thread'],18)
   mutations={'wireless-changed-code':0x4d8500,'wireless-changed-pointer':0x405438}
   if scenario in mutations:
    address=mutations[scenario];u.mem_write(address,bytes([u.mem_read(address,1)[0]^1]))
   put(0x4ee5d8,2)
   if scenario in mutations:
    # Enter shim directly with the qualified return site, avoiding execution
    # of deliberately damaged code. Image guard must reject before the endpoint.
    caller=int(build_report['wireless_composition']['request_caller'],16)
    u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,caller)
    u.reg_write(UC_ARM_REG_R0,2);u.reg_write(UC_ARM_REG_R1,2);stops[:]=[caller]
    u.emu_start(symbols['getpid'],caller+4,count=30000000)
    assert u.reg_read(UC_ARM_REG_R0)==0x574dfffd
   else:
    def apply_hook(uc,pc,size,data):
     if pc==0x4d8500:uc.reg_write(UC_ARM_REG_R2,0xff0000)
    handle=u.hook_add(UC_HOOK_CODE,apply_hook)
    assert call(0x4d8500)==(0x5a01 if scenario=='wireless' else 0x9a01)
    u.hook_del(handle)
   put(symbols['xw_test_thread'],17)
   if scenario!='wireless-unbound':assert call(symbols['test_wireless_mode'])==(2 if scenario=='wireless' else 0)
   assert get(symbols['test_errno'])==1234
  if scenario.startswith('settings'):
   mutations={'settings-changed-code':0x4d8040,'settings-changed-pointer':0x411350,'settings-changed-rows':0x4d802c}
   if scenario in mutations:
    address=mutations[scenario];u.mem_write(address,bytes([u.mem_read(address,1)[0]^1]))
    assert call(symbols['getpid'],0x4d8078)==0xfffffffd
   else:
    if scenario=='settings-wrong-thread':put(symbols['xw_test_thread'],18)
    assert call(0x4d8040)==0x201
   assert get(symbols['test_settings_requests'])==int(scenario=='settings')
   assert get(symbols['test_errno'])==1234
   put(symbols['xw_test_thread'],17)
 else:
  assert get(symbols['test_dispatch_calls'])==0
  assert result==(0 if scenario=='bind-incompatible' else 4321)
 before=get(symbols['test_dispatch_calls']);assert call(symbols['getpid'])==4321
 assert get(symbols['test_dispatch_calls'])==before and get(symbols['test_errno'])==1234
 if scenario=='fallback':assert fallbacks and get(symbols['test_pid_calls'])==0
 else:assert not fallbacks
 if remote_profile:assert get(symbols['test_factory_ticks'])==get(symbols['test_dispatch_calls']),scenario
 cases.append(dict(case=scenario,provider_ready=active,dispatches=get(symbols['test_dispatch_calls']),original_plt_calls=len(plt_calls),fallback_calls=len(fallbacks),native_prepare_calls=len(native_calls),observer_errno_preserved=True))
report=dict(passed=True,remote_factory_tick_route=bool(remote_profile),factory_tick_implementation_modeled=bool(remote_profile),device_accessed=False,original_anchor_instruction=True,actual_provider_binding=True,stock_app_booted=False,cases=cases,candidate_sha256=build_report['candidate_sha256'],
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES+[fixture,'tools/fixtures/stock_provider_host.c','tools/fixtures/stock_host_image.c','tools/test_player_host_anchor.py']},
 limits=['Loaded-image identity, RTLD_NEXT, original PID PLT routing and the kernel PID result are modeled.',
         'The patched ARM call, guarded shim, actual native provider binding and client snapshot call execute; stock AudioC is intentionally uninitialized.',
         'No endpoint, worker, device execution, flash package or sleep/USB validation is provided.'])
report['engine_provider']=engine_provider
report['native_prepare']=native_prepare
report['native_settings_bridge']=native_settings
report['native_wireless_bridge']=native_wireless
report['native_rf_gate']=native_rf
report['native_sleep_analysis']=native_sleep
if native_prepare:report['limits'].append('Native-prepare helper runs production PID/glue routing with no-resource policy/notification fixtures; original prepare body is intercepted. Full DSO links the production managed policy but is not booted here.')
(work/'anchor-test.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
