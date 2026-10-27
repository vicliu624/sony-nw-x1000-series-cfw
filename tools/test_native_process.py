"""Host Linux process integration of the unchanged launcher run_app C function.

Real fork/exec/wait/signals; syscall numbers translated at the host boundary.
No Sony executable, device node, mount or firmware operation is executed.
"""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'runtime/native/platform_arm.c').read_text()
function = source[source.index('static int run_app('):source.index('static int native(')]
work = ROOT / 'work/process-integration'
work.mkdir(parents=True, exist_ok=True)
prefix = r'''
#define _GNU_SOURCE
#include <unistd.h>
#include <sys/wait.h>
#include <signal.h>
#include <errno.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static volatile sig_atomic_t stop_requested;
struct app { char *folder; };
static int join(char *out,const char *dir,const char *name) {
 return snprintf(out,256,"%s/%s",dir,name)>=256;
}
static long host_call(int n,long a,long b,long c) {
 long r;
 switch(n) {
 case 1: _exit((int)a);
 case 2: r=fork(); break;
 case 57: r=setpgid((pid_t)a,(pid_t)b); break;
 case 12: r=chdir((const char*)a); break;
 case 11: r=execve((const char*)a,(char*const*)b,(char*const*)c); break;
 case 114: r=waitpid((pid_t)a,(int*)b,(int)c); break;
 case 37: r=kill((pid_t)a,(int)b); break;
 case 162: r=nanosleep((const struct timespec*)a,(struct timespec*)b); break;
 default: abort();
 }
 return r<0?-errno:r;
}
#define S(n,a,b,c) host_call(n,(long)(a),(long)(b),(long)(c))
'''
suffix = r'''
static void stop(int sig) { (void)sig; stop_requested=1; }
int main(int argc,char **argv) {
 if(argc!=3)return 64;
 struct app a={argv[1]}; char *env[]={"HB_PROCESS_TEST=present",NULL};
 if(atoi(argv[2])) { signal(SIGALRM,stop); alarm(1); }
 int status=run_app(&a,env); alarm(0);
 int stray; errno=0; int remaining=waitpid(-1,&stray,WNOHANG);
 printf("%d %d %d %d\n",status,(int)stop_requested,remaining,errno);
 return 0;
}
'''
harness = work / 'process.c'
harness.write_text(prefix + function + suffix)
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(harness),'-o',str(work/'runner')],check=True)
child = work / 'child.c'
child.write_text(r'''
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv) {
 char cwd[256];
 if(argc!=1 || !getcwd(cwd,sizeof cwd))return 91;
 if(strncmp(argv[0],cwd,strlen(cwd)) || strcmp(argv[0]+strlen(cwd),"/app"))return 92;
 if(!getenv("HB_PROCESS_TEST"))return 93;
 if(strstr(cwd,"running"))for(;;)pause();
 return 23;
}
''')
cases=[]
for name,expected,interrupted in [('normal',23<<8,0),('bad-exec',127<<8,0),('missing-dir',126<<8,0),('running',15,1)]:
    folder=work/name
    if name!='missing-dir':
        folder.mkdir(exist_ok=True)
        if name=='bad-exec':
            (folder/'app').write_bytes(b'not an ELF\n')
            (folder/'app').chmod(0o755)
        else:
            subprocess.run(['gcc','-O2',str(child),'-o',str(folder/'app')],check=True)
    result=subprocess.run([str(work/'runner'),str(folder),str(interrupted)],capture_output=True,text=True,check=True,timeout=6)
    status,stopped,remaining,error=map(int,result.stdout.split())
    assert (status,stopped,remaining,error)==(expected,interrupted,-1,10),(name,result.stdout)
    cases.append({'case':name,'wait_status':status,'stop_requested':bool(stopped),'no_unreaped_children':True})
report={'scope':'Unmodified run_app source under host Linux with translated syscall boundary; real child processes, not ARM/Sony integration',
        'runtime_source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'function_sha256':hashlib.sha256(function.encode()).hexdigest(),'cases':cases,
        'physical_device_access':False,'Sony_handoff_validated':False}
(ROOT/'sources/native-process-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
