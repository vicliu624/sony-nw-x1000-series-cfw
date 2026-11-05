"""Original action/bridge -> actual C glue/view/deferred drain -> prepare.

Host ownership policy, workers and native component effects remain fixtures.
"""
import contextlib,hashlib,io,json,runpy,struct,subprocess,time,sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
work=ROOT/'work/player-prepare-dispatch'/str(time.time_ns());work.mkdir(parents=True)
wireless='--wireless' in sys.argv
original_finalize='--finalize-original' in sys.argv
assert not original_finalize or wireless
with contextlib.redirect_stdout(io.StringIO()):composed=runpy.run_path(str(ROOT/'tools/test_player_prepare_composition.py'))
native=composed['artifact'].read_bytes()
sources=['runtime/platform/player/'+n for n in ('host_pid.S','host_prepare_bridge.c','stock_prepare_view.c','stock_image.c','client.c','service_drain.c','deferred_prepare.c')]+['runtime/platform/services/session.c','runtime/native/sha256.c','tools/fixtures/player_prepare_dispatch.c']
binary=work/'dispatch.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-DXW_PLAYER_CAPTURE_ARG2',*(['-DXW_PLAYER_NATIVE_RF'] if wireless else []),'-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
rows=[];callbacks=(0x16b74,0x143c0,0xf32c,0x3b498,0x37f08,0x49d6c,0x4492c,0x499f8,0x4f3dc)
for case in ('factory','owned','context-changed','code-changed','initial-code-refused','unknown-decision','wrong-owner',*(('factory-radio-unbound','owned-radio-unbound','factory-startup-incomplete','factory-native-pending','factory-existing-native-token','factory-existing-native-token-radio-pending','factory-existing-native-token-revoked') if wireless else ())):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 segments=[s for elf in (ELFFile(io.BytesIO(native)),helper) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 merged=[]
 for start,end in sorted((int(s['p_vaddr'])&~4095,(int(s['p_vaddr'])+int(s['p_memsz'])+4095)&~4095) for s in segments):
  if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
  else:merged.append((start,end))
 for start,end in merged:u.mem_map(start,end-start)
 for s in segments:u.mem_write(int(s['p_vaddr']),s.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 put(0x613e64,1);put(0x613e68,0);put(0x613eac,1);put(0x613eb0,0 if case=='factory-startup-incomplete' else 1);put(0x613e8c,0x66efe8);put(0x66efe8,0)
 entered=[];components=[];completed=[];finalize_calls=[]
 finalize_boundaries={0x3b0e0:'module-complete',0x50988:'service-complete',0x104fc:'root-flag',0x337dd4:'object-release',0x3ce08:'subsystem-get',0x3cdd0:'subsystem-release',0x288100:'moma-manager-release',0x28babc:'MomaLcPluginLib_finalize',0x2958a8:'MomaLib_finalize',0xa55b8:'queue-finalize',0x3365d4:'ticket-destroy',0x3378f4:'mutex-release',0xed94:'client-finalize',0xed98:'client-state-finalize',0xb6888:'input-get',0xb6b1c:'input-release',0xb6b18:'input-release-secondary'}
 def hook(cpu,pc,size,context):
  if pc==0xda84:cpu.reg_write(UC_ARM_REG_PC,symbols['getpid']);return
  value=0
  if pc==0x112fc:entered.append([cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]);return
  if pc in callbacks:
   assert cpu.reg_read(UC_ARM_REG_R1)==3;components.append(pc)
   token={0xf32c:0x123,0x4492c:0x456}.get(pc,0) if case=='factory-native-pending' else 0
   put(cpu.reg_read(UC_ARM_REG_R2),token)
  elif pc==0x1fd30:put(cpu.reg_read(UC_ARM_REG_R2),0)
  elif pc==0x10ee4:
   completed.append(pc)
   if original_finalize and case=='factory-native-pending':return
  elif original_finalize and case=='factory-native-pending' and pc in finalize_boundaries:
   finalize_calls.append(finalize_boundaries[pc])
  elif pc not in (0xff5c,0x116d4,0x33b83c,0x33b918):return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(name,args=()):
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):u.reg_write(reg,value)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(symbols[name] if isinstance(name,str) else name,done,count=4000000)
  assert u.reg_read(UC_ARM_REG_PC)==done
  v=u.reg_read(UC_ARM_REG_R0);return v if v<0x80000000 else v-0x100000000
 if case in ('factory','factory-radio-unbound','factory-startup-incomplete','factory-native-pending') or case.startswith('factory-existing-native-token'):put(symbols['test_prepare_owned'],0)
 else:assert call('test_init')==0
 if case=='initial-code-refused':u.mem_write(0x489dc,bytes([u.mem_read(0x489dc,1)[0]^1]))
 if case=='wrong-owner':put(symbols['xw_test_thread'],18)
 if case=='unknown-decision':put(symbols['test_decision_error'],-6)
 if wireless and case in ('owned','factory'):put(symbols['test_radio_pending'],1)
 if case.endswith('radio-unbound'):put(symbols['test_radio_unbound'],1)
 if case in ('factory-startup-incomplete','factory-native-pending'):put(symbols['test_radio_unbound'],1)
 if case.startswith('factory-existing-native-token'):
  put(0x66efe8,1);put(0x66efec,0x789)
  if case.endswith(('radio-pending','revoked')):put(symbols['test_radio_pending'],1)
 assert call(0x718c0)==0
 if case.startswith('factory-existing-native-token'):
  if case.endswith('revoked'):
   assert not entered
   put(symbols['test_prepare_owned'],1)
   call('xw_player_prepare_tick')
   assert not entered
   rows.append(dict(case=case,resource_reappearance_refuses_native_resume=True))
   continue
  if case.endswith('radio-pending'):
   assert not entered
   call('xw_player_prepare_tick')
  assert len(entered)==1,('Idle SDK consumed stock preparation because Sony already had a pending token',entered)
  rows.append(dict(case=case,original_prepare_called=True,stock_pending_state_not_used_as_sdk_ownership=True,native_effects_modeled=True))
  continue
 if case=='factory-startup-incomplete':
  assert len(entered)==1 and not components and not completed
  assert get(0x613e64)==1 and get(0x66efe8)==0
  put(0x613eb0,1) # Explicit later readiness fixture, not a production write.
  assert call(0x718c0)==0
  assert len(entered)==2 and len(components)==len(callbacks) and len(completed)==1
  rows.append(dict(case=case,original_readiness_getter_executed=True,first_native_call_declined_before_components=True,later_readiness_fixture_allows_exit=True))
  continue
 if case=='factory-native-pending':
  assert len(entered)==1 and len(components)==len(callbacks) and not completed
  assert get(0x613e64)==3 and get(0x66efe8)==2
  assert [get(0x66efec+i*4) for i in range(2)]==[0x123,0x456]
  assert get(get(symbols['test_output_value']))==1
  assert call(0x11250,(0x613e60,0x999))==0 and get(0x66efe8)==2 and not completed
  assert call(0x11250,(0x613e60,0x123))==0 and get(0x66efe8)==1 and not completed
  assert call(0x11250,(0x613e60,0x456))==0 and get(0x66efe8)==0 and len(completed)==1
  if original_finalize:
   assert finalize_calls.index('module-complete')<finalize_calls.index('MomaLcPluginLib_finalize')<finalize_calls.index('MomaLib_finalize')<finalize_calls.index('queue-finalize')<finalize_calls.index('client-finalize')
  rows.append(dict(case=case,original_pending_registration_and_completion_executed=True,pending_tokens=[0x123,0x456],unknown_token_preserves_pending=True,last_token_reaches_finalizer=True,finalizer_body_executed=original_finalize,cleanup_leaf_effects_modeled=True,finalizer_calls=finalize_calls))
  continue
 if case.endswith('radio-unbound'):
  expected=int(case=='factory-radio-unbound')
  assert len(entered)==expected,('Unbound radio must not suppress resource-free native exit',case,entered)
  assert len(completed)==expected and len(components)==len(callbacks)*expected
  call('xw_player_prepare_tick')
  assert len(entered)==expected
  rows.append(dict(case=case,native_prepare_calls=len(entered),completion_boundaries=len(completed),resource_free_stock_exit=bool(expected)))
  continue
 if wireless and case in ('owned','factory'):
  assert not entered
  if case=='owned':assert call('test_accepting')==1
  call('xw_player_prepare_tick')
  if case=='owned':assert not entered and call('test_accepting')==0
 if case=='factory':
  assert len(entered)==1 and components==list(callbacks) and len(completed)==1 and get(symbols['test_exit_events'])==1
  if not wireless:assert entered[0][2]==get(symbols['test_output_value'])
 elif case=='wrong-owner':assert not entered and not get(symbols['test_exit_events'])
 else:
  assert not entered
  # A later GUI tick reuses the caller's stack; never treat its old output
  # address as retained storage across that boundary.
  if not(wireless and case in ('initial-code-refused','owned')):assert get(get(symbols['test_output_value']))==0,case
  if case=='unknown-decision':assert call('test_step')==-1
  elif case=='initial-code-refused':assert call('test_step')==(-1 if wireless else -2)
  else:
   assert call('test_step')==-4 and not entered
   if case=='context-changed':put(0x613e68,1)
   if case=='code-changed':u.mem_write(0x10d80,bytes([u.mem_read(0x10d80,1)[0]^1]))
   put(symbols['test_readers'],0)
   result=call('test_step')
   if case=='owned':assert result==0 and len(entered)==1 and components==list(callbacks) and len(completed)==1
   else:assert result==-2 and not entered
  assert call(0x718c0)==0
  assert len(entered)==int(case=='owned') and get(symbols['test_exit_events'])==1
 assert get(symbols['test_reentries'])==int(case!='wrong-owner' and not(wireless and case=='initial-code-refused'))
 rows.append(dict(case=case,native_prepare_calls=len(entered),completion_boundaries=len(completed),component_callbacks=len(components),reentrant_context_replacement_refused=case!='wrong-owner'))
report=dict(passed=True,device_accessed=False,firmware_created=False,actual_arm_glue_view_deferred_and_native_prepare=True,cases=rows,
 input_image_sha256=hashlib.sha256(native).hexdigest(),
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/host_prepare_bridge.h','runtime/platform/player/stock_prepare_view.h','tools/fixtures/player_deferred_native.c','tools/fixtures/stock_info_host.c','tools/fixtures/stock_host_image.c','tools/test_player_prepare_dispatch.py']},
 limits=['The PID C dispatcher, host resource decision, worker readiness and owner identity are fixtures; native components/PCS/finalizer effects are intercepted.',
         'Actual C glue, code/Root view, client/session/drain core and native prepare coordination execute; no installed production dispatcher, full manager event ordering or hardware qualification.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
