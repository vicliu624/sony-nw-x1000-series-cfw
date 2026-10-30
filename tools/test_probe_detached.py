"""Kill the launching PC process group; actual detached C worker must finish."""
from pathlib import Path
import ctypes,hashlib,json,os,select,signal,subprocess,tempfile,time
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/autonomous-espnow-test';OUT.mkdir(exist_ok=True)
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
sources=['tools/fixtures/probe_detached.c','runtime/apps/espnow-test/detached.c'];app=OUT/'detach.host'
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,'-o',str(app)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(dir=OUT) as temporary:
 log=Path(temporary)/'result.txt'
 shell=subprocess.Popen(['/bin/sh','-c','"$1" "$2"; sleep 30','sh',str(app.resolve()),str(log.resolve())],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
 pid=None
 try:
  assert select.select([shell.stdout],[],[],5)[0];line=shell.stdout.readline().strip();assert line.startswith('job_pid=')
  pid=int(line.split()[0].split('=')[1]);assert pid>1 and os.getsid(pid)==pid and os.getpgid(pid)==pid and os.getpgid(shell.pid)!=pid
  os.killpg(shell.pid,signal.SIGTERM);shell.wait(timeout=3)
  waited,status=os.waitpid(pid,0);assert waited==pid and status==0 and log.read_bytes()==b'COMPLETED\n';pid=None
 finally:
  if shell.poll() is None:os.killpg(shell.pid,signal.SIGKILL);shell.wait(timeout=3)
  shell.communicate(timeout=3)
  if pid:
   try:os.kill(pid,signal.SIGKILL);os.waitpid(pid,0)
   except ProcessLookupError:pass
report={'passed':True,'actual_child_setsid_and_fd_cleanup':True,'launching_process_group_terminated':True,'background_worker_completed_and_fsynced_log':True,'device_accessed':False,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in [*sources,'runtime/apps/espnow-test/detached.h','tools/test_probe_detached.py']}}
(OUT/'detach-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
