"""Exercise the actual owner's scoped packet membership with modeled syscalls.

No sockets or devices are opened. This tests resource ownership, not RF reception.
"""
import hashlib
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'runtime/apps/wireless-remote/rf_owner.c'
text = source.read_text()
start = text.index('#include <net/if.h>')
end = text.index('/* Only the managed owner loop', start)
helper = text[start:end]
controller_start = text.index('static int remote_controller_step(')
controller_end = text.index('\n#endif\n#ifndef XNOW_REMOTE_POWER_OFF', controller_start)
controller = text[controller_start:controller_end]
out = ROOT / 'work/pairing-rx-filter-tests' / str(time.time_ns())
out.mkdir(parents=True)
harness = r'''
#define _DEFAULT_SOURCE
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
extern int owner_fcntl(int,int,...) __asm__("fcntl");
HELPER
static int failure, opens, options, closes, refs;
int socket(int family,int kind,int protocol){
 assert(family==AF_PACKET&&kind==SOCK_DGRAM&&protocol==0);
 opens++;return failure==1?-1:19;
}
int owner_fcntl(int fd,int command,...){
 va_list args;va_start(args,command);int flags=va_arg(args,int);va_end(args);
 assert(fd==19&&command==F_SETFD&&flags==FD_CLOEXEC);
 return failure==2?-1:0;
}
int shared_stock_ioctl(int fd,unsigned long request,...){
 va_list args;va_start(args,request);struct ifreq *p=va_arg(args,struct ifreq *);va_end(args);
 assert(fd==19&&!strcmp(p->ifr_name,"eth0"));
 if(request==SIOCGIFFLAGS){p->ifr_flags=IFF_UP|IFF_PROMISC;return 0;}
 assert(request==SIOCGIFINDEX);
 p->ifr_ifindex=failure==4?0:7;return failure==3?-1:0;
}
int shared_stock_setsockopt(int fd,int level,int option,const void *payload,socklen_t size){
 assert(fd==19&&level==SOL_PACKET&&option==PACKET_ADD_MEMBERSHIP);
 assert(size==sizeof(struct packet_mreq));const struct packet_mreq *p=payload;
 assert(p->mr_ifindex==7&&p->mr_type==PACKET_MR_PROMISC&&p->mr_alen==0);
 for(unsigned i=0;i<sizeof p->mr_address;i++)assert(!p->mr_address[i]);
 options++;if(failure==5)return -1;refs++;return 0;
}
int close(int fd){assert(fd==19);closes++;refs=0;return failure==6?-1:0;}
static void helper_cases(void){
 for(int f=1;f<=5;f++){
  failure=f;opens=options=closes=refs=0;
  int expected=f==1?-4101:f==5?-4103:-4102;
  assert(shared_rx_socket_open()==expected&&shared_rx_socket==-1&&!refs);
  assert(opens==1&&closes==(f!=1));
  assert(!shared_rx_socket_close()&&closes==(f!=1));
 }
 failure=0;opens=options=closes=refs=0;
 for(int i=0;i<20;i++){
  assert(!shared_rx_socket_open()&&refs==1&&shared_rx_interface_flags==112);
  assert(!shared_rx_socket_open()&&refs==1&&opens==i+1&&options==i+1);
  assert(!shared_rx_socket_close()&&!refs&&closes==i+1);
  assert(!shared_rx_socket_close()&&closes==i+1);
 }
 assert(!shared_rx_socket_open());failure=6;
 assert(shared_rx_socket_close()==-1&&shared_rx_socket==-1&&!refs);
 assert(!shared_rx_socket_close());
}
#define XNOW_REMOTE_MANAGED
#include "runtime/platform/espnow/xnow_full_control.h"
static struct xnow_full_control owner_control;
static unsigned pairing_listener;
static int sleep_called,stop_called,step_called;
static int restore_shared_sleep(struct xnow_full_control *c,void *p){
 (void)p;
 if(c->session.phase==XNOW_SESSION_STOPPING&&!c->endpoint_ready&&
    !c->job.pid&&!c->session.pending&&c->session.next==XNOW_SESSION_RELEASE)
  assert(shared_rx_socket<0);
 sleep_called++;return 0;
}
static int power_off_admission(void *p){(void)p;return 0;}
static int wr_radio_stop_step(struct xnow_full_control *c,void *p,int (*guard)(void *)){
 (void)c;(void)p;(void)guard;stop_called++;return 0;
}
int xnow_full_control_step(struct xnow_full_control *c){(void)c;step_called++;return 0;}
CONTROLLER
int main(void){
 helper_cases();failure=0;
 for(int gate=0;gate<5;gate++){
  memset(&owner_control,0,sizeof owner_control);
  owner_control.session.phase=XNOW_SESSION_STOPPING;
  owner_control.session.next=XNOW_SESSION_RELEASE;
  owner_control.stop_requested=1;
  if(gate==1)owner_control.endpoint_ready=1;
  if(gate==2)owner_control.job.pid=42;
  if(gate==3)owner_control.session.pending=XNOW_SESSION_RELEASE;
  if(gate==4)owner_control.session.next=XNOW_SESSION_VERIFY_STOCK;
  assert(!shared_rx_socket_open());int before=closes;
  assert(!remote_controller_step(NULL,&owner_control));
  assert(closes==before+(gate==0));
  assert((shared_rx_socket==-1)==(gate==0));
  assert(!shared_rx_socket_close());
 }
 assert(sleep_called==5&&stop_called==5&&!step_called);
 assert(!shared_rx_socket_open());failure=6;
 memset(&owner_control,0,sizeof owner_control);
 owner_control.session.phase=XNOW_SESSION_STOPPING;
 owner_control.session.next=XNOW_SESSION_RELEASE;
 assert(remote_controller_step(NULL,&owner_control)==XNOW_UNCERTAIN);
 assert(owner_control.uncertain&&sleep_called==5&&stop_called==5);
 puts("PAIRING_RX_FILTER_PASS");return 0;
}
'''.replace('HELPER', helper).replace('CONTROLLER', controller)
c = out / 'fixture.c'
c.write_text(harness)
binary = out / 'fixture'
subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-I', str(ROOT), str(c), '-o', str(binary)], check=True)
result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
assert result.returncode == 0 and 'PAIRING_RX_FILTER_PASS' in result.stdout, result.stdout + result.stderr
libs = ROOT / 'work/arm-signal-tests/lib'
arm = out / 'fixture.arm'
subprocess.run(['arm-linux-gnueabi-gcc', '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror',
                '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-march=armv5te', '-marm',
                '-mfloat-abi=soft', '-fno-builtin', '-fno-stack-protector', '-fno-pie',
                '-no-pie', '-nostdlib', '-Wl,--hash-style=sysv,--build-id=none',
                '-I', str(ROOT), str(c), str(ROOT / 'runtime/store/start.c'),
                str(ROOT / 'runtime/store/start.S'), str(libs / 'libc.so.6'),
                str(libs / 'ld-linux.so.3'), '-lgcc', '-o', str(arm)], check=True)
target = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libs / 'ld-linux.so.3'),
                         '--library-path', str(libs), str(arm)],
                        capture_output=True, text=True, timeout=10)
assert target.returncode == 0 and 'PAIRING_RX_FILTER_PASS' in target.stdout, target.stdout + target.stderr
report = dict(passed=True, device_accessed=False, cycles=20,
              original_libc_arm926=True, host_sanitizers=True,
              source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
              helper_sha256=hashlib.sha256(helper.encode()).hexdigest(),
              socket_protocol_zero=True, close_on_exec=True,
              failures_release_fd=True, repeated_open_does_not_add_reference=True,
              actual_controller_release_gates=True, close_failure_stops_retirement=True,
              limits=['Syscalls are modeled; no physical MAC-filter or reception proof.',
                      'Controller branch executes; sleep/manager callbacks are fixtures.'])
(out / 'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
