"""Compiled correlation hook, original release and full RX/TX code budget."""
import hashlib
import json
from app_registry import ROOT
from radio_test_profile import legacy_completion_fixture, selected_radio

output = ROOT / 'work/espnow-completion-hook'
fixture = legacy_completion_fixture(output, selected_radio())
env = fixture['env']
cpu, word, call, free_count = (env[name] for name in ('cpu', 'word', 'call', 'free_count'))
state, completion, sections, releases, command, operation, submit, finish = (
    fixture[name] for name in ('state', 'completion', 'sections', 'releases',
                               'command', 'operation', 'submit', 'finish')
)
env['queue_result'][0]=0
for status in (0,1):
 packet,token=submit();assert operation(1)==-2
 other=call(0xd458,1900);finish(other,1,0xffffffff)
 assert word(completion)==packet and word(completion+8)==word(completion+20)
 finish(packet,status,0x00070302)
 assert word(completion)==0 and word(completion+8)==token and word(completion+12)==status and word(completion+16)==0x00070302
 assert free_count()==3 and operation(1)==-2
 command(completion+20,token)
# Original task5 can reject before any MAC completion exists; common free
# still publishes the correlated terminal result and returns original0.
packet,token=submit();before=len(releases)
assert call(0xd51c,packet)==0
assert releases[before:]==[packet] and free_count()==3
assert word(completion)==0 and word(completion+8)==token and word(completion+12)==2 and word(completion+16)==0
command(completion+20,token)
# Rejected submission clears correlation before the original free.
assert operation(1)==0;packet=word(state+24);cpu.mem_write(packet+32,b'\x7f\x18\xfe\x34'+bytes(11));command(state+20,15)
env['queue_result'][0]=1
before=len(releases);assert operation(2)==-1 and word(completion)==0 and releases[before:]==[packet] and free_count()==3
assert operation(1)==0 and operation(3)==0 and free_count()==3
report={'passed':True,'original_common_management_free_patched':True,'pre_mac_rejection_reports_terminal_status2':True,'original_release_exactly_once':True,'unrelated_management_packet_ignored_by_observer':True,'completion_status_and_token_correlated':True,'unread_completion_backpressure':True,'queue_rejection_clears_pending':True,'task_stack_callee_saved_and_displaced_loads_preserved':True,'combined_reserved_bytes':sum(len(d) for _,d in sections),'completion_records_and_scheduler_modeled':True,'device_accessed':False,'download_image_created':False}
report.update(fixture['provenance'])
report['source_hashes']['tools/test_radio_completion_hook.py']=hashlib.sha256((ROOT/'tools/test_radio_completion_hook.py').read_bytes()).hexdigest()
output.mkdir(parents=True, exist_ok=True)
(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
