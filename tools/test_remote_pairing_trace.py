"""PC-only pairing trace compatibility, CRC, state and lifetime decoding."""
import json
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from read_remote_pairing_trace import HEADER, SEED

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='pairing-trace-', dir=ROOT / 'work') as folder:
    path = Path(folder) / 'trace.bin'
    cases = 0
    for tag in (0x60000000, 0x70000000):
        trace = bytearray(HEADER.ljust(2048, b'\0'))
        state = [0x80000283, 0x1000000b, 0x10, 0x20, 0x00d00057, 0x101]
        ready = [(1234 << 8) | 255, 1, 1, 1, 1, 0, *state]
        summary = tag | (1 if tag == 0x60000000 else 1 | (15 << 4) | (4 << 16) | (3 << 24))
        for seq, stage, payload in ((1, 15, ready), (2, 16, [summary, 1, 1, 1, 1, 0, *([0] * 6)])):
            raw = struct.pack('<15I', 0x31504248, stage, seq, *payload)
            raw += struct.pack('<I', zlib.crc32(raw))
            trace[32 + (stage - 1) * 64:32 + stage * 64] = raw
        path.write_bytes(trace)
        result = subprocess.run([sys.executable, str(ROOT / 'tools/read_remote_pairing_trace.py'),
                                 str(path)], capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        assert report['integrity_valid'] and not report['hardware_success_proven']
        ready, retired = report['records']
        assert ready['startup_ms_before_listening'] == 1234 and ready['interface_up']
        assert ready['radio_state']['mac_control_word'] == '0x80000283'
        assert retired['chip_hook_entries'] == 1
        if tag == 0x70000000:
            assert retired['listening_seconds'] == 4 and retired['chip_eligible'] == 15
            assert retired['stop_cause'] == 'mode-admission'
        trace[32 + 14 * 64 + 16] ^= 1
        path.write_bytes(trace)
        damaged = subprocess.run([sys.executable, str(ROOT / 'tools/read_remote_pairing_trace.py'),
                                  str(path)], capture_output=True, text=True)
        assert damaged.returncode == 2 and not json.loads(damaged.stdout)['integrity_valid']
        cases += 1
    trace = bytearray(HEADER.ljust(2048, b'\0'))
    payload = [0x40150000, 1, 1, 1, 1, 0, 0xc202, 0x9b01, 0, 0, 1, 0]
    raw = struct.pack('<15I', 0x31504248, 6, 1, *payload)
    raw += struct.pack('<I', zlib.crc32(raw))
    trace[32 + 5 * 64:32 + 6 * 64] = raw
    path.write_bytes(trace)
    run = subprocess.run([sys.executable, str(ROOT / 'tools/read_remote_pairing_trace.py'),
                          str(path)], capture_output=True, text=True, check=True)
    row = json.loads(run.stdout)['records'][0]
    assert row['name'] == 'pairing-ui-transition' and row['ui_progress'] == 21
    assert row['menu_before'] == '0xc202' and row['menu_after'] == '0x9b01'
    for seq,stage in enumerate((17,18,19,20,21),2):
        payload=[0,0,0,1,1,0,0x103,1,2,3,0,0]
        raw=struct.pack('<15I',0x31504248,stage,seq,*payload)
        raw+=struct.pack('<I',zlib.crc32(raw))
        trace[32+(stage-1)*64:32+stage*64]=raw
    path.write_bytes(trace)
    run=subprocess.run([sys.executable,str(ROOT/'tools/read_remote_pairing_trace.py'),str(path)],capture_output=True,text=True,check=True)
    decoded=json.loads(run.stdout)
    assert decoded['integrity_valid'] and len(decoded['records'])==6
    assert decoded['records'][-1]['runtime_context']['main_state']==0x103
    payload=[0xffffffff,0,0,1,1,0,0,1,0,3,0xfffffffa,0]
    raw=struct.pack('<15I',0x31504248,23,7,*payload)
    raw+=struct.pack('<I',zlib.crc32(raw))
    trace[32+22*64:32+23*64]=raw
    path.write_bytes(trace)
    run=subprocess.run([sys.executable,str(ROOT/'tools/read_remote_pairing_trace.py'),str(path)],capture_output=True,text=True,check=True)
    row=json.loads(run.stdout)['records'][-1]
    assert row['result']==-1 and row['exit_detail']==dict(service_exit=0,owner_exit=1,
        application_error=0,worker_reason=3,worker_error=-6,player_close_error=0)
    payload=[0xffffffeb,0,0,1,1,0,5,0,0,0,0,0]
    raw=struct.pack('<15I',0x31504248,24,8,*payload)
    raw+=struct.pack('<I',zlib.crc32(raw));trace[32+23*64:32+24*64]=raw;path.write_bytes(trace)
    run=subprocess.run([sys.executable,str(ROOT/'tools/read_remote_pairing_trace.py'),str(path)],capture_output=True,text=True,check=True)
    row=json.loads(run.stdout)['records'][-1]
    assert row['result']==-21 and row['failure_origin']=='receive-security' and row['failure_domain']=='encrypted-counter-storage'
    payload=[(-4101)&0xffffffff,0,0,1,1,0,2,0,0,0,0,0]
    raw=struct.pack('<15I',0x31504248,24,8,*payload)
    raw+=struct.pack('<I',zlib.crc32(raw));trace[32+23*64:32+24*64]=raw;path.write_bytes(trace)
    run=subprocess.run([sys.executable,str(ROOT/'tools/read_remote_pairing_trace.py'),str(path)],capture_output=True,text=True,check=True)
    row=json.loads(run.stdout)['records'][-1]
    assert row['result']==-4101 and row['failure_origin']=='endpoint-prepare'
    assert 'failure_domain' not in row
    payload=[0xfffffffe,0,0,1,1,0,3,1,0,0,0,0]
    raw=struct.pack('<15I',0x31504248,25,9,*payload)
    raw+=struct.pack('<I',zlib.crc32(raw));trace[32+24*64:32+25*64]=raw;path.write_bytes(trace)
    run=subprocess.run([sys.executable,str(ROOT/'tools/read_remote_pairing_trace.py'),str(path)],capture_output=True,text=True,check=True)
    row=json.loads(run.stdout)['records'][-1]
    assert row['result']==-2 and row['startup_stage']=='player-hello' and row['player_capability_closed']
    payload=[0,0,0,1,1,0,19,2,3,5,1,0]
    raw=struct.pack('<15I',0x31504248,26,10,*payload)
    raw+=struct.pack('<I',zlib.crc32(raw));trace[32+25*64:32+26*64]=raw;path.write_bytes(trace)
    run=subprocess.run([sys.executable,str(ROOT/'tools/read_remote_pairing_trace.py'),str(path)],capture_output=True,text=True,check=True)
    decoded=json.loads(run.stdout);row=decoded['records'][-1]
    assert not decoded['hardware_success_proven']
    assert row['radio_summary']==dict(decoded=19,authentication_rejected=2,replay_rejected=3,
        negotiation_frames=5,negotiated_key_installs=1,shared_wake_unrestored=0)
    before = Path(folder) / 'before.bin'
    baseline = bytearray(SEED)
    baseline[32+22*64:32+23*64] = trace[32+22*64:32+23*64]
    before.write_bytes(baseline)
    command = [sys.executable, str(ROOT/'tools/read_remote_pairing_trace.py'), str(path), '--before', str(before)]
    decoded = json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)
    assert not decoded['attempt_identity_present']
    assert decoded['comparison']['append_only'] and 23 not in decoded['comparison']['new_committed_slots']
    assert 26 in decoded['comparison']['new_committed_slots']
    assert next(row for row in decoded['records'] if row['stage'] == 23)['since_before'] == 'unchanged'
    path.write_bytes(SEED)
    reset = subprocess.run(command, capture_output=True, text=True)
    comparison = json.loads(reset.stdout)['comparison']
    assert reset.returncode == 2 and not comparison['append_only']
    assert comparison['changed_occupied_slots'] == [23] and comparison['new_committed_slots'] == []
    baseline[32+22*64] ^= 1
    before.write_bytes(baseline)
    path.write_bytes(trace)
    damaged_baseline = subprocess.run(command, capture_output=True, text=True)
    comparison = json.loads(damaged_baseline.stdout)['comparison']
    assert damaged_baseline.returncode == 2 and comparison['baseline_invalid_slots']
    assert comparison['new_committed_slots'] == []
print(json.dumps(dict(passed=True, summary_formats=cases, crc_rejection=True,
                     append_only_comparison=True, gui_transition_decoded=True,
                     hardware_success_never_inferred=True, device_accessed=False)))
