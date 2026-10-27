"""Native control loop plus real display adapter with virtual OABI devices."""
from pathlib import Path
import runpy,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
base=runpy.run_path(str(ROOT/'tools/test_native_loop.py'))
work=ROOT/'work/native-display-loop-tests';work.mkdir(exist_ok=True)
prefix=r'''
#include <assert.h>
#include <string.h>
#include "frontend.h"
static int stop_requested,count,rejected,scenario,owned,acquires,releases,runs,scans,event,error_message;
struct app{int unused;};static struct app apps[1];
static unsigned short canvas[240*432],mapped[0xc0000/2];
static int maps,unmaps,submits,fb_open,touch_open;
static int signals(void){return 0;}
static int scan(const char*root){assert(!strcmp(root,"fixture"));count=1;scans++;return 0;}
static void logtext(int fd,const char*s){(void)fd;(void)s;}
static void draw(struct hb_frontend*s,const char*m){assert(owned);(void)s;canvas[0]=0x1234;if(!strcmp(m,"APP ERROR - RETURNED TO LIST"))error_message=1;}
static int verified(struct app*a){(void)a;assert(owned);return scenario!=1;}
static int run_app(struct app*a,char**env){(void)a;(void)env;assert(!owned&&!fb_open&&!touch_open&&maps==unmaps);runs++;if(scenario==4)stop_requested=1;return scenario==2?256:0;}
static long x1000_oabi_call(long n,long a,long b,long c,long d,long e,long f){
 (void)d;(void)f;
 if(n==5){if(!strcmp((char*)a,"/dev/fb/0")){assert(!owned&&!fb_open&&!touch_open);acquires++;owned=fb_open=1;return 10;}assert(!strcmp((char*)a,"/dev/icx_touch_screen"));touch_open=1;return 70;}
 if(n==6){if(a==10){assert(fb_open);fb_open=owned=0;}else{assert(a==70&&touch_open);touch_open=0;releases++;}return 0;}
 if(n==192){assert(e==10&&b==0xc0000&&fb_open);maps++;return (long)mapped;}
 if(n==91){assert((void*)a==mapped&&b==0xc0000);unmaps++;return 0;}
 if(n==168){struct pollfd{int fd;short events,revents;}*p=(void*)a;assert(p->fd==70&&owned&&event<4);p->revents=1;return 1;}
 assert(n==54);unsigned*out=(void*)c;
 if((unsigned long)b==0x4602){memset(out,0,128);out[5]=0xc0000;out[11]=480;return 0;}
 if((unsigned long)b==0x4600){memset(out,0,160);out[0]=scenario==3&&acquires==2?239:240;out[1]=432;out[6]=16;out[8]=11;out[9]=5;out[11]=5;out[12]=6;out[15]=5;return 0;}
 if((unsigned long)b==0x80044e04){assert(out[0]==0&&out[1]==33);return 0;}
 if((unsigned long)b==0x5404)return 0;
 if((unsigned long)b==0x80044e00){out[1]=0;out[2]=1;return 0;}
 if((unsigned long)b==0x40044e01){assert(out[0]==1&&out[1]==1&&out[2]==255&&out[3]==0&&!out[4]&&!out[5]);assert(mapped[0]==0x1234);submits++;return 0;}
 assert(a==70&&(unsigned long)b==0x80045401u);unsigned char*p=(void*)c;unsigned x=800,y=event<2?4500:380;p[1]=(event%2)==0;p[2]=x>>8;p[3]=x;p[4]=y>>8;p[5]=y;event++;return 0;
}
#define S(n,a,b,c) x1000_oabi_call(n,(long)(a),(long)(b),(long)(c),0,0,0)
static int error(long r){return r<0&&r>=-4095;}
#include "display_touch.inc"
'''
suffix=base['suffix'].replace('owned=acquires=', 'maps=unmaps=submits=fb_open=touch_open=0;owned=acquires=').replace('assert(!owned);','assert(!owned&&!fb_open&&!touch_open&&maps==unmaps&&submits>0);')
generated=work/'test.c';generated.write_text(prefix+base['function']+suffix)
common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(ROOT/'runtime/native'),str(generated),str(ROOT/'runtime/native/frontend.c')]
subprocess.run(['gcc','-O2',*common,'-o',str(work/'test')],check=True);subprocess.run([str(work/'test')],check=True,timeout=10)
lib=ROOT/'work/arm-signal-tests/lib'
subprocess.run(['arm-linux-gnueabi-gcc','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*common,str(ROOT/'runtime/store/start.c'),str(ROOT/'runtime/store/start.S'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(work/'test.arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'trace':run.stderr,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/native/platform_arm.c','runtime/native/display_touch.inc','runtime/native/frontend.c','runtime/native/frontend.h']},'cases':base['report']['cases'],'limits':['Actual native loop, display adapter and frontend under host and original-libc ARM/QEMU.','Virtual OABI device calls; scan/verification/process/signal-installation boundaries remain simulated.','No physical drivers, Sony IPC or actual display/USB handoff qualification.']}
(ROOT/'sources/native-display-loop-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Native loop with actual display adapter: five host/ARM virtual-device cases passed.')
