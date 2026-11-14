"""Decode a copied X1060 pairing trace without accessing the device."""
import argparse
import json
from read_parent_entry_trace import decode
from review_managed_remote_profile import private

HEADER = b'X1000-REMOTE-PAIRING-TRACE-1'.ljust(32, b'\0')
SEED = HEADER.ljust(2048, b'\0')
SLOTS = 31
SETTINGS_RESULT = 28
CHILD_RESULT = 29
STAGES = {
    1: 'pairing-confirmed',
    2: 'binding-lookup-completed',
    3: 'discovery-start-returned',
    4: 'listener-ready',
    5: 'invitation-accepted',
    6: 'factory-tick-failed',
    7: 'radio-owner-retirement',
    8: 'initial-receive-queue-sample',
    9: 'later-receive-queue-activity',
    10: 'initial-chip-receive-sample',
    11: 'later-chip-receive-activity',
    12: 'tuner-readback-status',
    13: 'tuner-before-retune',
    14: 'tuner-after-retune',
    15: 'listener-diagnostic-baselines',
    16: 'receive-counters-at-retirement',
    17: 'remote-runtime-starting',
    18: 'remote-service-ready',
    19: 'remote-runtime-retirement-or-error',
    20: 'remote-native-context-became-inactive',
    21: 'remote-original-sleep-preparation',
    22: 'remote-gui-idle-timeout-bounded',
    23: 'remote-supervisor-exit-detail',
    24: 'remote-application-failure-origin',
    25: 'remote-service-start-refusal',
    26: 'remote-receive-and-link-retirement-summary',
    27: 'remote-packet-backend-start-failure',
    SETTINGS_RESULT: 'latest-settings-start-result',
    CHILD_RESULT: 'latest-start-child-detail',
}
SETTINGS_STAGES = ('none', 'host-admission', 'wireless-mode', 'prepare-generation',
                   'spawn-supervisor', 'offer-player', 'attach-dependencies',
                   'offer-accepted', 'child-exit', 'ready')
PACKET_OPERATIONS = {1: 'enable-frm1', 2: 'enable-bulk'}
SERVICE_OPERATIONS = {1: 'retirement-channel', 2: 'radio-client', 3: 'player-hello',
                      4: 'sender', 5: 'worker', 6: 'player-command-negotiation'}


def signed(word):
    return word if word < 2**31 else word - 2**32


def attempt_identity(words):
    serial, generation, process, build = (
        low | high << 32 for low, high in zip(words[::2], words[1::2])
    )
    return dict(request_serial=serial, generation=generation or None,
                player_process=f'{process:016x}', player_build=f'{build:016x}')
OWNER_STARTUP_FAILURES = {
    101: 'mode-view-open',
    102: 'root-storage-or-radio-preflight',
    103: 'native-manager-ipc-preflight',
    104: 'stored-keys',
    105: 'mode-view-admission',
    106: 'owner-gate',
    107: 'controller-init',
    108: 'command-stream-open',
    109: 'owner-runtime-init',
}
CONTROLLER_ACTIONS = (
    'none', 'preflight', 'manager-acquire', 'manager-inspect', 'disconnect',
    'unload', 'load-candidate', 'wake', 'initialize', 'verify-candidate',
    'configure', 'restore-unload', 'load-stock', 'restore-wake',
    'restore-initialize', 'verify-stock', 'reconnect', 'manager-release',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', help='Trace copied to the local work directory')
    parser.add_argument('--before', help='Local copy taken before a single test attempt')
    args = parser.parse_args()
    data = private(args.trace).read_bytes()
    result = decode(SEED, data, prefix=HEADER, names=STAGES, slots=SLOTS)
    result['limits'] = [
        'The latest Settings result and child detail carry a build, player process, request and generation identity.',
        'Legacy slots cannot be attributed to the latest request.',
        'An empty or unchanged slot can also mean refused storage, an occupied slot or an interrupted write.',
        'New records describe writes between the two copies. They do not independently identify a start request.',
    ]
    latest = next((row for row in result['records'] if row['stage'] == SETTINGS_RESULT), None)
    result['latest_settings_start'] = None
    result['latest_child_detail'] = None
    result['attempt_identity_present'] = False
    if latest:
        result['records'].remove(latest)
        code, stage, reaped, status, *identity = latest['payload']
        identity = attempt_identity(identity)
        if (latest['sequence'] != 1 or not 1 <= stage < len(SETTINGS_STAGES) or
                reaped not in (0, 1) or not identity['request_serial'] or
                not int(identity['player_process'], 16) or not int(identity['player_build'], 16)):
            result['integrity_valid'] = False
            result['invalid_slots'].append(dict(slot=SETTINGS_RESULT, reason='settings-result-fields'))
        else:
            result['attempt_identity_present'] = True
            result['latest_settings_start'] = dict(
                operation=SETTINGS_STAGES[stage], result=signed(code), **identity, child_reaped=bool(reaped),
                child_wait_status=status if reaped else None)
    child = next((row for row in result['records'] if row['stage'] == CHILD_RESULT), None)
    if child:
        result['records'].remove(child)
        identity = attempt_identity(child['payload'][:8])
        packet, packet_code, service, service_code = child['payload'][8:]
        if (child['sequence'] != 1 or not identity['request_serial'] or not identity['generation'] or
                not int(identity['player_process'], 16) or not int(identity['player_build'], 16) or
                packet not in (0, *PACKET_OPERATIONS) or bool(packet) != bool(packet_code) or
                service not in (0, *SERVICE_OPERATIONS)):
            result['integrity_valid'] = False
            result['invalid_slots'].append(dict(slot=CHILD_RESULT, reason='child-result-fields'))
        else:
            current = result['latest_settings_start']
            if current and current['child_reaped'] and all(current[key] == value for key, value in identity.items()):
                result['latest_child_detail'] = dict(
                    packet_backend=dict(operation=PACKET_OPERATIONS[packet], result=signed(packet_code))
                    if packet else None,
                    service_refusal=dict(operation=SERVICE_OPERATIONS[service], result=signed(service_code))
                    if service else None)
    if args.before is not None:
        before = private(args.before).read_bytes()
        baseline = decode(SEED, before, prefix=HEADER, names=STAGES, slots=SLOTS)
        changes = {}
        for slot in range(1, SLOTS + 1):
            start = 32 + (slot - 1) * 64
            previous = before[start:start + 64]
            current = data[start:start + 64]
            if previous != current:
                if slot == SETTINGS_RESULT and result['attempt_identity_present']:
                    changes[slot] = 'settings-result-updated'
                    continue
                if slot == CHILD_RESULT and result['latest_child_detail'] is not None:
                    changes[slot] = 'child-detail-updated'
                    continue
                changes[slot] = 'changed-occupied' if any(previous) else 'new'
        changed_occupied_slots = [slot for slot, change in changes.items() if change == 'changed-occupied']
        append_only = baseline['integrity_valid'] and result['integrity_valid'] and not changed_occupied_slots
        for row in result['records']:
            row['since_before'] = changes.get(row['stage'], 'unchanged')
        result['comparison'] = dict(append_only=append_only,
                                    baseline_invalid_slots=baseline['invalid_slots'],
                                    changed_occupied_slots=changed_occupied_slots,
                                    latest_settings_start_changed=SETTINGS_RESULT in changes,
                                    latest_child_detail_changed=CHILD_RESULT in changes,
                                    new_committed_slots=[slot for slot, change in changes.items()
                                                         if append_only and change == 'new'])
    for row in result['records']:
        raw, binding, phase, channel, mode, fault, *state = row.pop('payload')
        status = signed(raw)
        row.update(result=status, binding_result=binding, pairing_phase=phase,
                   channel=channel, radio_mode=mode, fault_latched=bool(fault))
        if row['stage'] in (17,18,20,21):
            row['runtime_context']=dict(zip(('main_state','root_command','client_state','backend_phase','backend_error','child_wait_status'),state))
        if row['stage']==19:
            row['retirement_context']=state
        if row['stage']==22:
            row['original_gui_idle_us'],row['remote_gui_idle_us']=state[:2]
        if row['stage']==23:
            row['exit_detail']=dict(zip(('service_exit','owner_exit','application_error','worker_reason','worker_error','player_close_error'),map(signed,state)))
        if row['stage']==24:
            row['failure_origin']={1:'storage-guard-or-endpoint',2:'endpoint-prepare',3:'owner-stream',4:'transmit-poll',5:'receive-security'}.get(state[0],'unknown')
            if state[0] in (2,5) and status==-21:row['failure_domain']='encrypted-counter-storage'
        if row['stage']==25:
            row['startup_stage']=SERVICE_OPERATIONS.get(state[0],'unknown')
            row['player_capability_closed']=state[1]==1
            row['initial_hello_ms']=None if state[2]==0xffffffff else state[2]
        if row['stage']==26:
            row['radio_summary']=dict(zip(('decoded','authentication_rejected','replay_rejected',
                'negotiation_frames','negotiated_key_installs','shared_wake_unrestored'),state))
        if row['stage']==27:
            row['operation']=PACKET_OPERATIONS.get(state[0],'unknown')
            row['failure_domain']='xnow-transport'
        if row['stage'] == 7 and status in OWNER_STARTUP_FAILURES:
            row['owner_startup_failure'] = OWNER_STARTUP_FAILURES[status]
        if row['stage'] == 7 and raw & 0xf0000000 == 0x50000000:
            row['owner_runtime_error'] = int.from_bytes((raw & 0xffff).to_bytes(2, 'little'), 'little', signed=True)
        if row['stage'] == 6 and raw & 0xf0000000 == 0x40000000:
            row['name'] = 'pairing-ui-transition'
            row['ui_progress'] = (raw >> 16) & 255
            row['ui_result'] = int.from_bytes((raw & 0xffff).to_bytes(2, 'little'), 'little', signed=True)
            row['menu_before'], row['menu_after'] = (f'0x{v:04x}' for v in state[:2])
        if row['stage'] == 7 and 10256 <= status < 10000 + len(CONTROLLER_ACTIONS) * 256:
            action, code = divmod(status - 10000, 256)
            row.update(controller_action=CONTROLLER_ACTIONS[action], controller_result=code - 128)
        if row['stage'] in (8, 9):
            row.update(radio_queued=raw & 0xffff, radio_dropped=raw >> 16)
        if row['stage'] in (10, 11) and status >= 0:
            row.update(chip_hook_entries=raw & 0xffff, chip_eligible=raw >> 16)
        if row['stage'] == 12:
            row.update(sample_attempted=bool(raw & 1), before_read=bool(raw & 2),
                       retune_completed=bool(raw & 4), after_read=bool(raw & 8))
        if row['stage'] in (13, 14):
            row['tuner_registers_67_to_6a'] = raw.to_bytes(4, 'little').hex(' ')
        if row['stage'] == 15:
            row.update(queue_baseline=bool(raw & 1), chip_baseline=bool(raw & 2),
                       clock_ready=bool(raw & 4), promiscuous_membership=bool(raw & 8))
            if raw & 0xf0 or raw >> 8:
                row.update(interface_flags_read=bool(raw & 64), interface_up=bool(raw & 16),
                           interface_promiscuous=bool(raw & 32), radio_state_read=bool(raw & 128),
                           startup_ms_before_listening=raw >> 8)
        if row['stage'] in (8, 9, 15) and any(state):
            row['radio_state'] = dict(zip(('mac_control_word', 'receive_filter_register',
                'ring_read_pointer', 'ring_write_pointer', 'last_work_length_and_frame_control',
                'management_state_word'), (f'0x{value:08x}' for value in state)))
        if row['stage'] == 16 and raw & 0xf0000000 == 0x60000000:
            row.update(chip_hook_entries=raw & 127, chip_eligible=(raw >> 7) & 127,
                       radio_queued=(raw >> 14) & 127, radio_dropped=(raw >> 21) & 127,
                       count_cap=127)
        if row['stage'] == 16 and raw & 0xf0000000 == 0x70000000:
            row.update(chip_hook_entries=raw & 15, chip_eligible=(raw >> 4) & 15,
                       radio_queued=(raw >> 8) & 15, radio_dropped=(raw >> 12) & 15,
                       listening_seconds=(raw >> 16) & 255, count_cap=15, seconds_cap=255,
                       stop_cause={0: 'unspecified', 1: 'clock-or-prior-stop', 2: 'pairing-deadline',
                                   3: 'mode-admission', 5: 'controller-or-runtime'}.get((raw >> 24) & 15, 'unknown'))
    result['records'].sort(key=lambda row: row['sequence'])
    print(json.dumps(result, indent=2))
    return 0 if result['integrity_valid'] and result.get('comparison', {}).get('append_only', True) else 2


if __name__ == '__main__':
    raise SystemExit(main())
