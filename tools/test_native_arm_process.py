"""Real ARM launcher fork/wait/exec against host-only child fixtures."""
from pathlib import Path
import runpy,subprocess,json,hashlib,time,signal,os
ROOT=Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT/'tools/test_native_arm_signals.py'))
subprocess.run(['python3',str(ROOT/'tools/test_native_process.py')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
work=ROOT/'work/arm-process-tests';work.mkdir(exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
source=(ROOT/'runtime/native/platform_arm.c').read_text()
handlers=source[source.index('static void stopped('):source.index('static int verified(')]
function=source[source.index('static int run_app('):source.index('static int native(')]
prefix='''
extern long x1000_oabi_call(long,long,long,long,long,long,long);
extern void x1000_rt_sigreturn(void);
#define S(n,a,b,c) x1000_oabi_call(n,(long)(a),(long)(b),(long)(c),0,0,0)
static volatile int stop_requested;
struct app {char *folder;};
static int join(char*out,const char*a,const char*b){unsigned n=0,m=0;while(a[n])n++;while(b[m])m++;if(n+m+2>256)return -1;for(unsigned i=0;i<n;i++)out[i]=a[i];out[n++]='/';for(unsigned i=0;i<=m;i++)out[n+i]=b[i];return 0;}
'''
suffix=r'''
extern int printf(const char*,...);
int main(int argc,char**argv){
 if(argc!=2||signals())return 64;
 struct app a={argv[1]};char*env[]={"HB_PROCESS_TEST=present",0};
 int status=run_app(&a,env);int stray=0;
 long remaining=S(114,-1,&stray,1);
 printf("%d %d %ld\n",status,(int)stop_requested,remaining);
 return 0;
}
'''
generated=work/'runner.c';generated.write_text(prefix+handlers+function+suffix)
sources=[str(generated),'runtime/native/syscalls.S','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(work/'runner.arm')],cwd=ROOT,check=True)
rows=[]
for name,expected in [('normal',23<<8),('bad-exec',127<<8),('missing-dir',126<<8)]:
 folder=ROOT/'work/process-integration'/name
 run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(work/'runner.arm'),str(folder)],capture_output=True,text=True,timeout=10)
 assert run.returncode==0,(name,run.returncode,run.stderr)
 assert tuple(map(int,run.stdout.split()))==(expected,0,-10),(name,run.stdout,run.stderr)
 assert not any(c in run.stderr.lower() for c in ('socket(','connect(','/dev/fb','/dev/icx_touch_screen'))
 rows.append({'case':name,'wait_status':expected,'trace':run.stderr,'no_unreaped_direct_child':True})
subprocess.run(['python3',str(ROOT/'tools/test_native_cooperative_process.py')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
folder=ROOT/'work/process-integration/cooperative';marker=folder/'app.closed';marker.unlink(missing_ok=True)
process=subprocess.Popen(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(work/'runner.arm'),str(folder)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
 ready=False;deadline=time.monotonic()+5
 while time.monotonic()<deadline and process.poll() is None:
  children=Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
  for child in children:
   try:
    executable=Path(f'/proc/{child}/exe').resolve()
    status=Path(f'/proc/{child}/status').read_text()
    caught=int(next(line.split()[1] for line in status.splitlines() if line.startswith('SigCgt:')),16)
    if executable==folder/'app' and caught&(1<<(signal.SIGTERM-1)):ready=True
   except (FileNotFoundError,ProcessLookupError):pass
  if ready:break
  time.sleep(.01)
 assert ready,'Cooperative child did not reach installed termination handler'
 process.send_signal(signal.SIGTERM)
 stdout,stderr=process.communicate(timeout=8)
 assert process.returncode==0 and tuple(map(int,stdout.split()))==(0,1,-10),(process.returncode,stdout,stderr)
 assert marker.read_text()=='closed\n'
 rows.append({'case':'ARM parent forwards SIGTERM to cooperative host C child','wait_status':0,'stop_requested':True,'cleanup_marker':True,'no_unreaped_direct_child':True,'trace':stderr})
finally:
 if process.poll() is None:
  process.kill();process.communicate(timeout=5)
# Host-only emulator adapter: do not install this shim on a player.
hello=ROOT/'work/hello-app/package/app'
hello_report=json.loads((ROOT/'sources/native-hello-app-build.json').read_text())
assert hashlib.sha256(hello.read_bytes()).hexdigest()==hello_report['sha256']
folder=work/'emulated-arm-child';folder.mkdir(exist_ok=True)
arguments=['/usr/bin/qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(hello)]
shim=folder/'adapter.c'
shim.write_text('#include <unistd.h>\nint main(void){char *args[]={'+','.join(json.dumps(a) for a in arguments)+',0};execv(args[0],args);return 125;}\n')
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(shim),'-o',str(folder/'app')],check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(work/'runner.arm'),str(folder)],capture_output=True,text=True,timeout=15)
assert run.returncode==0 and run.stdout=='Hello from a native Sony NW-X1000 homebrew app.\n0 0 -10\n',(run.returncode,run.stdout,run.stderr)
assert not any(c in run.stderr.lower() for c in ('socket(','connect(','/dev/fb','/dev/icx_touch_screen'))
rows.append({'case':'ARM parent launches real ARM Hello through explicit host QEMU adapter','wait_status':0,'child_sha256':hello_report['sha256'],'child_ARM_code_executed':True,'host_emulator_adapter_used':True,'no_unreaped_direct_child':True,'trace':run.stderr})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'function_sha256':hashlib.sha256(function.encode()).hexdigest(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/native/platform_arm.c','runtime/native/syscalls.S','runtime/store/start.c','runtime/store/start.S']},'cases':rows,'limits':['Parent runs actual ARM launcher run_app and OABI fork/exec/wait under QEMU with original libc.','Base success/cooperative children are host C fixtures; real ARM Hello case uses explicit host QEMU exec adapter, not native same-kernel ARM exec.','No display/touch, USB, Sony kernel/IPC or hardware qualification.']}
(ROOT/'sources/native-arm-process-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('ARM parent real process fork/exec/wait: normal, bad-exec and missing-dir passed.')
