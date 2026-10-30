"""Actual chat client fork/exec/owner through managed launcher; PC effects only."""
from pathlib import Path
import ctypes,hashlib,json,os,select,shutil,signal,subprocess,tempfile,time
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/chat-managed-process';OUT.mkdir(exist_ok=True)
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
common=['gcc','-std=c99','-D_DEFAULT_SOURCE','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(ROOT/'sdk/include')]
handoff=['runtime/apps/espnow-chat/chat_handoff.c','runtime/platform/espnow/xnow_managed_process.c']
owner_sources=['runtime/apps/espnow-chat/chat_owner.c','runtime/apps/espnow-chat/chat_handoff_owner.c',*handoff,'tools/fixtures/chat_owner_platform.c','tools/fixtures/xnow_control_platform.c']+['runtime/platform/espnow/'+n+'.c' for n in ('xnow_control','xnow_manager','xnow_session','xnow_chat')]
runner_sources=['tools/fixtures/chat_managed_process.c','runtime/platform/espnow/xnow_launcher_bridge.c','runtime/platform/espnow/xnow_managed_process.c','runtime/platform/espnow/xnow_handoff.c','runtime/native/app_process.c','runtime/native/linux_process_posix.c']
subprocess.run([*common,*runner_sources,'-o',str(OUT/'runner')],cwd=ROOT,check=True)
rows=[]
for mode in ('normal','crash'):
    folder=OUT/mode;folder.mkdir(exist_ok=True);worker=(folder/'radio-worker').resolve()
    subprocess.run([*common,'-DCHAT_OWNER_FIXTURE_MODE="'+mode+'"',*owner_sources,'-include','string.h','-o',str(worker)],cwd=ROOT,check=True)
    data=worker.read_bytes();digest=hashlib.sha256(data).digest()
    (folder/'chat_worker_identity.h').write_text('#define CHAT_WORKER_BYTES '+str(len(data))+'u\nstatic const unsigned char chat_worker_sha[32]={'+','.join(map(str,digest))+'};\n')
    original=(ROOT/'runtime/apps/espnow-chat/chat_client.c').read_text();literal='"/contents/HOMEBREW/apps/espnow-chat/radio-worker"';assert original.count(literal)==1
    client=folder/'client.c';client.write_text(original.replace(literal,json.dumps(str(worker))))
    ui_sources=['tools/fixtures/chat_managed_process.c',str(client),*handoff,'runtime/platform/espnow/xnow_file_check.c','runtime/native/sha256.c']
    subprocess.run([*common,'-DCHAT_UI_FIXTURE','-I'+str(folder),'-I'+str(ROOT/'runtime/apps/espnow-chat'),'-Wl,--wrap=lstat',*ui_sources,'-o',str(folder/'ui')],cwd=ROOT,check=True)
    clean_environment={k:v for k,v in os.environ.items() if k not in ('XNOW_HANDOFF_FD','XNOW_HANDOFF_COOKIE')}
    refused=subprocess.run([str(folder/'ui'),'--no-cap'],env=clean_environment,capture_output=True,text=True,check=True,timeout=3)
    assert refused.stdout=='unmanaged RF startup refused before owner fork\n'
    with tempfile.TemporaryDirectory(prefix=mode+'-',dir=OUT) as temporary:
        runfolder=Path(temporary);shutil.copy2(folder/'ui',runfolder/'app')
        started=time.monotonic();p=subprocess.Popen([str(OUT/'runner'),str(runfolder.resolve()),mode],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            if mode=='normal':
                stdout,stderr=p.communicate(timeout=16);assert p.returncode==0 and stdout=='managed_chat_status=9\n',(p.returncode,stdout,stderr)
                assert (runfolder/'owner-restored').exists();pid=int((runfolder/'worker-pid').read_text());_,status=os.waitpid(pid,0);assert status==0
                rows.append({'mode':mode,'ui_sigkill_status':9,'restore_completed_before_foreground_return':True,'seconds':round(time.monotonic()-started,3)})
            else:
                deadline=time.monotonic()+14;held=False
                while time.monotonic()<deadline:
                    ready,_,_=select.select([p.stderr],[],[],1)
                    if ready and 'Managed radio recovery is unconfirmed; foreground retained.' in p.stderr.readline():held=True;break
                    assert p.poll() is None,'foreground returned without restore'
                assert held and p.poll() is None and not (runfolder/'owner-restored').exists()
                pid=int((runfolder/'worker-pid').read_text());_,status=os.waitpid(pid,0);assert os.WIFEXITED(status) and os.WEXITSTATUS(status)==76
                rows.append({'mode':mode,'owner_crash_without_completion':True,'foreground_retained':True})
        finally:
            if p.poll() is None:p.kill();p.communicate(timeout=3)
            for name in ('ui-pid','worker-pid'):
                path=runfolder/name
                if not path.exists():continue
                pid=int(path.read_text())
                try:
                    got,_=os.waitpid(pid,os.WNOHANG)
                    if not got:os.kill(pid,signal.SIGKILL);os.waitpid(pid,0)
                except ChildProcessError:pass
report={'passed':True,'cases':rows,'real_chat_client_and_owner':True,'worker_hash_check_executed':True,'managed_launcher_grace_unmodified':True,'test_substitutions':['worker pathname redirected to project work','root/user-volume lstat distinction modeled','radio and cnmgr effects modeled'],'host_process_test_only':True,'device_accessed':False,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in set(owner_sources+runner_sources+['runtime/apps/espnow-chat/chat_client.c','tools/test_chat_managed_process.py'])}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
