"""Unchanged native loop with explicit simulated hardware/process boundaries."""
from pathlib import Path
import subprocess,hashlib,json,runpy
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/native-loop-tests';work.mkdir(exist_ok=True)
source=(ROOT/'runtime/native/platform_arm.c').read_text();function=source[source.index('static int native('):source.index('int hb_entry(')]
prefix=r'''
#include <assert.h>
#include <string.h>
#include "frontend.h"
static int stop_requested,count,rejected,scenario,owned,acquires,releases,runs,scans,event,error_message;
struct app{int unused;};static struct app apps[1];
struct devices{int touch,failed;};
static int signals(void){return 0;}
static int scan(const char*root){assert(!strcmp(root,"fixture"));count=1;scans++;return 0;}
static int acquire(struct devices*d){assert(!owned);acquires++;d->touch=70;d->failed=0;if(scenario==3&&acquires==2)return -1;owned=1;return 0;}
static void release(struct devices*d){(void)d;assert(owned);owned=0;releases++;}
static void logtext(int fd,const char*s){(void)fd;(void)s;}
static void draw(struct hb_frontend*s,const char*m){assert(owned);(void)s;if(!strcmp(m,"APP ERROR - RETURNED TO LIST"))error_message=1;}
static void present(struct devices*d){(void)d;assert(owned);}
static void flush_pending(struct devices*d){(void)d;assert(owned);}
static int verified(struct app*a){(void)a;assert(owned);return scenario!=1;}
static int run_app(struct app*a,char**env){(void)a;(void)env;assert(!owned);runs++;if(scenario==4)stop_requested=1;return scenario==2?256:0;}
static long simulated(int n,long a,long b,long c){
 if(n==168){struct pollfd{int fd;short events,revents;}*p=(void*)a;assert(p->fd==70&&owned&&event<4);p->revents=1;return 1;}
 assert(n==54&&a==70&&(unsigned long)b==0x80045401u);unsigned char*p=(void*)c;unsigned x=800,y=event<2?4500:380;p[1]=(event%2)==0;p[2]=x>>8;p[3]=x;p[4]=y>>8;p[5]=y;event++;return 0;
}
#define S(n,a,b,c) simulated(n,(long)(a),(long)(b),(long)(c))
'''
suffix=r'''
int main(void){
 for(scenario=0;scenario<5;scenario++){
  owned=acquires=releases=runs=scans=event=error_message=stop_requested=0;
  int result=native("fixture",0);
  assert(result==(scenario==3?2:0));assert(!owned);
  assert(runs==(scenario==1?0:1));
  assert(acquires==(scenario==1||scenario==4?1:2));
  assert(releases==(scenario==0||scenario==2?2:1));
  assert(scans==(scenario==1||scenario==4?1:2));
  assert(event==(scenario==3||scenario==4?2:4));
  assert(error_message==(scenario==2));
 }
 return 0;
}
'''
generated=work/'test.c';generated.write_text(prefix+function+suffix)
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'runtime/native'),str(generated),str(ROOT/'runtime/native/frontend.c'),'-o',str(work/'test')],check=True)
subprocess.run([str(work/'test')],check=True,timeout=10)
runpy.run_path(str(ROOT/'tools/test_native_arm_signals.py'))
lib=ROOT/'work/arm-signal-tests/lib'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-I'+str(ROOT/'runtime/native'),str(generated),str(ROOT/'runtime/native/frontend.c'),str(ROOT/'runtime/store/start.c'),str(ROOT/'runtime/store/start.S'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(work/'test.arm')],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stderr)
assert not any(c in run.stderr.lower() for c in ('socket(','connect(','/dev/fb','/dev/icx_touch_screen'))
report={'all_bounded_checks_passed':True,'physical_device_access':False,'ARM_QEMU_exit':run.returncode,'trace':run.stderr,'native_function_sha256':hashlib.sha256(function.encode()).hexdigest(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/native/platform_arm.c','runtime/native/frontend.c','runtime/native/frontend.h']},'cases':['tap app, release, child exit, reacquire, tap Walkman, release','verification failure stays in list','child failure returns to list with error','reacquire failure returns error without owned resources','termination during child skips reacquire and returns'],'limits':['Unchanged native control loop and actual touch decoder/state machine, host C and original-libc ARM/QEMU execution.','Display, scan, digest check, signal installation and child execution boundaries explicitly simulated.','No actual hardware drivers, ARM process or Sony return qualification.']}
(ROOT/'sources/native-loop-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Native list/application/return control loop: five simulated-boundary cases passed.')
