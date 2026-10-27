"""Stock-libc process integration, derived from test_native_full_loop.py; virtual devices only."""
from pathlib import Path
import hashlib,io,json,os,shutil,signal,subprocess,tarfile,tempfile,time
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1]
if not __debug__:raise RuntimeError('Run without Python optimization')
work=ROOT/'work/posix-full-loop-tests';work.mkdir(exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
packed=ROOT/'work/upg-jp/verified-3.bin'
assert hashlib.sha256(packed.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(packed.read_bytes()),mode='r:gz') as archive:
 for deployed,original in (('libc.so.6','libc-2.3.3.so'),('ld-linux.so.3','ld-2.3.3.so')):
  assert (lib/deployed).read_bytes()==archive.extractfile('./lib/'+original).read()
hello_report=verify_report(ROOT,'sources/native-hello-app-build.json')
assert (ROOT/hello_report['artifact']).read_bytes()==(ROOT/'work/hello-app/package/app').read_bytes()
# Device names below are always intercepted. An unexpected /dev open aborts.
prefix='''
#include <assert.h>
#include <string.h>
extern long __real_x1000_oabi_call(long,long,long,long,long,long,long);
extern int hb_entry(unsigned *);
static int owned,acquires,releases,event,maps,unmaps,submits,fb_open,touch_open;
static unsigned short mapped[0xc0000/2];
static unsigned char owned_files[256];
static int owned_file_count,reaped_count,last_wait_status,group_signals;
static long direct_child;
'''+ '#define LOADER '+json.dumps(str(lib/'ld-linux.so.3'))+'\n#define LIBRARY '+json.dumps(str(lib))+'\n'
fixture=r'''
long __wrap_x1000_oabi_call(long n,long a,long b,long c,long d,long e,long f) {
 if(n==5&&!strncmp((char*)a,"/dev/",5)) {
  if(!strcmp((char*)a,"/dev/input/event0"))return -2;
  if(!strcmp((char*)a,"/dev/fb/0")) {
   assert(!owned&&!fb_open&&!touch_open);acquires++;owned=fb_open=1;return 10;
  }
  assert(!strcmp((char*)a,"/dev/icx_touch_screen")&&owned&&fb_open&&!touch_open);
  touch_open=1;return 70;
 }
 if(n==6&&(a==10||a==70)) {
  if(a==10){assert(fb_open);fb_open=0;}else{assert(touch_open);touch_open=0;}
  if(!fb_open&&!touch_open){owned=0;releases++;}return 0;
 }
 if(n==5) {
  long fd=__real_x1000_oabi_call(n,a,b,c,d,e,f);
  if(fd>=0){assert(fd<256&&fd!=10&&fd!=70&&!owned_files[fd]);owned_files[fd]=1;owned_file_count++;}
  return fd;
 }
 if(n==6) {
  assert(a>=0&&a<256&&owned_files[a]);
  long result=__real_x1000_oabi_call(n,a,b,c,d,e,f);
  assert(result==0);owned_files[a]=0;owned_file_count--;return result;
 }
 if(n==192&&e==10){assert(owned&&b==0xc0000);maps++;return (long)mapped;}
 if(n==91&&a==(long)mapped){assert(owned&&b==0xc0000);unmaps++;return 0;}
 if(n==168) {
  struct {int fd;short events,revents;}*pollfd=(void*)a;
  assert(pollfd->fd==70&&owned&&event<4&&b==1&&c==50);pollfd->revents=1;return 1;
 }
 if(n==54) {
  assert(owned&&(a==10||a==70));unsigned *out=(void*)c;
  if((unsigned long)b==0x4602){memset(out,0,128);out[5]=0x120000;out[11]=480;return 0;}
  if((unsigned long)b==0x4600){memset(out,0,160);out[0]=240;out[1]=432;out[6]=16;out[8]=11;out[9]=5;out[11]=5;out[12]=6;out[15]=5;return 0;}
  if((unsigned long)b==0x80044e04){assert(out[0]==0&&out[1]==33);return 0;}
  if((unsigned long)b==0x5404)return 0;
  if((unsigned long)b==0x80044e00){assert(out[0]==0);out[1]=0;out[2]=1;return 0;}
  if((unsigned long)b==0x40044e01){assert(out[0]==1&&out[1]==1&&out[2]==255&&out[3]==0&&!out[4]&&!out[5]&&mapped[0]);submits++;return 0;}
  assert((unsigned long)b==0x80045401&&event<4);
  unsigned x=event<2?80:30,y=event<2?60:400;
  unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;
  unsigned char *packet=(void*)c;memset(packet,0,16);packet[1]=(unsigned char)(event%2==0);
  packet[2]=(unsigned char)(rx>>8);packet[3]=(unsigned char)rx;
  packet[4]=(unsigned char)(ry>>8);packet[5]=(unsigned char)ry;event++;return 0;
 }
 if(n==2) {long pid=__real_x1000_oabi_call(n,a,b,c,d,e,f);if(pid>0)direct_child=pid;return pid;}
 if(n==114) {
  long result=__real_x1000_oabi_call(n,a,b,c,d,e,f);
  if(result>0){assert(result==direct_child);reaped_count++;last_wait_status=*(int*)b;}
  return result;
 }
 if(n==37){assert(a==-direct_child&&b==15&&direct_child>0);group_signals++;return __real_x1000_oabi_call(n,a,b,c,d,e,f);}
 if(n==11) {
  assert(!owned&&!fb_open&&!touch_open&&maps==unmaps&&!owned_file_count);
  char *args[]={"/usr/bin/qemu-arm","-cpu","arm926","-strace",LOADER,"--library-path",LIBRARY,(char*)a,0};
  return __real_x1000_oabi_call(11,(long)args[0],(long)args,c,0,0,0);
 }
 return __real_x1000_oabi_call(n,a,b,c,d,e,f);
}
int hb_arm_selftest(void){return 0;}
int main(int argc,char **argv) {
 assert(argc==3);int expected=argv[2][0]=='1',stop_case=argv[2][0]=='s';
 unsigned stack[]={3,(unsigned)argv[0],(unsigned)"--native",(unsigned)argv[1],0,0};
 assert(hb_entry(stack)==0&&event==(stop_case?2:4));
 assert(acquires==1+expected&&releases==1+expected&&maps==1+expected&&unmaps==1+expected);
 assert(!owned&&!fb_open&&!touch_open&&submits>=(stop_case?2:3)&&!owned_file_count);
 assert(reaped_count==(expected||stop_case)&&last_wait_status==0);
 assert(group_signals==(stop_case?1:0));
 int status;assert(__real_x1000_oabi_call(114,-1,(long)&status,1,0,0,0)==-10);
 return 0;
}
'''
wrappers=ROOT/'tools/fixtures/posix_loop_wrappers.inc'
generated=work/'modular-test.c';generated.write_text(prefix+fixture+wrappers.read_text(encoding='utf-8-sig'))
modules=['frontend.c','sha256.c','platform_arm.c','app_catalog.c','linux_files.c','linux_file_ops_posix.c','app_process.c','home_key.c','linux_process_posix.c','linux_devices.c','linux_device_io_posix.c','linux_signals_posix.c','syscalls.S']
sources=[str(generated)]+['runtime/native/'+name for name in modules]+['runtime/store/start.c','runtime/store/start.S']
artifact=work/'modular-test.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-DHB_USE_POSIX_FILES','-DHB_USE_POSIX_DEVICE_IO','-DHB_USE_POSIX_DEVICE_IO','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=x1000_oabi_call','-Wl,--wrap=ioctl','-Wl,--wrap=mmap64','-Wl,--wrap=munmap','-Wl,--wrap=poll','-Wl,--wrap=open64','-Wl,--wrap=close','-Wl,--wrap=fork','-Wl,--wrap=waitpid','-Wl,--wrap=kill','-Wl,--wrap=execve',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='modular-apps-',dir=work) as temporary:
 apps=Path(temporary);shutil.copytree(ROOT/'work/hello-app/package',apps/'hello')
 def run(expected):
  return subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact),str(apps),expected],capture_output=True,text=True,timeout=20)
 accepted=run('1')
 assert accepted.returncode==0,(accepted.returncode,accepted.stdout,accepted.stderr[-16000:])
 assert accepted.stdout=='Hello from a native Sony NW-X1000 homebrew app.\n',accepted.stdout
 assert 'execve(' in accepted.stderr and ('wait4(' in accepted.stderr or 'waitpid(' in accepted.stderr),accepted.stderr
 damaged=bytearray((apps/'hello/app').read_bytes());damaged[-1]^=1;(apps/'hello/app').write_bytes(damaged)
 refused=run('0')
 assert refused.returncode==0 and not refused.stdout,(refused.returncode,refused.stdout,refused.stderr[-16000:])
 assert 'execve(' not in refused.stderr.lower(),refused.stderr

child_source=ROOT/'tools/fixtures/cooperative_app.c';child=work/'cooperative.arm'
child_sources=[str(child_source),'runtime/native/linux_process.c','runtime/native/linux_signals_posix.c','runtime/native/syscalls.S','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-DHB_USE_POSIX_FILES','-DHB_USE_POSIX_DEVICE_IO','-DHB_USE_POSIX_DEVICE_IO','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*child_sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(child)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='cooperative-apps-',dir=work) as temporary:
 apps=Path(temporary);folder=apps/'cooperative';folder.mkdir();app=folder/'app';shutil.copyfile(child,app)
 data=app.read_bytes();digest=hashlib.sha256(data).hexdigest()
 (folder/'app.ini').write_text('api=1\nid=cooperative\nname=Cooperative Test\nversion=0.0.0\ntarget=sony-nw-x1000-jp\nexec=app\nbytes='+str(len(data))+'\nsha256='+digest+'\n')
 process=subprocess.Popen(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact),str(apps),'s'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 known_children=[]
 try:
  deadline=time.monotonic()+8
  while process.poll() is None and time.monotonic()<deadline:
   try:
    if (folder/'ready').read_bytes()==b'OK':break
   except FileNotFoundError:pass
   time.sleep(.01)
  assert (folder/'ready').read_bytes()==b'OK'
  children=Path(f'/proc/{process.pid}/task/{process.pid}/children')
  known_children=children.read_text().split() if children.exists() else []
  process.send_signal(signal.SIGTERM)
  stop_stdout,stop_stderr=process.communicate(timeout=10)
  assert process.returncode==0 and not stop_stdout,(process.returncode,stop_stdout,stop_stderr[-18000:])
  assert (folder/'closed').read_bytes()==b'OK'
  assert stop_stderr.lower().count('sigreturn(')>=2
 finally:
  children=Path(f'/proc/{process.pid}/task/{process.pid}/children')
  remaining=children.read_text().split() if children.exists() else []
  for value in set(known_children+remaining):
   try:
    command=Path('/proc')/value/'cmdline'
    if command.exists() and str(app).encode() in command.read_bytes():os.kill(int(value),signal.SIGKILL)
   except (ProcessLookupError,FileNotFoundError):pass
  if process.poll() is None:process.kill();process.communicate(timeout=5)
tracked=[Path(__file__),wrappers,generated,child_source,child,packed,ROOT/'sources/native-hello-app-build.json',ROOT/'work/hello-app/package/app',ROOT/'runtime/native/font.inc',lib/'libc.so.6',lib/'ld-linux.so.3']+[ROOT/source for source in sources if not Path(source).is_absolute()]+list((ROOT/'runtime/native').glob('*.h'))
report={'all_bounded_checks_passed':True,'process_backend':'stock-libc POSIX','physical_device_access':False,'C_modules_linked_separately':True,'real_ARM_child_executed':True,'normal_child_releases_before_exec_and_reacquires_after_wait':True,'launcher_owned_files_closed_before_exec_and_on_return':True,'corrupt_payload_blocks_exec_and_allows_return':True,'stdout':accepted.stdout,'trace':accepted.stderr+refused.stderr+stop_stderr,'cooperative_child_stop':{'actual_SIGTERM_to_launcher':True,'child_group_SIGTERM_forwarded':True,'child_cleanup_marker':True,'child_exit_status':0,'direct_child_reaped':True,'ECHILD_after_return':True,'device_reacquires_after_stop':0},'artifact':str(artifact.relative_to(ROOT)),'bytes':artifact.stat().st_size,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'source_hashes':{**hello_report['source_hashes'],**{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}},'limits':['Harness links current launcher C modules with original Sony libc; production ELF has separate ARM adapter checks.', 'Framebuffer/touch calls are virtual, actual file reads/hash/fork/setpgid/wait/signals execute under QEMU.', 'Guest exec explicitly starts nested host QEMU for the known Hello ARM executable; not physical ARM hardware or Sony IPC.', 'Cooperative stop tested after child ready marker; launch-time races, ignored signals and detached/background children not covered.', 'No Sony UI, actual display/touch, USB handoff or return-to-Walkman qualification.']}
(ROOT/'sources/native-posix-full-loop-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('POSIX launcher: ARM Hello/return, corrupt-app rejection and actual SIGTERM cooperative-child cleanup/reap passed.')







