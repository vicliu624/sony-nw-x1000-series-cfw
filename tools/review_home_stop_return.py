"""Bind the same Home stop/launch/frontend/return evidence without hardware claims."""
from pathlib import Path
import json,hashlib,argparse,struct
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1]
paths=['sources/native-home-parent-ack-manager-close.json','sources/native-manager-home-inactive-exec.json','sources/native-home-stop-frontend-contract.json','sources/native-home-stop-proxy-exit.json','sources/native-home-stop-manager-return.json','sources/native-home-parent-frame-receiver.json','sources/native-return-provenance-tests.json']
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--wire-entry',action='store_true');parser.add_argument('--lookup-entry',action='store_true');parser.add_argument('--config-entry',action='store_true');parser.add_argument('--registry-entry',action='store_true');parser.add_argument('--state-entry',action='store_true');parser.add_argument('--actor-entry',action='store_true');parser.add_argument('--activation-entry',action='store_true');options=parser.parse_args()
if options.activation_entry:options.actor_entry=True
if options.actor_entry:options.state_entry=True
if options.state_entry:options.registry_entry=True
if options.registry_entry:options.config_entry=True
if options.config_entry:options.lookup_entry=True
if options.lookup_entry:options.wire_entry=True
if options.wire_entry:
 paths[:5]=['sources/native-home-parent-switch-client-ack-manager-close.json','sources/native-manager-home-wire-exec.json','sources/native-home-wire-frontend-contract.json','sources/native-home-wire-proxy-exit.json','sources/native-home-wire-manager-return.json']
if options.lookup_entry:
 paths[:5]=['sources/native-home-parent-lookup-client-switch-client-ack-manager-close.json','sources/native-manager-home-lookup-exec.json','sources/native-home-lookup-frontend-contract.json','sources/native-home-lookup-proxy-exit.json','sources/native-home-lookup-manager-return.json']
if options.config_entry:
 paths[1:5]=['sources/native-manager-home-config-exec.json','sources/native-home-config-frontend-contract.json','sources/native-home-config-proxy-exit.json','sources/native-home-config-manager-return.json']
if options.registry_entry:
 paths[1:5]=['sources/native-manager-home-registry-exec.json','sources/native-home-registry-frontend-contract.json','sources/native-home-registry-proxy-exit.json','sources/native-home-registry-manager-return.json']
if options.state_entry:paths[4]='sources/native-home-state-manager-return.json'
if options.actor_entry:
 paths[:6]=['sources/native-home-parent-lookup-frame-receiver.json','sources/native-manager-home-actor-exec.json','sources/native-home-actor-frontend-contract.json','sources/native-home-actor-proxy-exit.json','sources/native-home-actor-manager-return.json','sources/native-home-parent-lookup-frame-receiver.json']
if options.activation_entry:
 paths[:6]=['sources/native-home-parent-activation-route-frame-receiver.json','sources/native-manager-home-activation-exec.json','sources/native-home-activation-frontend-contract.json','sources/native-home-activation-proxy-exit.json','sources/native-home-activation-manager-return.json','sources/native-home-parent-activation-route-frame-receiver.json']
data={p:verify_report(ROOT,p) for p in paths};sha=lambda p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
home,launch,frontend,proxy,returned,recovery,negative=(data[p] for p in paths)
assert launch['inactive_confirmation_input']['sha256']==sha(paths[0])
if options.wire_entry:
 assert launch['home_switch_input']['sha256']==sha(paths[0])
 assert launch['home_switch_input']['words']==[1060,1 if options.lookup_entry else 0,1,6,55,0x30001,0,0]
 assert launch['inactive_confirmation_input']['packet']==[24,3 if options.activation_entry else 2 if options.lookup_entry else 1,1,1,55,1]
 if options.lookup_entry:
  assert launch['home_switch_input']['native_name_lookup_used']
  assert all(row['native_lookup_wire_requests'][0]['words']==[276,0,1,36,55] for row in home['cases'])
  assert all(row['native_lookup_wire_requests'][0]['parser']['native_parser_executed'] and row['native_lookup_wire_requests'][0]['parser']['record_count']==7 for row in home['cases'])
if options.config_entry:
 config=launch['native_launch_configuration'];assert config['native_parser_executed'] and config['record_count']==7 and len(config['entry_lookup'])==1
 assert config['entry_lookup'][0]['name']=='/contents/HOMEBREW/launcher/app'
 assert launch['cases'][0]['native_exec_commands']==[['appproxy','/contents/HOMEBREW/launcher/app','--native']]
if options.registry_entry:
 registry=launch['native_process_registry'];assert registry['record_count_after_activation']==2 and registry['home_preserved'] and registry['target_found']
 assert {'0x162b4','0x165fc','0x1633c','0x16510','0x16578','0x16594','0x110ac'}<={entry['procedure'] for entry in registry['events']}
 assert returned['native_return_registry'] and all(row['native_registry']['app_removed_by_native_list'] and row['native_registry']['daemon_preserved_by_native_lookup']==(not options.state_entry) and row['native_registry']['original_exists_callback']=='0xbd84' and row['native_registry']['count_after_walkman_activation']==(1 if options.state_entry else 2) and row['native_registry']['home_record_state']==2 for row in returned['cases'])
 if options.state_entry:
  assert returned['manager_state_input']['report_sha256']==sha(paths[1]) and returned['manager_state_input']['state']==launch['native_manager_state']
  assert returned['domain_preservation_checked'] and returned['activation_replayed'] is False
  assert all(row['native_activation_before_exit']['from_saved_manager_state'] and row['native_registry']['records_imported_from_launch'] for row in returned['cases'])
assert {'path':paths[1],'sha256':sha(paths[1])} in frontend['proxy_capture_inputs']
assert proxy['frontend_exit_input']['sha256']==sha(paths[2]) and proxy['registration_report_sha256']==sha(paths[1])
assert returned['proxy_exit_report_sha256']==sha(paths[3]) and returned['proxy_activation_report_sha256']==sha(paths[1])
assert returned['native_home_input']['sha256']==sha(paths[5])
if options.actor_entry:
 assert launch['home_switch_input']['combined_home_actor'] and sha(paths[0])==sha(paths[5])
 assert returned['native_home_input']['native_home_activation_packet']==[24,6 if options.activation_entry else 3,1,1,55,2]
 assert len(home['cases'])==4
 for row in home['cases']:
  if row['rebuild_cycle']==0:
   assert row['native_lookup_wire_requests'][0]['words'][1]==0 and row['native_switch_wire_requests'][0]['words'][1]==1
   assert row['native_manager_close']['apf_ack_requests']==[[24,3 if options.activation_entry else 2,1,1,55,1]]
  else:
   assert row['command7_activation_acks']==[[24,6 if options.activation_entry else 3,1,1,55,2]]
   shift=3*int(options.activation_entry)
   assert row['native_lookup_wire_requests'][-1]['words'][1]==4+shift and row['native_switch_wire_requests'][-1]['words'][1]==5+shift
   assert row['native_manager_close']['apf_ack_requests']==[[24,10 if options.activation_entry else 6,1,1,55,1]]
if options.activation_entry:
 assert home['native_activation_route'] and launch['home_switch_input']['native_activation_route']
 assert returned['returned_manager_state']['current_app']==1 and returned['returned_manager_state']['home_record_state']==2
 for row in home['cases']:
  stop=row['native_manager_close']['native_stop_route']
  assert stop['callback_entry']=='0xeb9c' and stop['callback_invoked_by_harness'] is False
  assert stop['native_receiver']=='0x26551c' and stop['native_registration'] is True and stop['returned_to_receive'] is True
  assert stop['events']==[[0x420024,0,0,0],[0x430113,0,6,0],[0x420032,0,0x683348,0]]
  assert len(stop['coordinator_calls'])==1 and stop['coordinator_calls'][0][:2]==[0x613e60,6]
  assert len(stop['module_calls'])==9 and stop['pending_registered']==[[0x68000900,0x206]] and stop['root_context_retained'] is True
  assert stop['snapshot_mode_field_fixture']==0 and stop['snapshot_converted_times']==[[985,0]]
  assert stop['snapshot_native_gate_client_states']==[2] and '0xb06e0' not in stop['snapshot_service_fixtures']
  consumer=stop['consumer_initialization'];assert consumer['constructor']=='0x6dec0' and consumer['context']=='0x683328'
  assert consumer['constructed_before_first_home'] is True and consumer['context_preserved'] is True and consumer['context_byte13']==11
  assert len(stop['snapshot_submissions_virtual'])==1 and len(bytes.fromhex(stop['snapshot_submissions_virtual'][0]))==108
  assert stop['snapshot_apf_transport_executed'] is True
  snapshots=stop['snapshot_wire_requests'];assert len(snapshots)==row['rebuild_cycle']+1
  assert [s['words'][1] for s in snapshots]==([2] if row['rebuild_cycle']==0 else [2,9])
  assert snapshots[-1]['manager']['used_slots']==row['rebuild_cycle']+1
  if row['rebuild_cycle']==1:
   route=row['native_activation_route'];init=route['root_initialization'];assert init['constructor']=='0x714c4' and init['initial']==[1,1] and init['after_notifications']==[2,1] and init['context_byte13']==5 and init['notification_slots_fixture']==list(range(6))
   receiver=route['native_receiver'];assert receiver['entry']=='0x26551c' and receiver['callback']=='0xeaa0' and receiver['callback_invoked_by_harness'] is False
   arguments=route['native_argument_query_requests'];assert len(arguments)==1 and arguments[0]['words']==[20,4,1,35,55]
   argv_reply=bytes.fromhex(arguments[0]['reply_hex']);assert len(argv_reply)==1044 and list(struct.unpack('<5I',argv_reply[:20]))==[1044,4,35,0,0]
   battery=route['native_battery_query_requests'];assert len(battery)==1 and battery[0]['words']==[20,5,1,7,55]
   assert list(struct.unpack('<6I',bytes.fromhex(battery[0]['reply_hex'])))==[24,5,7,0,1,0]
   assert receiver['notification_fixture']==[20,0,5,0,0] and receiver['returned_to_receive'] and receiver['client_state_before_confirmation']==1
   assert init['constructed_before_first_home'] is True and init['constructed_at_recovery_boundary'] is False
   assert init['preserved_until_recovery_checked'] is True and len(init['context_sha256_before_home_and_recovery'])==64
   assert route['events']==[[0x420011,0,1,0],[0x420023,0,0,0],[0x20303,0,1,0],[0x580101,0,1,0]]
   assert len(route['coordinator_calls'])==1 and route['coordinator_calls'][0][:2]==[0x613e60,7]
   assert len(route['module_calls'])==9 and route['pending_registered']==[[0x68000900,0x207]]
   assert route['delivery_order']==[0x420011,0x420023,0x20303,0x580101,0x20670,0x20671,0x420034,0x410009]
assert frontend['sha256']=='b01a35198ef0c7be01a08d4db2f619b2cd93993543b91715fa30d09e9fe61615'
cases=[r for r in frontend['cases'] if 'captured_argv' in r];assert len(cases)==(1 if options.wire_entry else 2) and all(r['exit']==0 and r['all_handles_closed'] and r['maps']==r['unmaps'] for r in cases)
assert proxy['self_event_shutdown_not_manager_op3'] and not proxy['quit_wire_to_manager_op3_verified'] and all(r['quit_after_reaped_child'] for r in proxy['cases'])
assert returned['Sony_return_validated'] is False and all(r['walkman_confirmation']['current_app']==1 and r['walkman_confirmation']['activation_from_native_home'] for r in returned['cases'])
report={'all_bounded_checks_passed':True,'physical_device_access':False,'generator_source':'tools/review_home_stop_return.py','generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'source_hashes':{p:sha(p) for p in paths},'same_launch_provenance_checked':True,'candidate_frontend_bound':True,'native_cleanup_ack_to_launch':True,'proxy_reap_before_shutdown':True,'native_recovery_packet_accepted':True,'hardware_qualified':False,'remaining':['Actual original kernel IPC, fork/wait/signal scheduling and registration delivery.','Real framebuffer/touch completion, user filesystem and USB unmount/export.','Boot/current-app/registry state and startup state1 remain supplied fixtures; no full firmware boot.'],'limits':['Separate emulators connected at exact captured message/argv/status bytes.','No assertion that physical Sony resources were released or that the player actually resumed.']}
report['native_switch_wire_entry']=options.wire_entry
report['native_name_lookup_entry']=options.lookup_entry
report['same_instance_configuration_parse_and_lookup']=options.lookup_entry
report['launch_entry_from_native_parsed_table']=options.config_entry
report['first_launch_registry_native']=options.registry_entry
report['return_registry_native']=options.registry_entry
report['saved_launch_state_continued']=options.state_entry
report['same_home_actor_client_state']=options.actor_entry
report['activation_callback_root_coordinator_executed']=options.activation_entry
if options.state_entry:
 report['remaining'].append('Activation callback invoked at declared boundary; Root2/1, other module objects/services, GUI-worker scheduling and IPC supplied. No APF receiver or kernel threads.' if options.activation_entry else 'Model RAM/module data imported at function boundaries, not CPU/thread context; I/O/service callbacks rebound. Home command7/event scheduling and IPC remain supplied.' if options.actor_entry else 'Model RAM and module writable regions imported at function boundaries, not CPU/thread context. I/O readiness/service callbacks are rebound; Home recovery client is a separate replay.')
elif options.registry_entry:report['remaining'].append('Return manager is a separate emulator; initial Home presence/PID, missing-Home launch/insertion and startup state1 remain supplied fixtures.')
(ROOT/('sources/native-home-activation-return-summary.json' if options.activation_entry else 'sources/native-home-actor-return-summary.json' if options.actor_entry else 'sources/native-home-state-return-summary.json' if options.state_entry else 'sources/native-home-registry-return-summary.json' if options.registry_entry else 'sources/native-home-config-return-summary.json' if options.config_entry else 'sources/native-home-lookup-return-summary.json' if options.lookup_entry else 'sources/native-home-wire-return-summary.json' if options.wire_entry else 'sources/native-home-stop-return-summary.json')).write_text(json.dumps(report,indent=2)+'\n');print('Same-provenance Home stop -> frontend -> original proxy/manager return summary passed; hardware unqualified.')
