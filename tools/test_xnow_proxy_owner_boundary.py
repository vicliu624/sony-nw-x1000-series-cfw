"""Original proxy monitor boundary: child exit records are not radio-restored ACKs.

Reuses existing original-instruction harness with supplied waitpid results; does
not touch its standard reports. No actual child/APF/USB/device runs here.
"""
from pathlib import Path
import hashlib,json
from app_registry import ROOT
baseline=ROOT/'tools/check_proxy_stop_order.py';text=baseline.read_text();text=text[:text.index('output=ROOT/(')]
text=text.replace('options=parser.parse_args()','options=parser.parse_args([])')
old='for event, child_status, late_stop in product((4, 6, None), statuses, (False, True)):'
assert old in text;text=text.replace(old,'for event, child_status, late_stop in ((4, 0, False), (6, 0, False)):')
# Preserve stop target321. Only the supplied libc waitpid result/expected
# native writev record changes to the reported direct-child fixture.
text=text.replace("elif pc == syms['waitpid']:\n", "elif pc == syms['waitpid']:\n            assert args[0]==0xffffffff and args[2]==1\n            trace.append('waitpid-any-child-WNOHANG')\n")
rows=[]
for reported_pid in (321,433):
 source=text.replace("uc.reg_write(UC_ARM_REG_R0, child_pid)","uc.reg_write(UC_ARM_REG_R0, "+str(reported_pid)+")").replace("struct.pack('<II', child_pid, child_status)","struct.pack('<II', "+str(reported_pid)+", child_status)")
 scope={'__file__':str(baseline),'__name__':'proxy_owner_boundary_fixture'};exec(compile(source,str(baseline),'exec'),scope)
 result=scope['result'];assert result['self_event_shutdown_not_manager_op3'] and not result['quit_wire_to_manager_op3_verified']
 for case in result['cases']:
  assert case['monitor_return']==0 and case['quit_after_reaped_child'] and 'waitpid-any-child-WNOHANG' in case['trace']
  assert case['trace'].index('child-reaped')<case['trace'].index('proxy-termination-message')
  rows.append({'stop_event':case['stop_event'],'stop_target_pid':321,'supplied_reaped_pid':reported_pid,'monitor_returns_without_pid_match':reported_pid!=321,'monitor_return':case['monitor_return'],'captured_self_shutdown_messages':case['captured_quit_wire_requests'],'trace':case['trace']})
report={'passed':True,'appproxy_sha256':hashlib.sha256((ROOT/'work/targets-jp/appproxy').read_bytes()).hexdigest(),'cases':rows,'waitpid_any_child_wnohang_executed':True,'monitor_has_no_radio_restore_ack':True,'self_event_is_not_manager_op3':True,'untracked_detached_owner_wait_not_established':True,'limits':['Libc waitpid results and original IPC/thread effects are supplied fixtures.','No actual child/APF manager or USB unmount/export order executes.','Different reaped PID case is a supplied direct-child scenario, not a claim that the detached radio owner is a child of proxy.'],'device_accessed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/test_xnow_proxy_owner_boundary.py','tools/check_proxy_stop_order.py','sources/native-manager-proxy-exec-request.json']}}
out=ROOT/'work/espnow-proxy-owner-boundary';out.mkdir(exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('cases','source_hashes')},indent=2))
