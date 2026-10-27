"""Host regression: ignored SIGTERM must not strand the launcher; fixture processes only."""
from pathlib import Path
import subprocess,os,signal,select,json,hashlib
r=Path(__file__).resolve().parents[1];w=r/'work/unresponsive-app-regression';w.mkdir(exist_ok=True)
(w/'runner.c').write_text('#include <signal.h>\n#include <stdio.h>\n#include <unistd.h>\n#include <sys/wait.h>\n#include "../../runtime/native/app_process.h"\nstatic volatile int stopping;\nstatic void stop(int n) { (void)n; stopping=1; }\nint main(int argc,char **argv) {\n if(argc!=3)return 64;\n signal(SIGTERM,stop);\n char *env[]={0};\n int status=hb_process_run(argv[1],argv[2],env,&stopping);\n printf("STATUS %d STOP %d\\n",status,stopping);fflush(stdout);\n return status<0?1:0;\n}\n')
(w/'app.c').write_text('#define _DEFAULT_SOURCE\n#include <signal.h>\n#include <stdio.h>\n#include <unistd.h>\nint main(void) {\n signal(SIGTERM,SIG_IGN);\n printf("READY %ld\\n",(long)getpid());fflush(stdout);\n for(;;)pause();\n}\n')
subprocess.run(['gcc','-D_DEFAULT_SOURCE','-std=c99','-O2','-Wall','-Wextra','-Werror',str(w/'runner.c'),str(r/'runtime/native/app_process.c'),str(r/'runtime/native/linux_process_posix.c'),'-o',str(w/'runner')],check=True)
subprocess.run(['gcc','-std=c99','-O2',str(w/'app.c'),'-o',str(w/'app')],check=True)
p=subprocess.Popen([str(w/'runner'),str(w),str(w/'app')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);child=None;timed_out=False
try:
 if not select.select([p.stdout],[],[],4)[0]:raise RuntimeError('No ready marker')
 line=p.stdout.readline();assert line.startswith('READY '),line;child=int(line.split()[1])
 assert int(Path(f'/proc/{child}/stat').read_text().split()[3])==p.pid
 p.send_signal(signal.SIGTERM)
 try:out,err=p.communicate(timeout=4)
 except subprocess.TimeoutExpired:
  timed_out=True
  assert int(Path(f'/proc/{child}/stat').read_text().split()[3])==p.pid
  os.kill(child,signal.SIGKILL);out,err=p.communicate(timeout=4)
 assert not timed_out, 'Launcher still waits indefinitely'
 assert p.returncode==0 and 'STATUS 9 STOP 1' in out
 report={'passed':True,'source_hashes':{str(q.relative_to(r)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [Path(__file__),r/'runtime/native/app_process.c',r/'runtime/native/linux_process_posix.c',r/'runtime/native/linux_process.h']},'ignored_sigterm_reproduced_wait':timed_out,'runner_exit':p.returncode,'output':out.strip(),'scope':'Host fixture only; actual app_process/POSIX backend, no Sony code or device'}
 (w/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
finally:
 if p.poll() is None:
  if child and Path(f'/proc/{child}/stat').exists() and int(Path(f'/proc/{child}/stat').read_text().split()[3])==p.pid:os.kill(child,signal.SIGKILL)
  p.kill();p.wait()

