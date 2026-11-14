"""Real broker workers + service drain, host and original LinuxThreads ARM guest."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time,sys
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
host_wrapper='--host-wrapper' in sys.argv
handoff_revocation='--handoff-revocation' in sys.argv
assert not handoff_revocation or (host_wrapper and len(sys.argv)==3)
exit_after_drain='--exit-after-sdk-drain' in sys.argv
assert not exit_after_drain or (host_wrapper and len(sys.argv)==3)
native_forward_fault='--native-exit-forward-fault' in sys.argv
native_forward='--native-exit-forward' in sys.argv or native_forward_fault
assert not native_forward or (host_wrapper and len(sys.argv)==3)
wait_backpressure='--wait-backpressure' in sys.argv
assert not wait_backpressure or host_wrapper
bound_native_repeat='--bound-native-repeat' in sys.argv
assert not bound_native_repeat or host_wrapper
native_pending_view='--native-pending-view' in sys.argv
assert not native_pending_view or bound_native_repeat
clock_failure='--clock-failure' in sys.argv
exit_fault='--exit-fault' in sys.argv
native_exit_empty='--native-exit-empty' in sys.argv
inherited_delivery='--inherited-delivery' in sys.argv
exit_dependency='--exit-dependency' in sys.argv
revoke_parser=argparse.ArgumentParser(add_help=False)
revoke_parser.add_argument('--revoke-context',choices=('drain','retirement','radio-wait','radio-ready'))
revoke_context=revoke_parser.parse_known_args()[0].revoke_context
native_retry_after_revoke='--native-retry-after-revoke' in sys.argv
assert not native_retry_after_revoke or (revoke_context in ('drain','radio-wait','radio-ready') and host_wrapper and exit_dependency)
assert revoke_context not in ('radio-wait','radio-ready') or native_retry_after_revoke
assert not revoke_context or (host_wrapper and exit_dependency and not any((bound_native_repeat,clock_failure,exit_fault,native_exit_empty,inherited_delivery)))
user_stop_fault='--user-stop-fault' in sys.argv
settings_requests='--settings-requests' in sys.argv
user_toggle='--user-toggle' in sys.argv or user_stop_fault
assert not user_toggle or (host_wrapper and not any((exit_dependency,inherited_delivery,native_exit_empty,clock_failure,exit_fault)))
assert not settings_requests or (host_wrapper and not any((user_toggle,exit_dependency,inherited_delivery,native_exit_empty,clock_failure,exit_fault)))
assert not exit_dependency or (host_wrapper and not native_exit_empty and not clock_failure and not exit_fault)
assert not inherited_delivery or (host_wrapper and not native_exit_empty and not clock_failure and not exit_fault)
assert not clock_failure or host_wrapper
assert not exit_fault or (host_wrapper and not clock_failure)
assert not native_exit_empty or (host_wrapper and not clock_failure and not exit_fault)
out=ROOT/('work/player-host-managed-test' if host_wrapper else 'work/player-service-drain')/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/player/'+n+'.c' for n in ('client','managed','managed_rpc','managed_channel','managed_control','rpc_wire','player_broker','metadata_async','local_identity','service_drain')]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events')]
sources+=['runtime/platform/player/drain_completion.c']
sources+=['runtime/platform/player/deferred_prepare.c']
sources+=['runtime/platform/player/managed_host.c','runtime/platform/player/session_offer.c','runtime/platform/services/descriptor.c']
if host_wrapper:sources+=['runtime/platform/player/host_managed_service.c']
if handoff_revocation:sources+=['runtime/platform/player/host_handoff_bridge.c']
if exit_after_drain:sources+=['tools/fixtures/player_prepare_rf_bridge.c']
if native_forward:
 bridge_source=(ROOT/'runtime/platform/player/host_prepare_bridge.c').read_text(encoding='utf-8')
 target='uintptr_t)XW_STOCK_PREPARE_COORDINATOR_ADDRESS'
 assert bridge_source.count(target)==1
 modeled=bridge_source.replace(target,'uintptr_t)xw_test_native_coordinator')
 assert modeled.replace('uintptr_t)xw_test_native_coordinator',target)==bridge_source
 generated=out/'native-forward-bridge.c'
 generated.write_text('#define XW_PLAYER_NATIVE_RF\n#include <stdint.h>\nextern int xw_test_native_coordinator(uint32_t,uint32_t,uint32_t *);\n'+modeled,encoding='utf-8')
 sources+=[generated.relative_to(ROOT).as_posix()]
if bound_native_repeat or native_retry_after_revoke:sources+=['tools/fixtures/player_prepare_rf_bridge.c']
if inherited_delivery:sources+=['runtime/platform/player/host_inherited.c']
fixture='tools/fixtures/player_host_managed_service.c' if host_wrapper else 'tools/fixtures/player_service_drain_threads.c';init_source='tools/fixtures/player_worker_system_init.c'
if handoff_revocation:fixture='tools/fixtures/player_handoff_service.c'
if exit_after_drain:fixture='tools/fixtures/player_exit_after_drain.c'
if native_forward:fixture='tools/fixtures/player_exit_after_drain.c'
flags=['-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if native_forward:flags+=['-DXW_TEST_NATIVE_FORWARD','-I'+str(ROOT/'runtime/platform/player')]
if native_forward_fault:flags+=['-DXW_TEST_NATIVE_FORWARD_FAULT']
if wait_backpressure:flags+=['-DXW_HOST_WAIT_BACKPRESSURE']
if bound_native_repeat:flags+=['-DXW_HOST_BOUND_NATIVE_REPEAT']
if native_pending_view:flags+=['-DXW_HOST_NATIVE_PENDING_VIEW']
if clock_failure:flags+=['-DXW_HOST_CLOCK_FAILURE']
if exit_fault:flags+=['-DXW_HOST_EXIT_FAULT']
if native_exit_empty:flags+=['-DXW_HOST_NATIVE_EXIT_EMPTY']
if inherited_delivery:flags+=['-DXW_HOST_INHERITED_DELIVERY']
if exit_dependency:flags+=['-DXW_HOST_EXIT_DEPENDENCY']
if revoke_context:flags+=['-DXW_HOST_REVOKED_CONTINUATION','-DXW_HOST_REVOKE_'+revoke_context.upper().replace('-','_')]
if native_retry_after_revoke:flags+=['-DXW_HOST_REVOKED_NATIVE_RETRY']
if user_toggle:flags+=['-DXW_HOST_USER_TOGGLE']
if user_stop_fault:flags+=['-DXW_HOST_USER_STOP_FAULT']
if settings_requests:flags+=['-DXW_HOST_SETTINGS_REQUESTS']
host=out/'host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined','-pthread',*sources,fixture,'-o',str(host)],cwd=ROOT,check=True)
run=subprocess.run([str(host)],capture_output=True,text=True,timeout=15)
(out/'host-result.json').write_text(json.dumps(dict(exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr,
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in [*sources,fixture,'runtime/platform/player/deferred_prepare.h']}),indent=2)+'\n')
assert run.returncode==0,run.stdout+run.stderr
libs=stock_libraries();startup=['runtime/store/start.c','runtime/store/start.S']
arm_flags=[*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
app=out/'test.arm';init=out/'init.arm'
for output,code in ((app,[*sources,fixture]),(init,[init_source])):
 subprocess.run(['arm-linux-gnueabi-gcc',*arm_flags,*code,*startup,str(libs['libpthread.so.0']),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(output)],cwd=ROOT,check=True)
report=run_guest(out,init,{'test':app},libs,['PLAYER_HOST_MANAGED_SERVICE_PASS' if host_wrapper else 'PLAYER_SERVICE_DRAIN_THREADS_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
paths=sources+startup+[fixture,init_source,'tools/fixtures/player_broker.c',Path(__file__).relative_to(ROOT).as_posix()]+[p.relative_to(ROOT).as_posix() for folder in ('runtime/platform/player','runtime/platform/services') for p in (ROOT/folder).glob('*.h')]
if handoff_revocation:paths+=['tools/fixtures/player_host_managed_service.c']
if exit_after_drain:paths+=['tools/fixtures/player_host_managed_service.c','runtime/platform/player/host_prepare_bridge.c']
if native_forward:paths+=['tools/fixtures/player_host_managed_service.c','runtime/platform/player/host_prepare_bridge.c']
if bound_native_repeat or native_retry_after_revoke:paths+=['runtime/platform/player/host_prepare_bridge.c']
report.update(host_sanitizers=True,real_blocked_workers=True,production_broker_and_service_drain=True,original_linuxthreads=True,moma_and_original_player_modeled=True,host_stdout=run.stdout,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(set(paths))},limits=['Generic ARM kernel, not Sony kernel/hardware.','Two actual reader threads hold modeled native handles until released by the fixture.','No original pending-table hook, library finalization or USB/sleep handshake executes.'])
report['managed_host_wrapper']=host_wrapper
report['application_handoff_revocation']=handoff_revocation
report['native_exit_after_sdk_drain']=exit_after_drain
report['native_exit_forwarding']=native_forward
report['native_exit_forwarding_fault']=native_forward_fault
report['exit_dependency_fixture']=exit_dependency
report['revoke_context_at']=revoke_context
report['native_retry_after_revoke']=native_retry_after_revoke
if revoke_context:report['limits'].append('Native continuation validity is revoked at a supplied boundary; real SDK/reader cleanup must finish without invoking that continuation. Radio retirement remains an independent callback fixture.')
report['user_toggle_fixture']=user_toggle
report['user_stop_fault_fixture']=user_stop_fault
report['settings_requests_fixture']=settings_requests
report['inherited_delivery']=inherited_delivery
report['clock_failure_fixture']=clock_failure
report['wait_backpressure']=wait_backpressure
report['exit_fault_fixture']=exit_fault
report['native_exit_empty_fixture']=native_exit_empty
if exit_fault:report['limits'].append('Exit fault retains SDK objects and suppresses native continuation; process exit is not evidence of graceful service drain.')
if host_wrapper:
 report['real_blocked_workers']=False;report['real_worker_threads']=True
 report['limits'][1]='Actual reader threads use modeled native handles and fixture delays; no explicit condition gate in this profile.'
 report['limits']+=['Real host dispatch/offer/prepare API and broker execute; original queue/source attachment and media/backend are models. No listener, original-manager policy or native hook is installed.']
if handoff_revocation:
 assert 'PLAYER_HANDOFF_SERVICE_CANCEL_PASS' in run.stdout
 assert 'PLAYER_HANDOFF_SERVICE_CANCEL_PASS' in (out/'serial.log').read_text(encoding='utf-8',errors='replace')
 report['limits'].append('Actual application-handoff bridge continues SDK/reader retirement after supplied Root revocation; native view and radio effects are models, with no stock coordinator forwarding.')
if exit_after_drain:
 assert 'PLAYER_EXIT_AFTER_DRAIN_PASS' in run.stdout
 assert 'PLAYER_EXIT_AFTER_DRAIN_PASS' in (out/'serial.log').read_text(encoding='utf-8',errors='replace')
 report['limits'].append('Actual SDK drain and RF-enabled native-exit bridge adopt a completed broker drain while independent retirement is pending. Native view/radio are models; no original coordinator or USB hardware executes.')
if native_forward:
 marker='PLAYER_NATIVE_EXIT_FORWARD_FAULT_PASS' if native_forward_fault else 'PLAYER_NATIVE_EXIT_FORWARD_PASS'
 assert marker in run.stdout
 assert marker in (out/'serial.log').read_text(encoding='utf-8',errors='replace')
 report['limits'].append('Actual RF-enabled exit bridge executes with only its native-coordinator call target replaced by a model. Native view/radio are models; no original finalizer or USB hardware executes.')
if native_exit_empty:
 report['real_worker_threads']=False;report['production_broker_and_service_drain']=False
 report['limits']=['No-resource native-exit admission/factory decision executes under the actual host wrapper; no SDK broker or worker starts.','Original native exit event and backend are modeled; no installed dispatcher or physical qualification.']
if settings_requests:
 report['real_worker_threads']=False;report['production_broker_and_service_drain']=False
 report['foreign_owner_probe_thread']=True
 report['limits']=['Actual private Settings queue/bind/result/cancel code executes; request backend and original player are modeled.',
                   'One foreign-owner probe thread is created/joined; no metadata/catalog worker, broker drain or RF owner starts.',
                   'Request delivery result is not radio status; no original GUI, power transition or device access.']
if bound_native_repeat:
 report['native_pending_view']=native_pending_view
 report['bound_native_repeat_fixture']=True
 report['real_worker_threads']=False;report['real_blocked_workers']=False;report['production_broker_and_service_drain']=False
 report['limits']=['Actual managed-service and RF-enabled prepare bridge execute on host sanitizers and ARM/Sony libc.',
  'Initialized provider, Root/image validation and verified-OFF radio response are fixtures; no actual radio owner, GUI or physical ordering executes.',
  'Repeated empty exit uses the same epoch and keeps admission closed; subsequent RF refusal suppresses native fallback.']
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print((out/'serial.log').read_text(errors='replace')[-900:]);print(json.dumps(report,indent=2));assert report['passed'],(out/'qemu.log').read_text(errors='replace')[-1000:]
