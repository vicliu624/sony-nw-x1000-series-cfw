"""Actual host launcher grace with detached cleanup worker and foreground barrier.

PR_SET_CHILD_SUBREAPER is set only on this PC test supervisor for cleanup; the
simulated launcher/worker do not use it. No player, APF, kernel USB or RF test.
"""
from pathlib import Path
import ctypes,hashlib,json,os,re,shutil,signal,subprocess,tempfile,time
from app_registry import ROOT
OUT=ROOT/'work/espnow-supervised-handoff';OUT.mkdir(exist_ok=True)
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
fixture='tools/fixtures/xnow_supervised_ui.c'
common=[fixture,'runtime/platform/espnow/xnow_handoff.c','runtime/platform/espnow/xnow_handoff_owner.c','runtime/platform/espnow/xnow_owner_gate.c','runtime/platform/espnow/xnow_full_control.c','runtime/platform/espnow/xnow_session.c','runtime/platform/espnow/xnow_manager.c','tools/fixtures/xnow_control_platform.c','runtime/native/app_process.c','runtime/native/linux_process_posix.c']
flags=['gcc','-std=c99','-Wall','-Wextra','-Werror','-DXNOW_OWNER_GATE_NAMESPACE="x1000-xnow-supervised-offline-test-v1"']
for name,extra in (('runner',[]),('ui',['-DXNOW_UI_CHILD'])):subprocess.run([*flags,*extra,*common,'-o',str(OUT/name)],cwd=ROOT,check=True)
rows=[]
for mode in ('normal','crash'):
 with tempfile.TemporaryDirectory(prefix=mode+'-',dir=OUT) as temporary:
  folder=Path(temporary);shutil.copy2(OUT/'ui',folder/'app');started=time.monotonic();run=None;pid=None
  try:
   run=subprocess.run([str(OUT/'runner'),str(folder),mode],capture_output=True,text=True,timeout=14)
   pid_path=folder/'worker-pid'
   if pid_path.is_file():pid=int(pid_path.read_text())
   assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
   match=re.fullmatch(r'ui_status=(\d+) pending_after_reap=(\d+) handoff=(-?\d+) permitted_release=(\d+)\n',run.stdout);assert match,run.stdout
   status,pending,handoff,permitted=map(int,match.groups());assert status==9 and pending==1
   assert pid and pid>1
   waited,worker_status=os.waitpid(pid,0);assert waited==pid
   if mode=='normal':assert handoff==0 and permitted==1 and worker_status==0 and (folder/'owner-restored').exists()
   else:assert handoff==-4 and permitted==0 and os.WIFEXITED(worker_status) and os.WEXITSTATUS(worker_status)==76 and not (folder/'owner-restored').exists()
   rows.append({'mode':mode,'ui_wait_status':status,'restore_still_pending_when_ui_reaped':bool(pending),'handoff_result':handoff,'release_permitted':bool(permitted),'elapsed_seconds':round(time.monotonic()-started,3),'worker_status':worker_status})
   pid=None
  finally:
   # Test-only cleanup: after runner timeout its UI/owner become children of
   # this subreaper. Verify parentage with waitpid before signaling any PID.
   for name in ('ui-pid','worker-pid'):
    path=folder/name
    if not path.is_file():continue
    target=int(path.read_text())
    if target<=1:continue
    try:
     waited,_=os.waitpid(target,os.WNOHANG)
     if not waited:os.kill(target,signal.SIGKILL);os.waitpid(target,0)
    except ChildProcessError:pass
report={'passed':True,'cases':rows,'original_app_process_grace_unmodified':True,'actual_host_processes_pipes_signals':True,'real_radio_manager_loader_apf_effects_mocked':True,'host_test_supervisor_subreaper_for_cleanup_only':True,'production_launcher_modified':False,'sdk_or_device_deployed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*common,'tools/test_xnow_supervised_handoff.py','tools/test_xnow_full_control.c']}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
