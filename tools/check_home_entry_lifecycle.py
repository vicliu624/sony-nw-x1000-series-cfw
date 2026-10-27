"""Reproduce seven bounded Home-entry lifecycle profiles on prepared local inputs.
Never execute physical-device mode or create firmware; logs remain under work/.
"""
from pathlib import Path
import os,sys,subprocess,json,hashlib
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];version=(ROOT/'VERSION').read_text().strip();baseline=ROOT/'work'/('integration-'+version);manifest=json.loads((baseline/'manifest.json').read_text())
protected=[ROOT/'VERSION',baseline/'manifest.json']+[baseline/item['path'] for item in manifest['files']]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for item in manifest['files']:assert sha(baseline/item['path'])==item['sha256']
before={str(p.relative_to(ROOT)):sha(p) for p in protected}
work=ROOT/'work/home-entry-lifecycle-suite';work.mkdir(exist_ok=True);runs=[]
environment=dict(os.environ,HB_FRONTEND_BINARY=str(baseline/'external/HOMEBREW/launcher/app'))
def run(arguments):
 result=subprocess.run([sys.executable,*arguments],cwd=ROOT,env=environment,capture_output=True,text=True,timeout=180)
 log=work/(f'{len(runs):02d}-'+Path(arguments[0]).stem+'.log');log.write_text(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError(str(arguments)+' failed: '+result.stderr[-4000:])
 runs.append({'command':arguments,'log':str(log.relative_to(ROOT))});print(len(runs),arguments[0],'passed',flush=True)
for command in [ ['tools/check_homebrew_lookup_service.py'],['tools/check_home_parent.py','--ack-manager-close'],['tools/check_home_parent.py','--native-switch-client'],['tools/check_home_parent.py','--native-name-lookup'],['tools/check_home_parent.py','--native-frame-receiver'],['tools/check_home_parent.py','--native-name-lookup','--native-frame-receiver'],['tools/check_home_parent.py','--native-activation-route'],['tools/check_manager_change_notification.py','--ack-registered','--wrong-app-ack'],['tools/check_manager_change_notification.py','--ack-registered'],['tools/check_proxy_manager_return.py','--native-registry'],['tools/check_proxy_manager_return.py','--home-confirmation-report','sources/native-home-parent-frame-receiver.json'],['tools/check_manager_change_notification.py','--inactive-confirmation-report','sources/native-home-parent-ack-manager-close.json'] ]:run(command)
profiles=[('stop','sources/native-home-parent-ack-manager-close.json','native-manager-home-inactive-exec.json',None),('wire','sources/native-home-parent-switch-client-ack-manager-close.json','native-manager-home-wire-exec.json','--wire-entry'),('lookup','sources/native-home-parent-lookup-client-switch-client-ack-manager-close.json','native-manager-home-lookup-exec.json','--lookup-entry'),('config','sources/native-home-parent-lookup-client-switch-client-ack-manager-close.json','native-manager-home-config-exec.json','--config-entry'),('registry','sources/native-home-parent-lookup-client-switch-client-ack-manager-close.json','native-manager-home-registry-exec.json','--registry-entry'),('actor','sources/native-home-parent-lookup-frame-receiver.json','native-manager-home-actor-exec.json','--actor-entry'),('activation','sources/native-home-parent-activation-route-frame-receiver.json','native-manager-home-activation-exec.json','--activation-entry')]
for profile,home,launch,review in profiles:
 arguments=['tools/check_manager_change_notification.py']+(['--inactive-confirmation-report',home,'--capture-frontend-exec'] if profile=='stop' else ['--home-switch-report',home]+(['--native-process-registry','--save-manager-state'] if profile in ('registry','actor','activation') else ['--native-launch-config'] if profile=='config' else ['--capture-frontend-exec']))
 run(arguments)
 run(['tools/test_native_adapter.py','--proxy-exec-report','sources/'+launch,'--report',f'sources/native-home-{profile}-frontend-contract.json'])
 run(['tools/check_proxy_stop_order.py','--frontend-exit-report',f'sources/native-home-{profile}-frontend-contract.json','--registration-report','sources/'+launch,'--report',f'sources/native-home-{profile}-proxy-exit.json'])
 run(['tools/check_proxy_manager_return.py','--proxy-exit-report',f'sources/native-home-{profile}-proxy-exit.json','--launch-report','sources/'+launch,'--home-confirmation-report',home if profile in ('actor','activation') else 'sources/native-home-parent-frame-receiver.json','--report',f'sources/native-home-{profile}-manager-return.json']+(['--manager-state-report','sources/'+launch] if profile in ('actor','activation') else ['--native-return-registry'] if profile=='registry' else [])+(['--save-return-state'] if profile=='activation' else []))
run(['tools/check_proxy_manager_return.py','--proxy-exit-report','sources/native-home-registry-proxy-exit.json','--launch-report','sources/native-manager-home-registry-exec.json','--home-confirmation-report','sources/native-home-parent-frame-receiver.json','--manager-state-report','sources/native-manager-home-registry-exec.json','--report','sources/native-home-state-manager-return.json'])
run(['tools/test_return_provenance.py'])
for profile,home,launch,review in profiles:run(['tools/review_home_stop_return.py']+([review] if review else []))
run(['tools/review_home_stop_return.py','--state-entry'])
run(['tools/check_root_deactivation_state.py'])
run(['tools/check_root_startup_transition.py'])
run(['tools/check_stop_event_consumer.py'])
run(['tools/check_snapshot_apf_request.py'])
run(['tools/check_snapshot_manager_request.py'])
run(['tools/check_alarm_persistence.py'])
run(['tools/check_alarm_record_delete.py'])
run(['tools/check_alarm_native_pool.py'])
run(['tools/check_snapshot_native_roundtrip.py'])
run(['tools/check_manager_stop_frame.py'])
run(['tools/check_spider_stop_receiver.py'])
run(['tools/check_saved_manager_arguments.py'])
run(['tools/check_manager_second_entry.py'])
run(['tools/test_native_adapter.py','--second-entry-report','sources/native-manager-second-entry.json','--report','sources/native-second-entry-frontend-contract.json'])
run(['tools/check_proxy_stop_order.py','--second-entry','--registration-report','sources/native-manager-second-entry.json','--frontend-exit-report','sources/native-second-entry-frontend-contract.json','--report','sources/native-second-entry-proxy-exit.json'])
run(['tools/check_proxy_manager_return.py','--proxy-exit-report','sources/native-second-entry-proxy-exit.json','--launch-report','sources/native-manager-second-entry.json','--manager-state-report','sources/native-manager-second-entry.json','--report','sources/native-second-entry-manager-reap.json','--stop-before-walkman-confirmation'])
run(['tools/check_home_parent.py','--three-home-cycles'])
run(['tools/check_proxy_manager_return.py','--proxy-exit-report','sources/native-second-entry-proxy-exit.json','--launch-report','sources/native-manager-second-entry.json','--manager-state-report','sources/native-manager-second-entry.json','--home-confirmation-report','sources/native-home-parent-activation-route-frame-receiver-three-cycles.json','--home-confirmation-cycle','2','--report','sources/native-second-entry-manager-return.json'])
run(['tools/check_proxy_port_close.py'])
run(['tools/check_manager_port_cleanup.py'])
run(['tools/check_manager_change_notification.py','--home-switch-report','sources/native-home-parent-activation-route-frame-receiver.json','--native-ipc-service'])
run(['tools/test_native_adapter.py','--proxy-exec-report','sources/native-manager-native-ipc-exec.json','--report','sources/native-ipc-frontend-contract.json'])
run(['tools/check_proxy_stop_order.py','--registration-report','sources/native-manager-native-ipc-exec.json','--frontend-exit-report','sources/native-ipc-frontend-contract.json','--report','sources/native-ipc-proxy-exit.json'])
run(['tools/check_proxy_manager_return.py','--proxy-exit-report','sources/native-ipc-proxy-exit.json','--launch-report','sources/native-manager-native-ipc-exec.json','--manager-state-report','sources/native-manager-native-ipc-exec.json','--home-confirmation-report','sources/native-home-parent-activation-route-frame-receiver.json','--report','sources/native-ipc-manager-return.json','--native-ipc-exit-cleanup','--save-return-state'])
run(['tools/check_saved_manager_arguments.py','--return-report','sources/native-ipc-manager-return.json','--report','sources/native-ipc-saved-manager-arguments.json'])
run(['tools/check_manager_second_entry.py','--native-ipc'])
run(['tools/test_native_adapter.py','--second-entry-report','sources/native-manager-native-ipc-second-entry.json','--report','sources/native-ipc-second-frontend-contract.json'])
run(['tools/check_proxy_stop_order.py','--second-entry','--registration-report','sources/native-manager-native-ipc-second-entry.json','--frontend-exit-report','sources/native-ipc-second-frontend-contract.json','--report','sources/native-ipc-second-proxy-exit.json'])
run(['tools/check_proxy_manager_return.py','--proxy-exit-report','sources/native-ipc-second-proxy-exit.json','--launch-report','sources/native-manager-native-ipc-second-entry.json','--manager-state-report','sources/native-manager-native-ipc-second-entry.json','--home-confirmation-report','sources/native-home-parent-activation-route-frame-receiver-three-cycles.json','--home-confirmation-cycle','2','--report','sources/native-ipc-second-manager-return.json','--native-ipc-exit-cleanup'])
run(['tools/check_manager_stop_frame.py','--activation-return-report','sources/native-ipc-second-manager-return.json'])
run(['tools/check_home_parent.py','--activation-frame-report','sources/native-manager-return-frame.json'])
run(['tools/check_home_parent.py','--three-home-cycles','--activation-frame-report','sources/native-manager-return-frame.json'])
run(['tools/check_proxy_manager_return.py','--proxy-exit-report','sources/native-ipc-second-proxy-exit.json','--launch-report','sources/native-manager-native-ipc-second-entry.json','--manager-state-report','sources/native-manager-native-ipc-second-entry.json','--home-confirmation-report','sources/native-home-parent-activation-route-frame-receiver-three-cycles-captured-activation.json','--home-confirmation-cycle','2','--report','sources/native-ipc-captured-home-manager-return.json','--native-ipc-exit-cleanup'])
run(['tools/check_home_ipc_registration.py'])
run(['tools/check_home_client_registration.py'])
run(['tools/check_home_ipc_registration.py','--client-request-report','sources/native-home-client-registration-request.json'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--receive-registration-events'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--native-event-lookup'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--registered-manager-lookup'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--native-event-services'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--dispatch-root-events'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--execute-coordinator'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--native-gui-submit'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--consume-gui-queue'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--run-gui-worker'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--complete-gui-token'])
run(['tools/check_home_client_registration.py','--reply-report','sources/native-home-ipc-client-registration.json','--acknowledge-activation'])
run(['tools/check_main_native_constructor.py'])
run(['tools/check_main_native_constructor.py','--execute-first-activation'])
run(['tools/check_usb_state_query.py'])
assert before=={str(p.relative_to(ROOT)):sha(p) for p in protected}
reports=[f'sources/native-home-{profile}-return-summary.json' for profile,_,_,_ in profiles]+['sources/native-home-state-return-summary.json']
sources=sorted({arguments['command'][0] for arguments in runs})+['tools/native_lookup_fixture.py']+reports+['sources/native-root-deactivation-state.json','sources/native-root-startup-transition.json','sources/native-stop-event-consumer.json']
sources+=['sources/native-snapshot-apf-request.json','sources/native-snapshot-manager-request.json','sources/native-alarm-persistence.json','sources/native-alarm-record-delete.json','sources/native-alarm-native-pool.json']
sources+=['sources/native-spider-stop-receiver.json']
sources+=['sources/native-manager-stop-frame.json']
sources+=['tools/native_alarm_fixture.py','sources/native-snapshot-native-roundtrip.json','sources/native-saved-manager-arguments.json']
sources+=['sources/native-manager-second-entry.json']
sources+=['sources/native-second-entry-frontend-contract.json']
sources+=['sources/native-second-entry-proxy-exit.json']
sources+=['sources/native-second-entry-manager-reap.json']
sources+=['sources/native-home-parent-activation-route-frame-receiver-three-cycles.json','sources/native-second-entry-manager-return.json']
sources+=['sources/native-proxy-port-close.json','sources/native-manager-port-cleanup.json']
sources+=['sources/native-manager-native-ipc-exec.json','sources/native-ipc-frontend-contract.json','sources/native-ipc-proxy-exit.json','sources/native-ipc-manager-return.json','sources/native-ipc-saved-manager-arguments.json']
sources+=['sources/native-manager-native-ipc-second-entry.json','sources/native-ipc-second-frontend-contract.json','sources/native-ipc-second-proxy-exit.json','sources/native-ipc-second-manager-return.json']
sources+=['sources/native-manager-return-frame.json','sources/native-home-parent-activation-route-frame-receiver-captured-activation.json']
sources+=['sources/native-home-parent-activation-route-frame-receiver-three-cycles-captured-activation.json','sources/native-ipc-captured-home-manager-return.json']
sources+=['sources/native-home-ipc-registration.json']
sources+=['sources/native-home-client-registration-request.json','sources/native-home-ipc-client-registration.json']
sources+=['sources/native-home-client-registration-reply.json']
sources+=['sources/native-home-client-registration-events.json']
sources+=['sources/native-home-client-registration-native-lookup.json']
sources+=['sources/native-home-client-registration-manager-lookup.json']
sources+=['sources/native-home-client-registration-services.json']
sources+=['sources/native-home-client-registration-root.json']
sources+=['sources/native-home-client-registration-coordinator.json']
sources+=['sources/native-home-client-registration-gui-submit.json']
sources+=['sources/native-home-client-registration-gui-queue.json']
sources+=['sources/native-home-client-registration-gui-worker.json']
sources+=['sources/native-home-client-registration-gui-completion.json']
sources+=['sources/native-home-client-registration-active.json']
sources+=['sources/native-main-constructor.json']
sources+=['sources/native-main-first-activation.json']
sources+=['sources/native-usb-state-query.json']
report={'all_bounded_checks_passed':True,'physical_device_access':False,'version':version,'runs':runs,'profiles':[p[0] for p in profiles],'protected_candidate_unchanged':True,'saved_state_continuation_checked':True,'protected_files':len(protected),'generator_source':'tools/check_home_entry_lifecycle.py','generator_sha256':sha(Path(__file__)),'source_hashes':{p:sha(ROOT/p) for p in sources},'hardware_qualified':False,'firmware_package_created':False,'limits':['Prepared local inputs required; this is not a clean firmware build or full kernel boot.','Separate emulators, virtual services and initial states; exact captured bytes join stages.','No physical device, real IPC scheduling, display/storage/Wi-Fi qualification.']}
(ROOT/'sources/native-home-entry-lifecycle-suite.json').write_text(json.dumps(report,indent=2)+'\n');print('Seven bounded lifecycle profiles passed; protected candidate unchanged; hardware unqualified.')
