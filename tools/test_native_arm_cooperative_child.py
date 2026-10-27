"""ARM parent termination forwards to real ARM cooperative child via host emulator."""
from pathlib import Path
import runpy,subprocess,json,hashlib,time,signal,os
ROOT=Path(__file__).resolve().parents[1]
base=runpy.run_path(str(ROOT/'tools/test_native_arm_process.py'))
work=ROOT/'work/arm-cooperative-child-tests';work.mkdir(exist_ok=True);lib=base['lib']
source=ROOT/'runtime/native/platform_arm.c';text=source.read_text();handlers=text[text.index('static void stopped('):text.index('static int verified(')]
code='''extern long x1000_oabi_call(long,long,long,long,long,long,long);extern void x1000_rt_sigreturn(void);static volatile int stop_requested;
'''+handlers+r'''
static int mark(const char*p){long fd=x1000_oabi_call(5,(long)p,577,384,0,0,0);if(fd<0)return -1;long wrote=x1000_oabi_call(4,fd,(long)"OK",2,0,0,0);long closed=x1000_oabi_call(6,fd,0,0,0,0,0);return wrote==2&&closed==0?0:-1;}
int main(void){if(signals()||mark("ready"))return 20;while(!stop_requested){long ts[2]={0,10000000};x1000_oabi_call(162,(long)ts,0,0,0,0,0);}return mark("closed")?21:0;}
'''
generated=work/'child.c';generated.write_text(code)
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',str(generated),'runtime/native/syscalls.S','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(work/'child.arm')],cwd=ROOT,check=True)
args=['/usr/bin/qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(work/'child.arm')]
shim=work/'adapter.c';shim.write_text('#include <unistd.h>\nint main(void){char*args[]={'+','.join(json.dumps(a) for a in args)+',0};execv(args[0],args);return 125;}\n')
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(shim),'-o',str(work/'app')],check=True)
for name in ('ready','closed'):(work/name).unlink(missing_ok=True)
process=subprocess.Popen(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(base['work']/'runner.arm'),str(work)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
 deadline=time.monotonic()+8
 while not (work/'ready').exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.01)
 assert (work/'ready').read_bytes()==b'OK'
 process.send_signal(signal.SIGTERM);stdout,stderr=process.communicate(timeout=10)
 assert process.returncode==0 and stdout=='0 1 -10\n',(process.returncode,stdout,stderr[-10000:])
 assert (work/'closed').read_bytes()==b'OK'
 assert stderr.lower().count('rt_sigreturn(')>=2,stderr
 assert not any(c in stderr.lower() for c in ('socket(','connect(','/dev/fb','/dev/icx_touch_screen'))
finally:
 if process.poll() is None:
  children=Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
  for child in children:
   try:os.killpg(int(child),signal.SIGKILL)
   except ProcessLookupError:pass
  process.kill();process.communicate(timeout=5)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'trace':stderr,'ARM_parent_and_child':True,'child_cleanup_marker':True,'parent_stop_flag':True,'direct_child_reaped':True,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/native/platform_arm.c','runtime/native/syscalls.S','runtime/store/start.c','runtime/store/start.S']},'limits':['Explicit host QEMU exec adapter; not same Sony-kernel native execution.','Child is an offline ARM C cooperative fixture, not the production store.','Files ready/closed exist only in project work; no hardware, display or Sony IPC qualification.']}
(ROOT/'sources/native-arm-cooperative-child-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('ARM parent -> SIGTERM -> real ARM child cleanup -> reap passed via explicit host QEMU adapter.')
