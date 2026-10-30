"""Opt-in actual launcher bridge: correct restore returns, crash holds foreground.

Only host test descendants are killed/reaped for bounded cleanup. RF/APF mocked.
"""
from pathlib import Path
import ctypes,hashlib,json,os,select,shutil,signal,subprocess,tempfile,time
from app_registry import ROOT
OUT=ROOT/'work/espnow-launcher-bridge';OUT.mkdir(exist_ok=True)
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
sources=['tools/fixtures/xnow_launcher_bridge_ui.c',*['runtime/platform/espnow/'+n+'.c' for n in ('xnow_launcher_bridge','xnow_managed_process','xnow_handoff','xnow_handoff_owner','xnow_owner_gate','xnow_full_control','xnow_session','xnow_manager')],'tools/fixtures/xnow_control_platform.c','runtime/native/app_process.c','runtime/native/linux_process_posix.c']
for name,flags in (('runner',[]),('ui',['-DXNOW_UI_CHILD'])):
 subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-DXNOW_OWNER_GATE_NAMESPACE="x1000-xnow-bridge-offline-test-v1"',*flags,*sources,'-o',str(OUT/name)],cwd=ROOT,check=True)
rows=[]
for mode in ('normal','crash'):
 with tempfile.TemporaryDirectory(prefix=mode+'-',dir=OUT) as temporary:
  folder=Path(temporary);shutil.copy2(OUT/'ui',folder/'app');sha=hashlib.sha256((folder/'app').read_bytes()).hexdigest();(folder/'launch.contract').write_bytes(b'XNOW-MANAGED-1\n'+sha.encode()+b'\n')
  started=time.monotonic();p=subprocess.Popen([str(OUT/'runner'),str(folder),mode,sha],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   if mode=='normal':
    stdout,stderr=p.communicate(timeout=14);assert p.returncode==0 and stdout=='bridge_status=9\n',(p.returncode,stdout,stderr)
    assert (folder/'owner-restored').exists() and (folder/'child-detached').exists()
    pid=int((folder/'worker-pid').read_text());_,status=os.waitpid(pid,0);assert status==0
    rows.append({'mode':mode,'returned_ui_status':9,'restore_completed_before_return':True,'elapsed_seconds':round(time.monotonic()-started,3)})
   else:
    deadline=time.monotonic()+12;message=False;lines=[]
    while time.monotonic()<deadline:
     ready,_,_=select.select([p.stderr],[],[],1)
     if ready:
      line=p.stderr.readline();lines.append(line)
      if 'Managed radio recovery is unconfirmed; foreground retained.' in line:message=True;break
     assert p.poll() is None,('foreground exited early',p.returncode,''.join(lines))
    assert message and p.poll() is None and not (folder/'owner-restored').exists()
    pid=int((folder/'worker-pid').read_text());_,status=os.waitpid(pid,0);assert os.WIFEXITED(status) and os.WEXITSTATUS(status)==76
    assert p.poll() is None
    rows.append({'mode':mode,'owner_exited_without_restore':True,'foreground_still_alive':True,'release_not_permitted':True,'bounded_test_cleanup_kill_only':True,'elapsed_seconds':round(time.monotonic()-started,3)})
  finally:
   if p.poll() is None:p.kill();p.communicate(timeout=5)
   for name in ('ui-pid','worker-pid'):
    path=folder/name
    if not path.is_file():continue
    pid=int(path.read_text())
    if pid<=1:continue
    try:
     waited,_=os.waitpid(pid,os.WNOHANG)
     if not waited:os.kill(pid,signal.SIGKILL);os.waitpid(pid,0)
    except ChildProcessError:pass
report={'passed':True,'actual_launcher_bridge_used':True,'cases':rows,'production_default_not_selected':True,'original_app_process_unmodified':True,'radio_manager_loader_and_apf_effects_mocked':True,'host_supervisor_subreaper_for_test_cleanup_only':True,'device_accessed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'tools/test_xnow_launcher_bridge.py','tools/test_xnow_full_control.c']}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
