"""Actual managed launcher + full owner runtime in real host fork/exec processes."""
from pathlib import Path
import ctypes,hashlib,json,os,select,shutil,signal,subprocess,tempfile,time
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-full-owner-process';OUT.mkdir(parents=True,exist_ok=True)
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0 # PC descendant cleanup only
sources=['tools/fixtures/full_owner_process.c','tools/fixtures/xnow_control_platform.c']+['runtime/platform/espnow/'+n+'.c' for n in ['xnow_launcher_bridge','xnow_managed_process','xnow_handoff','xnow_handoff_owner','xnow_owner_runtime','xnow_owner_gate','xnow_owner_stream','xnow_owner_commands','xnow_owner_commands_control','xnow_full_control','xnow_session','xnow_manager','xnow_endpoint','xnow_peer','xnow_wire','xnow_full']]+['runtime/native/app_process.c','runtime/native/linux_process_posix.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
for name,extra in [('runner',[]),('ui',['-DXNOW_RUNTIME_CHILD'])]:
    subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-DXNOW_OWNER_GATE_NAMESPACE="x1000-xnow-full-process-offline-v1"',*extra,*sources,'-o',str(OUT/name)],cwd=ROOT,check=True)
rows=[]
for mode in ['normal','crash']:
    with tempfile.TemporaryDirectory(prefix=mode+'-',dir=OUT) as temporary:
        folder=Path(temporary);shutil.copy2(OUT/'ui',folder/'app');sha=hashlib.sha256((folder/'app').read_bytes()).hexdigest();(folder/'launch.contract').write_bytes(b'XNOW-MANAGED-1\n'+sha.encode()+b'\n')
        started=time.monotonic();p=subprocess.Popen([str(OUT/'runner'),str(folder),mode,sha],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            if mode=='normal':
                stdout,stderr=p.communicate(timeout=14);assert p.returncode==0 and stdout=='bridge_status=9\n',(p.returncode,stdout,stderr)
                assert (folder/'owner-restored').exists() and (folder/'child-detached').exists() and (folder/'radio-inflight').exists()
                pid=int((folder/'worker-pid').read_text());_,status=os.waitpid(pid,0);assert status==0
                rows.append({'mode':mode,'returned_ui_status':9,'actual_full_runtime':True,'1470_byte_send_inflight_before_ui_stop':True,'restore_completed_before_return':True,'elapsed_seconds':round(time.monotonic()-started,3)})
            else:
                deadline=time.monotonic()+12;message=False;lines=[]
                while time.monotonic()<deadline:
                    ready,_,_=select.select([p.stderr],[],[],1)
                    if ready:
                        line=p.stderr.readline();lines.append(line)
                        if 'Managed radio recovery is unconfirmed; foreground retained.' in line:message=True;break
                    assert p.poll() is None,('foreground exited early',p.returncode,''.join(lines))
                assert message and p.poll() is None and not (folder/'owner-restored').exists() and (folder/'radio-inflight').exists()
                pid=int((folder/'worker-pid').read_text());_,status=os.waitpid(pid,0);assert os.WIFEXITED(status) and os.WEXITSTATUS(status)==76;assert p.poll() is None
                rows.append({'mode':mode,'actual_full_runtime':True,'owner_exited_without_restore':True,'foreground_still_alive':True,'release_not_permitted':True,'elapsed_seconds':round(time.monotonic()-started,3)})
        finally:
            if p.poll() is None:p.kill();p.communicate(timeout=3)
            for name in ['ui-pid','worker-pid']:
                path=folder/name
                if not path.exists():continue
                pid=int(path.read_text())
                if pid<=1:continue
                try:
                    waited,_=os.waitpid(pid,os.WNOHANG)
                    if not waited:os.kill(pid,signal.SIGKILL);os.waitpid(pid,0)
                except ChildProcessError:pass
dependencies=[*sources,'tools/fixtures/full_owner_ipc.c','tools/test_xnow_full.c','tools/test_full_owner_process.py','runtime/platform/espnow/xnow_owner_runtime.h','runtime/platform/espnow/xnow_launcher_bridge.h']
report={'passed':True,'cases':rows,'actual_host_fork_exec_pipes_signals':True,'original_launcher_grace_unmodified':True,'actual_full_owner_runtime':True,'real_radio_apf_usb_manager_effects_mocked':True,'host_subreaper_for_fixture_cleanup_only':True,'device_accessed':False,'installed':False,'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in dependencies}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2))
