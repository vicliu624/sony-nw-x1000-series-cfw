"""Full native supervisor/service chain in an isolated ARM guest; RF/media modeled."""
import hashlib,json,struct,subprocess,sys,time
from app_registry import ROOT
from build_remote_owner import build as build_owner
from build_remote_service import build as build_service, reviewed_service
from build_remote_supervisor import build as build_supervisor
from player_arm_guest import stock_libraries,run_guest
out=ROOT/'work/remote-supervisor-integration'/str(time.time_ns());out.mkdir(parents=True)
reusable='--reusable-sessions' in sys.argv
bad_generation='--bad-generation' in sys.argv
bad_grants='--bad-grants' in sys.argv
assert not (bad_generation and bad_grants)
direct_delivery='--direct-delivery' in sys.argv or bad_generation or bad_grants
managed_process='--managed-process' in sys.argv
automatic_factory='--automatic-factory' in sys.argv
owner_view_forward='--owner-view-forward' in sys.argv
shared_wifi='--shared-wifi' in sys.argv
application_handoff='--application-handoff' in sys.argv
native_owner_wait='--native-owner-wait' in sys.argv or application_handoff
native_worker_retirement='--native-worker-retirement' in sys.argv or native_owner_wait
native_exit_bridge='--native-exit-bridge' in sys.argv or native_worker_retirement
exit_idle_progress='--exit-idle-progress' in sys.argv or native_exit_bridge
revoked_exit_context='--revoked-exit-context' in sys.argv
assert not revoked_exit_context or exit_idle_progress
assert not native_exit_bridge or (automatic_factory and not revoked_exit_context)
artwork_transfer='--artwork-transfer' in sys.argv
if artwork_transfer:
 from PIL import Image
 image=Image.new('RGB',(64,64))
 image.putdata([((x*19+y*13)&255,(x*7+y*29)&255,(x*31+y*5)&255) for y in range(64) for x in range(64)])
 image_path=out/'test-cover.jpg';image.save(image_path,format='JPEG',quality=95,subsampling=0)
 image_data=image_path.read_bytes()
 artwork_header=out/'artwork_test_payload.h'
 artwork_header.write_text('#define WR_CHAIN_ARTWORK_BYTES '+str(len(image_data))+'u\nstatic const unsigned char wr_chain_artwork_data[]={'+','.join(map(str,image_data))+'};\n')
service_handoff_refusal='--service-handoff-refusal' in sys.argv
service_start_refusal='--service-start-refusal' in sys.argv or service_handoff_refusal
assert not service_start_refusal or shared_wifi
assert not artwork_transfer or (shared_wifi and automatic_factory and owner_view_forward and not service_start_refusal)
device_pairing='--device-pairing' in sys.argv
play_mode_control='--play-mode-control' in sys.argv
assert not play_mode_control or (device_pairing and shared_wifi)
diagnostic_ready='--diagnostic-ready' in sys.argv
assert not diagnostic_ready or device_pairing
delayed_pairing_ready='--delayed-pairing-ready' in sys.argv
assert not delayed_pairing_ready or device_pairing
embedded_runtime='--embedded-runtime' in sys.argv
assert not embedded_runtime or device_pairing
assert not device_pairing or shared_wifi
assert not shared_wifi or (automatic_factory and owner_view_forward and '--real-owner-startup-refusal' not in sys.argv)
assert not owner_view_forward or automatic_factory
real_owner_refusal='--real-owner-startup-refusal' in sys.argv
assert not real_owner_refusal or (owner_view_forward and '--sleep-retirement' not in sys.argv)
real_owner_managed='--real-owner-managed' in sys.argv
assert not real_owner_managed or real_owner_refusal
formal_data_layout='--formal-data-layout' in sys.argv
assert not formal_data_layout or real_owner_managed
sleep_retirement='--sleep-retirement' in sys.argv
assert not exit_idle_progress or (shared_wifi and not sleep_retirement)
assert not sleep_retirement or automatic_factory
settings_factory='--settings-factory' in sys.argv or automatic_factory
settings_backend='--settings-backend' in sys.argv or settings_factory
native_page_chain='--native-page-chain' in sys.argv
assert not native_page_chain or (settings_backend and not settings_factory)
if settings_factory:reusable=True
rf_admission='--rf-admission' in sys.argv
assert not rf_admission or settings_backend
early_stop='--early-stop' in sys.argv
mode_switch='--mode-switch' in sys.argv
assert not mode_switch or (settings_backend and not early_stop)
assert not native_page_chain or not any((mode_switch,early_stop,rf_admission,bad_generation,bad_grants))
assert not early_stop or settings_backend
assert not settings_factory or not any((bad_generation,bad_grants,early_stop,mode_switch,rf_admission))
if settings_backend:managed_process=True
if managed_process:direct_delivery=True
if '--service-review' in sys.argv:
 if service_start_refusal:
  raise ValueError('A service build cannot replace the failure-injection fixture')
 _,service_artifact,service_report=reviewed_service(sys.argv[sys.argv.index('--service-review')+1])
elif service_start_refusal:
 fixture_flags=['-Wl,--wrap=xw_managed_client_bind_stock']
 if service_handoff_refusal:
  fixture_flags+=['-DWR_TEST_HANDOFF_REFUSAL','-Wl,--wrap=xnow_handoff_adopt_reader']
 service_artifact,service_report=build_service(out/'fixture-service',
  fixture_sources=['tools/fixtures/remote_bind_refusal.c'],fixture_flags=fixture_flags)
else:
 service_artifact,service_report=build_service(out/'service-build')
libs=stock_libraries(include_rt=True)
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK',
       '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin',
       '-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none']
startup=['runtime/store/start.c','runtime/store/start.S']
linked=[str(libs[n]) for n in ('librt.so.1','libpthread.so.0','libc.so.6','ld-linux.so.3')]
def compile(sources,target,extra=()):subprocess.run(['arm-linux-gnueabi-gcc',*flags,*extra,*sources,*startup,*linked,'-lgcc','-o',str(target)],cwd=ROOT,check=True)
owner=out/'fixture-owner/remote-rf-owner.arm';owner.parent.mkdir();owner_sources=['tools/fixtures/remote_chain_owner.c','runtime/apps/wireless-remote/control.c','runtime/apps/wireless-remote/link.c','runtime/apps/wireless-remote/status_auth.c','runtime/native/sha256.c','runtime/store/deadline.c']
owner_sources+=['runtime/apps/wireless-remote/mode_wire.c']
owner_flags=['-DWR_CHAIN_BROKER_MODEL','-DWR_CHAIN_MANUAL_STOP'] if settings_backend else []
if artwork_transfer:
 owner_flags+=['-DWR_CHAIN_ARTWORK','-I'+str(out)]
 owner_sources+=['runtime/apps/wireless-remote/artwork_wire.c','runtime/apps/wireless-remote/artwork_client.c']
if device_pairing:
 from pairing_crypto import inputs as pairing_crypto_inputs
 curve_sources,curve_flags=pairing_crypto_inputs()
 owner_sources+=curve_sources;owner_flags+=curve_flags
 owner_flags+=['-DWR_CHAIN_DEVICE_PAIRING']
 owner_sources+=['runtime/apps/wireless-remote/pairing_proof.c']
 owner_sources+=['runtime/apps/wireless-remote/run_profile.c']
if early_stop or service_start_refusal:owner_flags+=['-DWR_CHAIN_ALLOW_EMPTY_STOP']
if reusable:owner_flags+=['-DWR_CHAIN_DYNAMIC_SESSION']
if owner_view_forward:
 owner_flags+=['-DWR_CHAIN_OWNER_VIEW']
 owner_sources+=['runtime/apps/wireless-remote/owner_admission.c','runtime/platform/wireless/mode_client.c','runtime/platform/wireless/mode_channel.c','runtime/platform/wireless/mode_policy.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
if shared_wifi:owner_flags+=['-DWR_CHAIN_SHARED_WIFI']
if diagnostic_ready:owner_flags+=['-DWR_CHAIN_DIAGNOSTIC_READY']
if delayed_pairing_ready:owner_flags+=['-DWR_CHAIN_DELAYED_PAIRING_READY']
real_owner_report=None
if real_owner_refusal:
 sdk_output=out/'native-sdk'
 subprocess.run([sys.executable,str(ROOT/'runtime/platform/espnow/build_library.py'),
  '--output',str(sdk_output)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
 owner,real_owner_report=build_owner(legacy_radio=True, power_off_exit=True, mode_view_required=True,
  managed_session=real_owner_managed, window_seconds=None if real_owner_managed else 180,
  data_leaf='wireless-remote' if formal_data_layout else 'espnow-test', output=out/'real-owner-build',
  sdk_review=sdk_output/'sdk/build.json')
 owner_sources=[]
 libs['libcnmgr.so.1']=ROOT/'work/stock-resolver-probe/libcnmgr.so.1'
else:
 compile(owner_sources,owner,owner_flags)
 fixture_inputs=owner_sources+startup+[p.relative_to(ROOT).as_posix() for p in (ROOT/'runtime/apps/wireless-remote').glob('*.h')]
 fixture_report=dict(built=True,fixture_only=True,device_accessed=False,radio_started=False,
                     artifact=owner.relative_to(ROOT).as_posix(),bytes=owner.stat().st_size,
                     sha256=hashlib.sha256(owner.read_bytes()).hexdigest(),
                     source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in fixture_inputs})
 (owner.parent/'build.json').write_text(json.dumps(fixture_report,indent=2)+'\n',encoding='utf-8')
generation=1 if automatic_factory else 41 if settings_backend else 23
template_generation=40 if automatic_factory else generation-1 if reusable else generation
config=out/'config.bin';config.write_bytes(b'XWRUN001'+struct.pack('<QQ',template_generation,1234567)+bytes([2,1,2,3,4,5])+b'\0\0'+bytes(range(1,33))+bytes(range(16)))
review=dict(generation=template_generation,device_directory='/contents/HOMEBREW/data/wireless-remote/runtime' if formal_data_layout else '/contents/HOMEBREW/data/player-sdk-live-1/remote',files={})
if owner_view_forward:review['owner_mode_view_supported']=True
for name,path in [('service',service_artifact),('owner',owner),('config',config)]:review['files'][name]=dict(local=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
review_path=out/'review.private.json';review_path.write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')
supervisor,supervisor_report=build_supervisor(review=review_path,output=out/'supervisor-build',
 reusable_sessions=reusable,forward_owner_mode_view=owner_view_forward,device_pairing=device_pairing,
 embedded_runtime=embedded_runtime,play_mode_control=play_mode_control)
if play_mode_control:assert supervisor_report['play_mode_control'] is True
if device_pairing:
 assert set(supervisor_report['inputs'])=={'service','owner'}
 data=bytearray(config.read_bytes())
 data[:8]=b'XWRUN002'
 struct.pack_into('<Q',data,8,template_generation+4)
 data.extend(bytes(range(1,33)))
 config.write_bytes(data)
names=('client','managed','managed_rpc','rpc_wire','managed_channel','managed_control','managed_codec','managed_remote','managed_client','managed_clock','managed_host','session_offer','service_drain','deferred_prepare','startup_delivery')
server_sources=['runtime/platform/player/'+n+'.c' for n in names]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events','descriptor')]+['runtime/store/deadline.c','tools/fixtures/managed_host_external.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
server_flags=['-DXW_FIXTURE_STARTUP_PROBE']
if artwork_transfer:server_flags+=['-DXW_FIXTURE_ARTWORK','-I'+str(out)]
if managed_process:
 server_sources+=['runtime/apps/wireless-remote/supervisor_process.c']
 server_flags+=['-DXW_FIXTURE_MANAGED_PROCESS','-DWR_SUPERVISOR_PATH="/supervisor"']
if settings_backend:
 names=('client','managed','managed_rpc','managed_channel','managed_control','rpc_wire','player_broker','metadata_async','local_identity','service_drain','drain_completion','deferred_prepare','managed_host','session_offer','host_managed_service')
 server_sources=['runtime/platform/player/'+n+'.c' for n in names]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events','descriptor')]
 server_sources+=['runtime/apps/wireless-remote/settings_backend.c','runtime/apps/wireless-remote/native_page_bridge.c','runtime/apps/wireless-remote/supervisor_process.c','runtime/platform/wireless/mode_policy.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','tools/fixtures/settings_backend_chain.c']
if native_page_chain:
 server_sources=[p for p in server_sources if p!='tools/fixtures/settings_backend_chain.c']
 server_sources+=['tools/fixtures/native_page_backend_chain.c']
 server_sources+=['runtime/platform/sony-settings/native_page.c']
 server_flags+=['-DWR_NATIVE_PAGE_CHAIN']
if settings_factory:
 server_sources=[p for p in server_sources if p!='tools/fixtures/settings_backend_chain.c']
 server_sources+=['runtime/apps/wireless-remote/settings_factory.c','runtime/platform/player/wireless_host.c','runtime/platform/wireless/native_publisher.c','runtime/platform/wireless/mode_channel.c','tools/fixtures/settings_factory_chain.c']
 server_sources+=['runtime/apps/wireless-remote/owner_admission.c','runtime/platform/wireless/mode_client.c']
 server_flags+=['-DXW_PLAYER_NATIVE_RF']
if automatic_factory:
 server_sources+=['tools/fixtures/remote_idle_probe.c']
 (out/'remote_factory_profile.h').write_text('#define WR_REMOTE_SUPERVISOR_BYTES '+str(supervisor.stat().st_size)+'u\n'+('#define WR_REMOTE_OWNER_VIEW\n' if owner_view_forward else ''))
 server_flags+=['-DWR_SETTINGS_AUTO_TEST','-I'+str(out)]
if shared_wifi:server_flags+=['-DWR_SETTINGS_SHARED_WIFI','-DXW_PLAYER_SHARED_WIFI_ANALYSIS']
if exit_idle_progress:server_flags+=['-DWR_SETTINGS_EXIT_IDLE_PROGRESS']
if native_exit_bridge:
 server_flags+=['-DWR_SETTINGS_NATIVE_EXIT_BRIDGE','-I'+str(ROOT/'runtime/platform/player')]
 bridge_source=(ROOT/'runtime/platform/player/host_prepare_bridge.c').read_text(encoding='utf-8')
 target='uintptr_t)XW_STOCK_PREPARE_COORDINATOR_ADDRESS'
 assert bridge_source.count(target)==1
 modeled=bridge_source.replace(target,'uintptr_t)xw_test_factory_native_coordinator')
 assert modeled.replace('uintptr_t)xw_test_factory_native_coordinator',target)==bridge_source
 generated=out/'native-exit-bridge.c'
 generated.write_text('#include <stdint.h>\nextern int xw_test_factory_native_coordinator(uint32_t,uint32_t,uint32_t *);\n'+modeled,encoding='utf-8')
 server_sources+=[generated.relative_to(ROOT).as_posix()]
if native_worker_retirement:
 server_flags+=['-DWR_SETTINGS_NATIVE_WORKER']
 server_sources+=['runtime/platform/wireless/'+name+'.c' for name in ('native_delivery','native_offer','native_permission','native_rf_worker','native_bootstrap','native_boot','native_retirement','radio_modules')]
 server_sources+=['runtime/store/deadline.c','tools/fixtures/native_factory_radio.c']
if native_owner_wait:
 server_flags+=['-DWR_SETTINGS_NATIVE_OWNER_WAIT','-Wl,--wrap=xw_native_delivery_send_notice']
 server_sources+=['runtime/platform/player/owner_wait.c']
if application_handoff:
 server_flags+=['-DWR_SETTINGS_APPLICATION_HANDOFF']
 handoff_source=(ROOT/'runtime/platform/player/host_handoff_bridge.c').read_text(encoding='utf-8')
 replacements={'(uintptr_t)STOCK_CLIENT_GETTER_ADDRESS':'(uintptr_t)xw_test_application_client',
               '(uintptr_t)STOCK_PREPARE_COORDINATOR_ADDRESS':'(uintptr_t)xw_test_application_coordinator'}
 modeled=handoff_source
 for target,replacement in replacements.items():
  assert modeled.count(target)==(2 if 'CLIENT_GETTER' in target else 1)
  modeled=modeled.replace(target,replacement)
 restored=modeled
 for target,replacement in replacements.items():restored=restored.replace(replacement,target)
 assert restored==handoff_source
 generated=out/'application-handoff-bridge.c'
 generated.write_text('#include "factory_application_view.h"\n'+modeled,encoding='utf-8')
 server_sources+=[generated.relative_to(ROOT).as_posix(),'tools/fixtures/factory_application_view.c']
 server_flags+=['-I'+str(ROOT/'tools/fixtures')]
if revoked_exit_context:server_flags+=['-DWR_SETTINGS_REVOKED_EXIT_CONTEXT']
if service_start_refusal:server_flags+=['-DWR_SETTINGS_SERVICE_START_REFUSAL']
if device_pairing:
 server_flags+=['-DWR_SETTINGS_DEVICE_PAIRING','-DWR_PAIRING_PROCESS']
 server_sources+=curve_sources;server_flags+=curve_flags
 server_sources+=['runtime/platform/espnow/xnow_client.c','runtime/platform/espnow/xnow_handoff.c',
                  'runtime/apps/wireless-remote/pairing_proof.c','runtime/apps/wireless-remote/status_auth.c',
                  'runtime/apps/wireless-remote/link.c','runtime/apps/wireless-remote/run_profile.c','runtime/native/sha256.c']
if sleep_retirement:
 server_sources+=['runtime/platform/player/sleep_retirement.c','runtime/platform/player/sleep_host.c']
 server_flags+=['-DWR_SETTINGS_SLEEP_RETIREMENT']
if real_owner_refusal:server_flags+=['-DWR_REAL_OWNER_REFUSAL']
if early_stop:server_flags+=['-DWR_SETTINGS_EARLY_STOP']
if mode_switch:server_flags+=['-DWR_SETTINGS_MODE_SWITCH']
if rf_admission:server_flags+=['-DXW_PLAYER_NATIVE_RF','-DWR_SETTINGS_ADMISSION_TEST']
if reusable and settings_backend and not mode_switch and not early_stop:server_flags+=['-DWR_SETTINGS_RESTART']
server=out/'server.arm';compile(server_sources,server,server_flags)
init_flags=['-DXW_DIRECT_REMOTE'] if direct_delivery else []
if embedded_runtime:init_flags+=['-DXW_EMBEDDED_REMOTE']
if formal_data_layout:init_flags+=['-DXW_FORMAL_REMOTE_LAYOUT']
if bad_generation:init_flags+=['-DXW_DIRECT_BAD_GENERATION']
if bad_grants:init_flags+=['-DXW_DIRECT_BAD_GRANTS']
init=out/'init.arm';compile(['tools/fixtures/remote_chain_init.c'],init,init_flags)
markers=['REMOTE_DIRECT_REJECTION_PASS','PUBLIC_MANAGED_HOST_SERVER_PASS','REMOTE_CHAIN_CHILD_STATUS=0'] if bad_generation or bad_grants else ['REMOTE_CHAIN_OWNER_STARTED','REMOTE_SUPERVISOR_CHILDREN service=0 owner=0','REMOTE_SERVICE_RETIRED startup_failure=0','PUBLIC_MANAGED_HOST_SERVER_PASS','REMOTE_CHAIN_CHILD_STATUS=0']
markers.append('REMOTE_CONFIG_UNCHANGED')
if real_owner_refusal:
 markers=['REMOTE_RF_MODE_VIEW_AUTHORIZED','REMOTE_SUPERVISOR_CHILDREN service=1 owner=69','REMOTE_SUPERVISOR_START_REFUSAL_RETIRED','REMOTE_SERVICE_RETIRED startup_failure=1','FACTORY_START_REFUSAL_RETRY_PASS','PUBLIC_MANAGED_HOST_SERVER_PASS','REMOTE_CHAIN_CHILD_STATUS=0','REMOTE_CONFIG_UNCHANGED']
if shared_wifi:
 markers=['FACTORY_MISSING_PAIRING_RETIRED','REMOTE_CHAIN_MODE_VIEW_PASS','REMOTE_SUPERVISOR_CHILDREN service=1 owner=0','REMOTE_SUPERVISOR_CHANNEL_CHANGE_RETIRED','FACTORY_SHARED_WIFI_PASS','PUBLIC_MANAGED_HOST_SERVER_PASS','REMOTE_CHAIN_CHILD_STATUS=0','REMOTE_CONFIG_UNCHANGED']
if device_pairing:markers.append('REMOTE_PAIRING_OWNER_EXECUTED')
if artwork_transfer:markers.append('REMOTE_CHAIN_ARTWORK_PASS')
if service_start_refusal:
 markers=['REMOTE_HANDOFF_REFUSAL_FIXTURE' if service_handoff_refusal else 'REMOTE_BIND_REFUSAL_FIXTURE','REMOTE_SUPERVISOR_CHILDREN service=75 owner=0','FACTORY_START_REFUSAL_DRAIN_PASS','PUBLIC_MANAGED_HOST_SERVER_PASS','REMOTE_CHAIN_CHILD_STATUS=0','REMOTE_CONFIG_UNCHANGED']
report=run_guest(out,init,{'test':server,'supervisor':supervisor,'stage/service.arm':service_artifact,'stage/owner.arm':owner,'stage/config.bin':config},libs,
                 markers,timeout=75 if artwork_transfer else 25)
if native_page_chain:assert 'NATIVE_PAGE_BACKEND_CHAIN_PASS' in (out/'serial.log').read_text(errors='replace')
elif settings_backend and not real_owner_refusal:assert 'SETTINGS_BACKEND_CHAIN_PASS' in (out/'serial.log').read_text(errors='replace')
if reusable and native_page_chain:assert 'NATIVE_PAGE_GENERATION_STALE_PASS' in (out/'serial.log').read_text(errors='replace')
elif reusable and settings_backend and not mode_switch and not early_stop and not real_owner_refusal:assert 'SETTINGS_BACKEND_RESTART_PASS' in (out/'serial.log').read_text(errors='replace')
if settings_factory and not real_owner_refusal:assert 'SETTINGS_FACTORY_CHAIN_PASS' in (out/'serial.log').read_text(errors='replace')
if settings_factory and not real_owner_refusal:assert (out/'serial.log').read_text(errors='replace').count('FACTORY_OWNER_VIEW_PASS') >= (2 if sleep_retirement else 1)
if sleep_retirement:
 assert 'SLEEP_RETIREMENT_CHAIN_PASS' in (out/'serial.log').read_text(errors='replace')
 assert 'SLEEP_REMOTE_RESTART_PASS' in (out/'serial.log').read_text(errors='replace')
if owner_view_forward and not real_owner_refusal:assert (out/'serial.log').read_text(errors='replace').count('REMOTE_CHAIN_MODE_VIEW_PASS') >= (2 if service_start_refusal else 4 if sleep_retirement else 3)
if real_owner_refusal:
 serial=(out/'serial.log').read_text(errors='replace');assert 'REMOTE_RF_OWNER_STARTING' not in serial
 assert serial.count('REMOTE_SUPERVISOR_START_REFUSAL_RETIRED')>=2 and 'startup_failure=1' in serial
if rf_admission:assert 'SETTINGS_BACKEND_ADMISSION_PASS' in (out/'serial.log').read_text(errors='replace')
if bad_generation or bad_grants:
 assert 'REMOTE_SUPERVISOR_CHILDREN' not in (out/'serial.log').read_text(errors='replace')
 assert 'REMOTE_CHAIN_OWNER_STARTED' not in (out/'serial.log').read_text(errors='replace')
inputs=owner_sources+server_sources+['tools/fixtures/remote_chain_init.c','tools/test_remote_supervisor.py']
if artwork_transfer:inputs+=[artwork_header.relative_to(ROOT).as_posix(),'runtime/apps/wireless-remote/artwork_client.h','runtime/apps/wireless-remote/artwork_wire.h']
if service_start_refusal:inputs+=['tools/fixtures/remote_bind_refusal.c','runtime/apps/wireless-remote/startup_result.h']
if managed_process:inputs+=['runtime/apps/wireless-remote/supervisor_process.h']
if automatic_factory:inputs+=['runtime/platform/player/remote_auto.c','runtime/platform/player/remote_ready.h']
if exit_idle_progress:assert 'FACTORY_USB_DRAIN_IDLE_PASS' in (out/'serial.log').read_text(errors='replace')
if native_exit_bridge:
 assert 'FACTORY_NATIVE_EXIT_BRIDGE_PASS' in (out/'serial.log').read_text(errors='replace')
 inputs+=['runtime/platform/player/host_prepare_bridge.c','runtime/platform/player/host_prepare_bridge.h','runtime/platform/player/stock_prepare_view.h']
if native_worker_retirement:
 assert 'FACTORY_NATIVE_WORKER_RETIREMENT_PASS' in (out/'serial.log').read_text(errors='replace')
 inputs+=['tools/fixtures/native_factory_radio.h','runtime/store/deadline.h']
 inputs+=[p.relative_to(ROOT).as_posix() for p in (ROOT/'runtime/platform/wireless').glob('native*.h')]
if native_owner_wait:
 assert 'FACTORY_NATIVE_OWNER_WAIT_PASS' in (out/'serial.log').read_text(errors='replace')
 assert 'FACTORY_NATIVE_NOTICE_WAIT_PASS' in (out/'serial.log').read_text(errors='replace')
 inputs+=['runtime/platform/player/owner_wait.h']
if application_handoff:
 assert 'FACTORY_APPLICATION_WIFI_RETURN_PASS' in (out/'serial.log').read_text(errors='replace')
 inputs+=['runtime/platform/player/host_handoff_bridge.c','runtime/platform/player/host_handoff_bridge.h','tools/fixtures/factory_application_view.h']
if revoked_exit_context:assert 'FACTORY_REVOKED_EXIT_RETIRED_PASS' in (out/'serial.log').read_text(errors='replace')
if sleep_retirement:inputs+=['runtime/platform/player/sleep_retirement.h','runtime/platform/player/sleep_host.h']
if settings_factory:inputs+=['runtime/apps/wireless-remote/settings_factory.h','runtime/apps/wireless-remote/owner_admission.h','runtime/platform/player/wireless_host.h','runtime/platform/wireless/native_publisher.h','runtime/platform/wireless/mode_channel.h','runtime/platform/wireless/mode_client.h','runtime/platform/services/session.h']
if settings_backend:inputs+=['runtime/apps/wireless-remote/settings_backend.h','runtime/platform/wireless/mode.h','runtime/platform/wireless/mode_policy.h','runtime/platform/player/host_managed_service.h','tools/fixtures/player_host_managed_service.c','tools/fixtures/player_broker.c']
if settings_backend:inputs+=['runtime/platform/sony-settings/native_page.h','runtime/platform/sony-settings/bindings.h','runtime/apps/wireless-remote/native_page_bridge.h']
if native_page_chain:inputs=[p for p in inputs if p!='tools/fixtures/settings_backend_chain.c']
report.update(built=True,service_start_refusal=service_start_refusal,client_bind_failure_injected=service_start_refusal,native_page_chain=native_page_chain,shared_wifi_factory_chain=shared_wifi,artifact=supervisor.relative_to(ROOT).as_posix(),bytes=supervisor.stat().st_size,
              native_page_generation_refusal_checked=native_page_chain and reusable,
              sha256=supervisor_report['sha256'],original_libc_arm_entry_checks=True,
              actual_supervisor=True,actual_service=not (bad_generation or bad_grants),actual_player_host=True,radio_owner_modeled=not real_owner_refusal,player_backend_modeled=True,
              actual_real_owner=real_owner_refusal,real_owner_startup_refusal_checked=real_owner_refusal,
              real_owner_managed=real_owner_managed,
              formal_data_layout=formal_data_layout,
              direct_delivery=direct_delivery,reusable_sessions=reusable,runtime_generation=generation,template_generation=template_generation,
              managed_process_launcher=managed_process,
              actual_settings_backend=settings_backend,actual_settings_factory=settings_factory,foreign_generation_isolation_checked=settings_factory and not real_owner_refusal,cooperative_native_exit_checked=settings_factory and not real_owner_refusal,automatic_factory=automatic_factory,inactive_player_admission=rf_admission,
              factory_owner_view_checked=settings_factory,
              owner_view_forwarded=owner_view_forward,
              early_stop=early_stop,
              actual_sleep_retirement=sleep_retirement,native_sleep_ack_modeled=sleep_retirement,
              sleep_remote_restart_checked=sleep_retirement,native_recovery_evidence_modeled=sleep_retirement,
              system_mode_change=mode_switch,
              actual_mode_policy=settings_backend,mode_policy_evidence_modeled=settings_backend,
              rejects_bad_generation=bad_generation,rejects_bad_grants=bad_grants,
              device_accessed=False,source_hashes={**(real_owner_report['source_hashes'] if real_owner_report else {}),**service_report['source_hashes'],**supervisor_report['source_hashes'],**{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs}})
report['artwork_transfer']=artwork_transfer
report['native_exit_bridge_chain']=native_exit_bridge
report['native_worker_retirement']=native_worker_retirement
report['native_owner_wait']=native_owner_wait
report['application_handoff']=application_handoff
if application_handoff:
 report.setdefault('limits',[]).append('Actual command6/7 bridge drains the Remote/SDK chain, retains the exact native Wi-Fi lease and restarts a fresh Remote generation after a supplied APF return. Root/client state, getter, coordinator and physical RF are models; no original capture, display handoff or appproxy child launch executes.')
if native_worker_retirement:
 report.setdefault('limits',[]).append('Native bootstrap, SCM_RIGHTS offer, original-LinuxThreads worker identity, read-only mode IPC, TLS sealing and retirement notice run in the same service/SDK exit chain. Queue scheduling, boot/RF state and stock coordinator remain fixtures. No physical power-off or USB acceptance.')
if native_exit_bridge:
 report.setdefault('limits',[]).append('Actual exit interceptor, native tick, Settings factory, supervisor/service processes, SDK drain and mode policy run together. Root/image validation and native RF OFF evidence are fixtures; only the stock coordinator call target is replaced. No original finalizer or USB hardware executes.')
if artwork_transfer:report['artwork_payload_sha256']=hashlib.sha256(image_data).hexdigest()
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
assert report['passed'],(out/'serial.log').read_text(errors='replace')[-6000:]
print(json.dumps(report,indent=2))
