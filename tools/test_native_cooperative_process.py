"""Real host process tests for cooperative external apps; never access Sony hardware."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
# Existing harness extracts run_app unchanged and translates only host syscalls.
baseline=subprocess.run(['python3',str(ROOT/'tools/test_native_process.py')],cwd=ROOT,capture_output=True,text=True,timeout=30)
assert baseline.returncode==0,baseline.stderr
base=json.loads((ROOT/'sources/native-process-tests.json').read_text())
work=ROOT/'work/process-integration'
code=r'''
#define _POSIX_C_SOURCE 200809L
#include <signal.h>
#include <unistd.h>
#include <sys/wait.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
static volatile sig_atomic_t stopped;
static void stop(int signal_number) { (void)signal_number; stopped=1; }
static int mark(const char *name) {
 FILE *file=fopen(name,"w"); if(!file)return 80;
 if(fputs("closed\n",file)<0){fclose(file);return 81;}
 return fclose(file)?82:0;
}
int main(void) {
 struct sigaction action; memset(&action,0,sizeof action); action.sa_handler=stop;
 sigemptyset(&action.sa_mask); if(sigaction(SIGTERM,&action,0))return 83;
 char cwd[512];if(!getcwd(cwd,sizeof cwd))return 84;
 pid_t child=-1;
 if(strstr(cwd,"group-cooperative")) {
  child=fork();if(child<0)return 85;
  if(child==0){while(!stopped)pause();return mark("helper.closed");}
 }
 while(!stopped)pause();
 if(child>0){int status;pid_t waited;do{waited=waitpid(child,&status,0);}while(waited<0&&errno==EINTR);
  if(waited!=child||!WIFEXITED(status)||WEXITSTATUS(status))return 86;}
 return mark("app.closed");
}
'''
source=work/'cooperative.c';source.write_text(code);rows=[]
for name,markers in [('cooperative',['app.closed']),('group-cooperative',['app.closed','helper.closed'])]:
 folder=work/name;folder.mkdir(exist_ok=True)
 for marker in markers:
  path=folder/marker
  if path.exists():path.unlink()
 subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(source),'-o',str(folder/'app')],check=True)
 result=subprocess.run([str(work/'runner'),str(folder),'1'],capture_output=True,text=True,check=True,timeout=8)
 assert tuple(map(int,result.stdout.split()))==(0,1,-1,10),(name,result.stdout)
 assert all((folder/marker).read_text()=='closed\n' for marker in markers)
 rows.append({'case':name,'clean_exit':True,'stop_forwarded':True,'cleanup_markers':markers,'direct_child_reaped':True,'helper_reaped_by_app':len(markers)==2})
report={'all_passed':True,'physical_device_access':False,'function_sha256':base['function_sha256'],'baseline_report_sha256':hashlib.sha256((ROOT/'sources/native-process-tests.json').read_bytes()).hexdigest(),'cases':rows,'limits':['Real Linux host fork/exec/process-group signal/wait using unchanged launcher run_app C function and translated syscall boundary.','Cooperative test apps close resources and explicitly reap their helper; ignoring signals/detached background apps remain unsupported.','Does not qualify ARM signal ABI, Sony IPC, filesystem unmount or actual USB/display handoff.']}
(ROOT/'sources/native-cooperative-process-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
