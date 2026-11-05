#define _DEFAULT_SOURCE
#include "../runtime/platform/wireless/mode_channel.h"
#include "../runtime/platform/wireless/mode_client.h"
#include "../runtime/platform/wireless/native_permission.h"
#include "../runtime/platform/wireless/native_rf_worker.h"
#include "../runtime/platform/wireless/native_offer.h"
#include "../runtime/platform/wireless/native_delivery.h"
#include "../runtime/platform/wireless/native_publisher.h"
#include "../runtime/platform/player/wireless_host.h"
#include "../runtime/platform/wireless/native_boot.h"
#include "../runtime/platform/wireless/native_retirement.h"
#include "../runtime/apps/wireless-remote/owner_admission.h"
#include <assert.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <poll.h>
#include <errno.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#ifndef __arm__
/* Host-only bridge for the production fixed two-word clock adapter. ARM uses
 * the original libc clock symbol, not the host's timespec layout. */
long x1000_oabi_call(long nr,long clock,long output,long d,long e,long f,long g){
 (void)d;(void)e;(void)f;(void)g;assert(nr==263&&clock==1);
 struct timespec now;if(clock_gettime(CLOCK_MONOTONIC,&now))return -1;
 int *words=(int *)output;words[0]=(int)now.tv_sec;words[1]=(int)now.tv_nsec;return 0;
}
#endif
extern int fixture_mode_fcntl(int,int,...) __asm__("fcntl");
/* Test-link-only scheduling marker: production objects contain no tracing.
 * Hold GUI initialization until the early worker reaches its real poll. */
static pthread_key_t poll_trace;
extern int __real_poll(struct pollfd *,nfds_t,int);
int __wrap_poll(struct pollfd *fds,nfds_t count,int timeout){
 int *report=pthread_getspecific(poll_trace);
 if(report){assert(!pthread_setspecific(poll_trace,0));assert(write(*report,"W",1)==1);}
 return __real_poll(fds,count,timeout);
}
static struct xw_wireless_mode_policy *boot_authority;
/* This transport test supplies an active original owner. Exit denial is
 * exercised separately by test_wireless_auto_exit.py. */
int xw_player_host_original_exiting(void){return 0;}
static int boot_test_bad,boot_test_flag;
static unsigned retirement_state_reads;
static int retirement_modules_clear=1;
static unsigned stop_attempts,stop_accepted;static int stop_backpressure;
int xw_native_rf_stop_request(void){
 stop_attempts++;if(stop_backpressure){stop_backpressure=0;return XW_MODE_PENDING;}
 stop_accepted++;return 0;
}
int xw_native_boot_manager_state(void){retirement_state_reads++;return 2;}
int xw_native_boot_radio_unloaded(void){return retirement_modules_clear;}
int xw_native_boot_observe(struct xw_native_boot_observation *out){
 *out=(struct xw_native_boot_observation){777,2,2,boot_test_bad?0:1,1};return boot_test_bad?XW_MODE_DENIED:0;
}
int xw_native_boot_flag(void){return boot_test_flag;}
int xw_native_rf_image_valid(void){return 1;}
int xw_player_host_wireless_bind(struct xw_wireless_mode_policy *policy){boot_authority=policy;return xw_player_host_wireless_bound(policy);}
static uint32_t u32(const unsigned char *p){uint32_t n=0;for(unsigned i=0;i<4;i++)n|=(uint32_t)p[i]<<(8*i);return n;}
static uint64_t u64(const unsigned char *p){uint64_t n=0;for(unsigned i=0;i<8;i++)n|=(uint64_t)p[i]<<(8*i);return n;}
static void exchange(int fd,unsigned op,uint64_t serial,int mode,unsigned char reply[80]){
 unsigned char raw[32];assert(!xw_mode_request_encode(raw,op,serial,mode));
 assert(send(fd,raw,32,MSG_NOSIGNAL)==32);
 struct pollfd wait={fd,POLLIN,0};assert(poll(&wait,1,3000)==1&&recv(fd,reply,80,0)==80);
 assert(!memcmp(reply,"WMS1",4)&&u32(reply+4)==op&&u64(reply+8)==serial);
 for(unsigned i=72;i<80;i++)assert(!reply[i]);
 struct xw_mode_reply decoded,before;memset(&decoded,0xa5,sizeof decoded);before=decoded;
 assert(xw_mode_reply_decode(&decoded,reply,79,op,serial)==XW_MODE_INVALID&&!memcmp(&decoded,&before,sizeof decoded));
 assert(xw_mode_reply_decode(&decoded,reply,80,op,serial+1)==XW_MODE_STALE&&!memcmp(&decoded,&before,sizeof decoded));
 unsigned char bad[80];memcpy(bad,reply,80);bad[72]=1;
 assert(xw_mode_reply_decode(&decoded,bad,80,op,serial)==XW_MODE_INVALID&&!memcmp(&decoded,&before,sizeof decoded));
 memcpy(bad,reply,80);bad[32]=1;bad[36]=1;
 assert(xw_mode_reply_decode(&decoded,bad,80,op,serial)==XW_MODE_INVALID&&!memcmp(&decoded,&before,sizeof decoded));
 assert(!xw_mode_reply_decode(&decoded,reply,80,op,serial));
 assert(decoded.operation==op&&decoded.serial==serial&&decoded.result==(int32_t)u32(reply+16)&&decoded.generation);
}
static void client(int fd,int proof_writer,int crash){
 unsigned char r[80];exchange(fd,XW_MODE_QUERY,1,0,r);assert((int32_t)u32(r+16)==0&&u32(r+24)==XW_WIRELESS_MODE_ESPNOW);
 exchange(fd,XW_MODE_SELECT,2,XW_WIRELESS_MODE_WIFI,r);assert((int32_t)u32(r+16)==XW_MODE_DENIED&&u32(r+24)==XW_WIRELESS_MODE_ESPNOW);
 exchange(fd,XW_MODE_ACQUIRE,3,XW_WIRELESS_MODE_ESPNOW,r);assert((int32_t)u32(r+16)==0&&u32(r+68)==1&&u64(r+40)==77&&u64(r+48)==1&&u64(r+56)==101);
 if(crash==1){close(fd);_exit(0);}
 if(crash==2){unsigned char forged[32];assert(!xw_mode_request_encode(forged,XW_MODE_RELEASE,4,0));forged[20]=1;assert(send(fd,forged,32,MSG_NOSIGNAL)==32);close(fd);_exit(0);}
 exchange(fd,XW_MODE_ACQUIRE,3,XW_WIRELESS_MODE_ESPNOW,r);assert((int32_t)u32(r+16)==0&&u64(r+48)==1);
 exchange(fd,XW_MODE_ACQUIRE,3,XW_WIRELESS_MODE_WIFI,r);assert((int32_t)u32(r+16)==XW_MODE_STALE&&u64(r+48)==1);
 exchange(fd,XW_MODE_ACQUIRE,4,XW_WIRELESS_MODE_ESPNOW,r);assert((int32_t)u32(r+16)==XW_MODE_BUSY);
 exchange(fd,XW_MODE_RELEASE,5,0,r);assert((int32_t)u32(r+16)==XW_MODE_PENDING&&u32(r+20)==XW_MODE_DRAINING&&u32(r+32)==1&&!u32(r+36));
 exchange(fd,XW_MODE_QUERY,6,0,r);assert(u32(r+20)==XW_MODE_DRAINING&&u32(r+24)==XW_WIRELESS_MODE_ESPNOW&&u32(r+32)==1);
 /* Test adapter's explicit simulated driver-completion signal, not a policy
  * timeout or a client-supplied hardware proof in the RPC protocol. */
 assert(write(proof_writer,"R",1)==1);close(proof_writer);
 uint64_t serial=7;for(unsigned i=0;;i++){
  assert(i<100);exchange(fd,XW_MODE_QUERY,serial++,0,r);
  if(u32(r+20)==XW_MODE_STABLE)break;usleep(1000);
 }
 assert(u32(r+24)==XW_WIRELESS_MODE_WIFI&&!u32(r+32)&&u32(r+36)==1&&!u32(r+68));
 exchange(fd,XW_MODE_ACQUIRE,serial,XW_WIRELESS_MODE_WIFI,r);assert((int32_t)u32(r+16)==XW_MODE_DENIED);
 close(fd);_exit(0);
}
static void scenario(int crash){
 struct xw_wireless_mode_policy policy={0};assert(!xw_mode_policy_init(&policy,77)&&!xw_mode_policy_confirm_off(&policy,XW_WIRELESS_MODE_ESPNOW,1));
 int pair[2],proof[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,pair)&&!pipe(proof));assert(fixture_mode_fcntl(proof[0],F_SETFL,O_NONBLOCK)==0);
 pid_t child=fork();assert(child>=0);if(!child){close(pair[0]);close(proof[0]);client(pair[1],proof[1],crash);}
 close(pair[1]);close(proof[1]);struct xw_mode_channel channel={0};
 assert(!xw_mode_channel_open(&channel,&policy,pair[0],101,XW_MODE_GRANT_READ|XW_MODE_GRANT_ESPNOW));close(pair[0]);
 unsigned confirmed=0;int status=0;
 for(unsigned i=0;;i++){
  assert(i<6000);int step=xw_mode_channel_step(&channel);assert(!step||(crash==2&&step==XW_MODE_FAULT));
  char marker;ssize_t n=read(proof[0],&marker,1);
  if(n==1){
   assert(marker=='R'&&policy.state.active&&policy.state.phase==XW_MODE_DRAINING&&!confirmed);
   assert(xw_mode_policy_request(&policy,XW_WIRELESS_MODE_WIFI)==XW_MODE_PENDING);
   assert(!xw_mode_channel_retired(&channel,1));confirmed=1;
  }
  pid_t done=waitpid(child,&status,WNOHANG);assert(done==0||done==child);if(done==child)break;usleep(1000);
 }
 assert(!status);
 if(crash==2){for(unsigned i=0;channel.bound;i++){assert(i<100);(void)xw_mode_channel_step(&channel);usleep(1000);}assert(channel.fault&&policy.state.active&&!policy.state.off_verified);}
 if(crash){
  assert(channel.held&&policy.state.active&&xw_mode_channel_close(&channel)==XW_MODE_PENDING);
  assert(policy.state.active&&xw_mode_policy_admitted(&policy)==XW_WIRELESS_MODE_UNKNOWN);
  assert(xw_mode_channel_retired(&channel,0)==XW_MODE_FAULT&&channel.held&&policy.state.active);
  assert(!xw_mode_channel_retired(&channel,1)&&!channel.held&&!policy.state.active&&policy.state.phase==XW_MODE_FAILED);
  assert(!xw_mode_policy_confirm_off(&policy,XW_WIRELESS_MODE_WIFI,1));
 }else assert(confirmed&&!channel.held&&!policy.state.active&&policy.serial==1);
 assert(!xw_mode_channel_close(&channel));close(proof[0]);
 assert(xw_mode_policy_admitted(&policy)==XW_WIRELESS_MODE_WIFI);
}
static void admin_scenario(void){
 struct xw_wireless_mode_policy p={0};assert(!xw_mode_policy_init(&p,88)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_WIFI,1));
 int pair[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,pair));pid_t child=fork();assert(child>=0);
 if(!child){close(pair[0]);unsigned char r[80];exchange(pair[1],XW_MODE_ACQUIRE,1,XW_WIRELESS_MODE_ESPNOW,r);assert((int32_t)u32(r+16)==XW_MODE_DENIED);
  exchange(pair[1],XW_MODE_SELECT,2,XW_WIRELESS_MODE_ESPNOW,r);assert((int32_t)u32(r+16)==0&&u32(r+24)==XW_WIRELESS_MODE_ESPNOW&&!u32(r+32)&&u32(r+36)==1);close(pair[1]);_exit(0);}
 close(pair[1]);struct xw_mode_channel c={0};assert(!xw_mode_channel_open(&c,&p,pair[0],303,XW_MODE_GRANT_READ|XW_MODE_GRANT_SELECT));close(pair[0]);
 int status;for(unsigned i=0;;i++){assert(i<6000&&!xw_mode_channel_step(&c));pid_t done=waitpid(child,&status,WNOHANG);assert(done==0||done==child);if(done)break;usleep(1000);}
 assert(!status&&!p.state.active&&p.state.off_verified&&xw_mode_policy_admitted(&p)==XW_WIRELESS_MODE_ESPNOW);
 assert(!xw_mode_channel_close(&c));
}
static struct xw_mode_reply client_exchange(struct xw_mode_client *c,unsigned op,int mode){
 struct xw_mode_reply reply,poison;memset(&reply,0xa5,sizeof reply);poison=reply;
 assert(!xw_mode_client_begin(c,op,mode));
 assert(xw_mode_client_begin(c,op,mode)==XW_MODE_BUSY);
 for(unsigned i=0;;i++){
  assert(i<6000);int rc=xw_mode_client_step(c,&reply);if(!rc)break;
  assert(rc==XW_MODE_PENDING&&!memcmp(&reply,&poison,sizeof reply));usleep(1000);
 }
 return reply;
}
static void managed_client_scenario(int wrong_generation){
 struct xw_wireless_mode_policy p={0};assert(!xw_mode_policy_init(&p,123)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_ESPNOW,1));
 int pair[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,pair));pid_t child=fork();assert(child>=0);
 if(!child){
  close(pair[0]);struct xw_mode_client c={0};assert(!xw_mode_client_open(&c,pair[1],wrong_generation?124:123));close(pair[1]);
  if(wrong_generation){
   struct xw_mode_reply reply,before;memset(&reply,0xa5,sizeof reply);before=reply;
   assert(!xw_mode_client_begin(&c,XW_MODE_QUERY,0));
   for(unsigned i=0;;i++){
    assert(i<6000);int rc=xw_mode_client_step(&c,&reply);assert(!memcmp(&reply,&before,sizeof reply));
    if(rc==XW_MODE_FAULT)break;assert(rc==XW_MODE_PENDING);usleep(1000);
   }
   assert(xw_mode_client_close(&c)==XW_MODE_PENDING);_exit(0);
  }
  struct xw_mode_reply r=client_exchange(&c,XW_MODE_QUERY,0);assert(!r.result&&!r.owned&&r.selected==XW_WIRELESS_MODE_ESPNOW);
  r=client_exchange(&c,XW_MODE_ACQUIRE,XW_WIRELESS_MODE_ESPNOW);assert(!r.result&&r.owned);
  r=client_exchange(&c,XW_MODE_RELEASE,0);assert(r.result==XW_MODE_PENDING&&r.owned);
  for(unsigned i=0;;i++){
   assert(i<100);r=client_exchange(&c,XW_MODE_QUERY,0);if(!r.owned)break;
  }
  assert(r.selected==XW_WIRELESS_MODE_ESPNOW&&r.off_verified&&!r.active);
  assert(!xw_mode_client_close(&c));_exit(0);
 }
 close(pair[1]);struct xw_mode_channel channel={0};assert(!xw_mode_channel_open(&channel,&p,pair[0],909,XW_MODE_GRANT_READ|XW_MODE_GRANT_ESPNOW));close(pair[0]);
 int status;
 for(unsigned i=0;;i++){
  assert(i<6000&&!xw_mode_channel_step(&channel));
  if(channel.held&&p.state.phase==XW_MODE_DRAINING)assert(!xw_mode_channel_retired(&channel,1));
  pid_t done=waitpid(child,&status,WNOHANG);assert(done==0||done==child);if(done)break;usleep(1000);
 }
 assert(!status&&!p.state.active&&!xw_mode_channel_close(&channel));
}
static void observed_worker(void){
 struct xw_wireless_mode_policy p={0};struct xw_wireless_lease lease;
 assert(!xw_mode_policy_init(&p,333)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_WIFI,1));
 assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,808,&lease));
 int pair[2],markers[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,pair)&&!pipe(markers));
 assert(fixture_mode_fcntl(markers[0],F_SETFL,O_NONBLOCK)==0);
 pid_t child=fork();assert(child>=0);
 if(!child){
  close(pair[0]);close(markers[0]);struct xw_mode_client c={0};assert(!xw_mode_client_open(&c,pair[1],333));close(pair[1]);
  struct xw_mode_reply r=client_exchange(&c,XW_MODE_QUERY,0);assert(!xw_mode_reply_data_allowed(&r)&&r.lease.consumer==808);
  r=client_exchange(&c,XW_MODE_SELECT,XW_WIRELESS_MODE_OFF);assert(r.result==XW_MODE_DENIED);
  r=client_exchange(&c,XW_MODE_ACQUIRE,XW_WIRELESS_MODE_WIFI);assert(r.result==XW_MODE_DENIED);
  r=client_exchange(&c,XW_MODE_RELEASE,0);assert(r.result==XW_MODE_STALE&&r.owned);
  assert(write(markers[1],"S",1)==1);
  for(unsigned i=0;;i++){assert(i<100);r=client_exchange(&c,XW_MODE_QUERY,0);if(r.phase==XW_MODE_DRAINING)break;}
  assert(xw_mode_reply_data_allowed(&r)==XW_MODE_DENIED&&r.owned);
  assert(write(markers[1],"R",1)==1);close(markers[1]);
  for(unsigned i=0;;i++){assert(i<100);r=client_exchange(&c,XW_MODE_QUERY,0);if(!r.owned)break;}
  assert(r.selected==XW_WIRELESS_MODE_ESPNOW&&!xw_mode_client_close(&c));_exit(0);
 }
 close(pair[1]);close(markers[1]);struct xw_mode_channel channel={0};
 assert(!xw_mode_channel_open(&channel,&p,pair[0],808,XW_MODE_GRANT_READ));close(pair[0]);
 assert(!xw_mode_channel_observe(&channel,&lease));unsigned stopped=0,retired=0;int status;
 for(unsigned i=0;;i++){
  assert(i<6000&&!xw_mode_channel_step(&channel));char marker;ssize_t n=read(markers[0],&marker,1);
  if(n==1){
   assert(xw_mode_channel_retired(&channel,1)==XW_MODE_STALE);
   if(marker=='S'){assert(!stopped++&&xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW)==XW_MODE_PENDING);}
   else {assert(marker=='R'&&stopped&&!retired++&&!xw_mode_policy_release(&p,&lease,1));}
  }
  pid_t done=waitpid(child,&status,WNOHANG);assert(done==0||done==child);if(done)break;usleep(1000);
 }
 assert(!status&&stopped&&retired&&!channel.held&&!xw_mode_channel_close(&channel));close(markers[0]);
 /* Closing an observed view must not quiesce the actual native service. */
 assert(!xw_mode_policy_request(&p,XW_WIRELESS_MODE_WIFI)&&!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,808,&lease));
 memset(&channel,0,sizeof channel);assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,pair));
 assert(!xw_mode_channel_open(&channel,&p,pair[0],808,XW_MODE_GRANT_READ)&&!xw_mode_channel_observe(&channel,&lease));
 assert(!xw_mode_channel_close(&channel)&&!xw_mode_policy_data_allowed(&p,&lease));close(pair[0]);close(pair[1]);
 assert(!xw_mode_policy_release(&p,&lease,1));
}
static void reused_client_fd(void){
 int pair[2],pipefd[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,pair)&&!pipe(pipefd));
 struct xw_mode_client c={0};assert(!xw_mode_client_open(&c,pair[0],123));
 int reused=c.fd;assert(!close(reused)&&dup2(pipefd[0],reused)==reused);
 struct xw_mode_reply r,before;memset(&r,0xa5,sizeof r);before=r;
 assert(!xw_mode_client_begin(&c,XW_MODE_QUERY,0)&&xw_mode_client_step(&c,&r)==XW_MODE_FAULT);
 assert(!memcmp(&r,&before,sizeof r)&&fixture_mode_fcntl(reused,F_GETFD)>=0);
 assert(xw_mode_client_close(&c)==XW_MODE_PENDING);close(reused);close(pair[0]);close(pair[1]);close(pipefd[0]);close(pipefd[1]);
}
struct permission_fixture {int fd,report,proceed,timeout,gui_pid;unsigned long gui_thread;struct xw_wireless_lease lease;};
static void *permission_thread(void *context){
 struct permission_fixture *f=context;struct xw_native_wireless_permission permission={0};
 struct xw_native_wireless_permission wrong_peer={0};
 assert(xw_native_permission_open(&wrong_peer,f->fd,f->gui_pid+100000,f->gui_thread,&f->lease)==XW_MODE_WRONG_OWNER);
 if(f->timeout==1){
  assert(!xw_native_permission_open(&permission,f->fd,f->gui_pid,f->gui_thread,&f->lease));
  assert(xw_native_permission_check(&permission,20)==XW_MODE_FAULT);
  assert(xw_native_permission_close(&permission)==XW_MODE_PENDING);assert(write(f->report,"T",1)==1);return 0;
 }
 assert(xw_native_rf_permission()==XW_MODE_DENIED);
 assert(!xw_native_rf_worker_bind(f->fd,f->gui_pid,f->gui_thread,&f->lease));
 assert(xw_native_rf_worker_bind(f->fd,f->gui_pid,f->gui_thread,&f->lease)==XW_MODE_BUSY);
 pid_t copy=fork();assert(copy>=0);
 if(!copy){assert(xw_native_rf_permission()!=0);_exit(0);}
 int copy_status;assert(waitpid(copy,&copy_status,0)==copy&&!copy_status);
 assert(!xw_native_rf_permission());assert(write(f->report,"A",1)==1);
 char go;assert(read(f->proceed,&go,1)==1&&go=='B');
 assert(xw_native_rf_permission()==XW_MODE_DENIED);
 if(f->timeout!=2){assert(xw_native_rf_worker_close()==XW_MODE_PENDING);assert(xw_native_rf_permission()==XW_MODE_DENIED);}
 assert(write(f->report,"D",1)==1);return 0;
}
static void native_worker_permission(int timeout){
 struct xw_wireless_mode_policy p={0};struct xw_wireless_lease lease;
 assert(!xw_mode_policy_init(&p,444)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_WIFI,1));
 assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,808,&lease));
 int pair[2],reports[2],proceed[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,pair)&&!pipe(reports)&&!pipe(proceed));
 assert(fixture_mode_fcntl(reports[0],F_SETFL,O_NONBLOCK)==0);
 struct xw_mode_channel channel={0};assert(!xw_mode_channel_open(&channel,&p,pair[0],808,XW_MODE_GRANT_READ)&&!xw_mode_channel_observe(&channel,&lease));
 struct xw_native_wireless_permission wrong={0};assert(xw_native_permission_open(&wrong,pair[1],getpid(),(unsigned long)pthread_self(),&lease)==XW_MODE_WRONG_OWNER);
 assert(xw_native_rf_permission()==XW_MODE_DENIED);
 assert(xw_native_rf_worker_bind(pair[1],getpid(),(unsigned long)pthread_self(),&lease)==XW_MODE_WRONG_OWNER);
 struct permission_fixture f={pair[1],reports[1],proceed[0],timeout,getpid(),(unsigned long)pthread_self(),lease};
 pthread_t thread;assert(!pthread_create(&thread,0,permission_thread,&f));
 if(timeout==1){
  assert(!pthread_join(thread,0));char marker;assert(read(reports[0],&marker,1)==1&&marker=='T');
 }else{
  for(unsigned i=0;;i++){
   assert(i<6000&&!xw_mode_channel_step(&channel));char marker;ssize_t n=read(reports[0],&marker,1);
   if(n==1){
    if(marker=='A'){assert(xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW)==XW_MODE_PENDING);assert(write(proceed[1],"B",1)==1);}
    else {assert(marker=='D');break;}
   }
   usleep(1000);
  }
  assert(!pthread_join(thread,0));
 }
 assert(!xw_mode_channel_close(&channel)&&p.state.active&&!xw_mode_policy_owns(&p,&lease));
 assert(!xw_mode_policy_release(&p,&lease,1));
 close(pair[0]);close(pair[1]);close(reports[0]);close(reports[1]);close(proceed[0]);close(proceed[1]);
}
struct renewal_fixture {int oldfd,newfd,report,proceed,gui_pid;unsigned long gui_thread;struct xw_wireless_lease lease;};
static void *renewal_thread(void *context){
 struct renewal_fixture *f=context;
 assert(!xw_native_rf_worker_bind(f->oldfd,f->gui_pid,f->gui_thread,&f->lease)&&!xw_native_rf_permission());
 assert(xw_native_rf_worker_replace(f->newfd,f->gui_pid,f->gui_thread,&f->lease)==XW_MODE_STALE);
 /* A relabeled old capability must not replace the still-valid original TLS. */
 struct xw_wireless_lease fake=f->lease;fake.serial++;
 assert(xw_native_rf_worker_replace(f->oldfd,f->gui_pid,f->gui_thread,&fake)==XW_MODE_DENIED);
 assert(!xw_native_rf_permission()&&!xw_native_rf_permission()&&write(f->report,"A",1)==1);
 struct xw_wireless_lease fresh;assert(read(f->proceed,&fresh,sizeof fresh)==sizeof fresh);
 assert(fresh.serial>f->lease.serial);
 assert(!xw_native_rf_worker_replace(f->newfd,f->gui_pid,f->gui_thread,&fresh));
 assert(!xw_native_rf_permission());
 assert(xw_native_rf_worker_replace(f->oldfd,f->gui_pid,f->gui_thread,&f->lease)==XW_MODE_STALE);
 assert(xw_native_rf_worker_close()==XW_MODE_PENDING&&write(f->report,"D",1)==1);return 0;
}
static void native_worker_renewal(void){
 struct xw_wireless_mode_policy p={0};struct xw_wireless_lease old,fresh;
 assert(!xw_mode_policy_init(&p,555)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_WIFI,1));
 assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,808,&old));
 int first[2],second[2],reports[2],proceed[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,first)&&!socketpair(AF_UNIX,SOCK_DGRAM,0,second)&&!pipe(reports)&&!pipe(proceed));
 assert(fixture_mode_fcntl(reports[0],F_SETFL,O_NONBLOCK)==0);
 struct xw_mode_channel a={0},b={0};assert(!xw_mode_channel_open(&a,&p,first[0],808,XW_MODE_GRANT_READ)&&!xw_mode_channel_observe(&a,&old));
 struct renewal_fixture f={first[1],second[1],reports[1],proceed[0],getpid(),(unsigned long)pthread_self(),old};
 pthread_t thread;assert(!pthread_create(&thread,0,renewal_thread,&f));int renewed=0;
 for(unsigned i=0;;i++){
  assert(i<6000&&!xw_mode_channel_step(&a));if(renewed)assert(!xw_mode_channel_step(&b));
  char marker;ssize_t n=read(reports[0],&marker,1);
  if(n==1){
   if(marker=='A'){
    assert(!renewed&&xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW)==XW_MODE_PENDING);
    assert(!xw_mode_policy_release(&p,&old,1)&&!xw_mode_policy_request(&p,XW_WIRELESS_MODE_WIFI));
    assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,808,&fresh));
    assert(!xw_mode_channel_open(&b,&p,second[0],808,XW_MODE_GRANT_READ)&&!xw_mode_channel_observe(&b,&fresh));
    renewed=1;assert(write(proceed[1],&fresh,sizeof fresh)==sizeof fresh);
   }else {assert(marker=='D'&&renewed);break;}
  }
  usleep(1000);
 }
 assert(!pthread_join(thread,0)&&!xw_mode_channel_close(&a)&&!xw_mode_channel_close(&b));
 assert(p.state.active&&!xw_mode_policy_data_allowed(&p,&fresh)&&!xw_mode_policy_release(&p,&fresh,1));
 close(first[0]);close(first[1]);close(second[0]);close(second[1]);close(reports[0]);close(reports[1]);close(proceed[0]);close(proceed[1]);
}
struct offer_fixture {int delivery,report,proceed,gui_pid;};
static void *offer_thread(void *context){
 struct offer_fixture *f=context;
 int adopted=xw_native_offer_receive(f->delivery);
 if(adopted){printf("OFFER_ADOPT=%d WORKER_PID=%d GUI_PID=%d\n",adopted,getpid(),f->gui_pid);fflush(stdout);}
 assert(!adopted&&!xw_native_rf_permission());
 assert(xw_native_offer_receive(f->delivery)==XW_MODE_PENDING&&write(f->report,"A",1)==1);
 char go;assert(read(f->proceed,&go,1)==1&&go=='B');
 assert(!xw_native_offer_receive(f->delivery)&&!xw_native_rf_permission());
 assert(xw_native_rf_worker_close()==XW_MODE_PENDING&&write(f->report,"D",1)==1);return 0;
}
static unsigned count_fds(void){unsigned n=0;for(int fd=0;fd<256;fd++)if(fixture_mode_fcntl(fd,F_GETFD)>=0)n++;return n;}
static void native_worker_delivery(void){
 struct xw_wireless_mode_policy p={0};struct xw_wireless_lease old,fresh;
 assert(!xw_mode_policy_init(&p,666)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_WIFI,1));
 assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,808,&old));
 int first[2],second[2],delivery[2],reports[2],proceed[2];
 assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,first)&&!socketpair(AF_UNIX,SOCK_DGRAM,0,second)&&!socketpair(AF_UNIX,SOCK_DGRAM,0,delivery)&&!pipe(reports)&&!pipe(proceed));
 assert(fixture_mode_fcntl(reports[0],F_SETFL,O_NONBLOCK)==0);
 struct xw_mode_channel a={0},b={0};assert(!xw_mode_channel_open(&a,&p,first[0],808,XW_MODE_GRANT_READ)&&!xw_mode_channel_observe(&a,&old));
 unsigned before=count_fds();
 assert(!xw_native_offer_send(&p,delivery[0],first[1],&old));
 assert(xw_native_offer_receive(delivery[1])==XW_MODE_INVALID&&count_fds()==before); /* GUI cannot adopt its own offer. */
 unsigned char bad[64]={0};assert(send(delivery[0],bad,sizeof bad,MSG_NOSIGNAL)==sizeof bad);
 assert(xw_native_offer_receive(delivery[1])==XW_MODE_INVALID&&count_fds()==before);
 assert(!xw_native_offer_send(&p,delivery[0],first[1],&old));
 struct offer_fixture f={delivery[1],reports[1],proceed[0],getpid()};pthread_t thread;assert(!pthread_create(&thread,0,offer_thread,&f));int renewed=0;
 for(unsigned i=0;;i++){
  assert(i<6000&&!xw_mode_channel_step(&a));if(renewed)assert(!xw_mode_channel_step(&b));
  char marker;ssize_t n=read(reports[0],&marker,1);
  if(n==1){
   if(marker=='A'){
    assert(!renewed&&xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW)==XW_MODE_PENDING);
    assert(xw_native_offer_send(&p,delivery[0],first[1],&old)==XW_MODE_DENIED);
    assert(!xw_mode_policy_release(&p,&old,1)&&!xw_mode_policy_request(&p,XW_WIRELESS_MODE_WIFI));
    assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,808,&fresh));
    assert(!xw_mode_channel_open(&b,&p,second[0],808,XW_MODE_GRANT_READ)&&!xw_mode_channel_observe(&b,&fresh));
    assert(!xw_native_offer_send(&p,delivery[0],second[1],&fresh));renewed=1;assert(write(proceed[1],"B",1)==1);
   }else {assert(marker=='D'&&renewed);break;}
  }
  usleep(1000);
 }
 assert(!pthread_join(thread,0)&&!xw_mode_channel_close(&a)&&!xw_mode_channel_close(&b));
 assert(p.state.active&&!xw_mode_policy_release(&p,&fresh,1));
 close(first[0]);close(first[1]);close(second[0]);close(second[1]);close(delivery[0]);close(delivery[1]);close(reports[0]);close(reports[1]);close(proceed[0]);close(proceed[1]);
}
struct automatic_fixture {struct offer_fixture io;int fail_off;};
static void *automatic_delivery_thread(void *context){
 struct automatic_fixture *configuration=context;struct offer_fixture *f=&configuration->io;
 assert(!xw_native_rf_bootstrap_worker()&&xw_native_delivery_attached());
 assert(write(f->report,"S",1)==1);
 if(configuration->fail_off!=3){
  assert(!pthread_setspecific(poll_trace,&f->report));
  assert(!xw_native_rf_permission()&&!xw_native_rf_permission());
  assert(!xw_native_rf_poweroff_note(0)&&!retirement_state_reads); /* Stable off is not a handover receipt. */
 }
 assert(write(f->report,"A",1)==1);
 char go;assert(read(f->proceed,&go,1)==1&&go=='R');
 if(configuration->fail_off==3){
  assert(xw_native_rf_refresh_offer()==XW_NATIVE_RF_CLEANUP_VIEW);
  assert(xw_native_rf_permission()!=0); /* Ownership for cleanup never permits data. */
 }
 struct xw_mode_reply view;assert(!xw_native_rf_worker_observe(&view)&&view.phase==XW_MODE_DRAINING);
 struct xw_native_retirement old={view.lease,0,2,view.phase,1,1,configuration->fail_off==3?XW_NATIVE_RETIRE_DISABLE_CHECKPOINT:XW_NATIVE_RETIRE_OFF_CALL};
 assert(!(configuration->fail_off==3?xw_native_rf_disable_checkpoint(0x4c0006):xw_native_rf_poweroff_note(0)));
 assert(xw_native_rf_cleanup_permission()==2&&xw_native_rf_permission()!=0);
 assert(!xw_native_rf_poweroff_note(0)&&write(f->report,"N",1)==1);
 assert(read(f->proceed,&go,1)==1&&go=='B');
 assert(!xw_native_rf_permission()&&!xw_native_rf_permission()&&write(f->report,"G",1)==1);
 assert(read(f->proceed,&go,1)==1&&go=='F');
 unsigned char stale[64];assert(!xw_native_retirement_encode(stale,&old)&&!xw_native_delivery_send_notice(stale));
 assert(write(f->report,"L",1)==1&&read(f->proceed,&go,1)==1&&go=='H');
 if(configuration->fail_off==1||configuration->fail_off==2){
  if(configuration->fail_off==2)retirement_modules_clear=0;
  assert(!xw_native_rf_poweroff_note(configuration->fail_off==2?0:16)&&write(f->report,"E",1)==1);
  assert(read(f->proceed,&go,1)==1&&go=='T');
  retirement_modules_clear=1;
 }
 assert(!xw_native_rf_poweroff_note(0)&&write(f->report,"D",1)==1);
 return 0; /* Both TLS destructors clean up without releasing native ownership. */
}
static void publisher_failure_cleanup(void){
 struct xw_wireless_mode_policy p={0};struct xw_wireless_lease lease;struct xw_native_publisher publisher={0};
 assert(!xw_mode_policy_init(&p,776)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_WIFI,1));
 assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_WIFI,808,&lease)&&!xw_native_publisher_bind(&publisher,&p));
 unsigned baseline=count_fds();
 /* GUI delivery bootstrap has not run: publication must clean both observation
  * endpoints while retaining the authority's real lease and fault state. */
 assert(xw_native_publisher_prepare(&publisher,&lease)==XW_MODE_FAULT&&publisher.fault);
 assert(count_fds()==baseline&&p.state.active&&!xw_mode_policy_data_allowed(&p,&lease));
 assert(!xw_native_publisher_close(&publisher)&&!xw_mode_policy_release(&p,&lease,1));
}
static void *boot_report_thread(void *unused){
 (void)unused;assert(!xw_native_rf_bootstrap_worker());
 assert(xw_native_rf_permission()==XW_MODE_DENIED);return 0;
}
static void boot_condition_case(int off){
 pid_t child=fork();assert(child>=0);
 if(!child){
  boot_test_bad=!off;boot_test_flag=off;
  assert(!xw_native_rf_bootstrap_gui()&&xw_player_host_wireless_auto()==XW_MODE_PENDING);
  assert(xw_player_host_wireless_request(0x4c0007)==XW_MODE_PENDING);
  pthread_t thread;assert(!pthread_create(&thread,0,boot_report_thread,0));int rc;
  for(unsigned i=0;;i++){assert(i<3000);rc=xw_player_host_wireless_auto();if(rc!=XW_MODE_PENDING)break;usleep(1000);}
  assert(!pthread_join(thread,0));
  if(off){
   assert(!rc&&boot_authority&&boot_authority->state.selected==XW_WIRELESS_MODE_OFF&&!boot_authority->state.active);
   assert(xw_player_host_wireless_request(0x4c0007)==XW_MODE_DENIED&&!xw_player_host_wireless_backend_close());
  }else assert(rc==XW_MODE_DENIED&&!boot_authority&&xw_player_host_wireless_auto()==XW_MODE_DENIED&&xw_player_host_wireless_request(0x4c0007)==XW_MODE_DENIED);
  _exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child&&!status);
}
static void native_worker_automatic_delivery(int fail_off){
 assert(!xw_native_rf_bootstrap_gui()&&!xw_native_rf_bootstrap_gui());
 assert(xw_native_rf_bootstrap_worker()==XW_MODE_DENIED);
 unsigned baseline=count_fds();
 struct xw_wireless_mode_policy *p=0;struct xw_wireless_lease old,fresh;
 int reports[2],proceed[2];assert(!pipe(reports)&&!pipe(proceed));
 assert(fixture_mode_fcntl(reports[0],F_SETFL,O_NONBLOCK)==0);
 assert(xw_player_host_wireless_auto()==XW_MODE_PENDING&&!boot_authority);
 assert(xw_player_host_wireless_request(0x4c0007)==XW_MODE_PENDING&&xw_player_host_wireless_request(0x4c0001)==XW_MODE_PENDING);
 struct automatic_fixture f={{-1,reports[1],proceed[0],getpid()},fail_off};pthread_t thread;assert(!pthread_create(&thread,0,automatic_delivery_thread,&f));int renewed=0,started=0,notice=0,finished=0;
 int waited=0;
 for(unsigned i=0;!waited;i++){
  assert(i<3000);char marker;ssize_t n=read(reports[0],&marker,1);
  if(n==1){assert(marker=='S'||marker=='W');if(marker=='W'||(marker=='S'&&fail_off==3))waited=1;}else usleep(1000);
 }
 unsigned delivered_stops=0;
 for(unsigned i=0;;i++){
  assert(i<6000);int automatic=xw_player_host_wireless_auto();assert(automatic==0||automatic==XW_MODE_PENDING);
  if(!started&&automatic==0){
   p=boot_authority;assert(p&&p->generation==777&&p->state.selected==XW_WIRELESS_MODE_WIFI);
   assert(p->state.active&&!xw_player_host_wireless_request(0x4c000d));
   assert(!xw_player_host_wireless_request(0x4c0005));
   old=p->state.lease;assert(old.consumer==XW_NATIVE_WIFI_CONSUMER&&p->serial==1);
   started=1;
  }
  int tick=xw_player_host_wireless_tick();
  assert(!tick||(fail_off&&tick==XW_MODE_FAULT&&p&&p->state.phase==XW_MODE_FAILED));
  if(stop_accepted>delivered_stops){
   assert(stop_accepted==delivered_stops+1);delivered_stops=stop_accepted;
   char event=delivered_stops==1?'R':'F';assert(write(proceed[1],&event,1)==1);
  }
  if(notice&&!renewed&&!p->state.active&&p->state.selected==XW_WIRELESS_MODE_ESPNOW){
   struct xw_wireless_lease independent;
   assert(!xw_mode_policy_acquire(p,XW_WIRELESS_MODE_ESPNOW,0xee,&independent));
   extern int xw_native_rf_gui_cleanup_permission(void);
   assert(xw_native_rf_gui_cleanup_permission()==2&&!xw_mode_policy_release(p,&independent,1));
   assert(!xw_mode_policy_request(p,XW_WIRELESS_MODE_WIFI));
   assert(!xw_player_host_wireless_request(0x4cc001)&&!xw_player_host_wireless_request(0x4cc001));
   fresh=p->state.lease;assert(fresh.serial>old.serial&&fresh.consumer==XW_NATIVE_WIFI_CONSUMER);
   renewed=1;assert(write(proceed[1],"B",1)==1);
  }
  if(finished&&!p->state.active)break;
  char marker;ssize_t n=read(reports[0],&marker,1);
  if(n==1){
   if(marker=='S'){continue;}
   if(marker=='A'){
    stop_backpressure=1;
    assert(started&&!renewed&&xw_mode_policy_request(p,XW_WIRELESS_MODE_ESPNOW)==XW_MODE_PENDING);
    assert(xw_player_host_wireless_request(0x4c0001)==XW_MODE_DENIED);
   }else if(marker=='N')notice=1;
   else if(marker=='G'){
    assert(renewed&&p->state.active);
    if(!fail_off){
     assert(xw_player_host_wireless_prepare_stop(0)==XW_MODE_INVALID);
     assert(xw_player_host_wireless_prepare_stop(42)==XW_MODE_PENDING);
     assert(xw_player_host_wireless_prepare_stop(43)==XW_MODE_STALE);
     assert(xw_player_host_wireless_request(0x4c0007)==XW_MODE_DENIED);
     assert(!xw_player_host_wireless_request(0x4c000d));
    }else assert(xw_mode_policy_request(p,XW_WIRELESS_MODE_OFF)==XW_MODE_PENDING);
   }else if(marker=='L'){
    assert(!xw_player_host_wireless_tick()&&p->state.active&&p->state.lease.serial==fresh.serial);
    assert(write(proceed[1],"H",1)==1);
   }else if(marker=='E'){
    int failure=xw_player_host_wireless_tick();assert((failure==0||failure==XW_MODE_FAULT)&&p->state.phase==XW_MODE_FAILED&&p->state.active);
    assert(xw_mode_policy_admitted(p)==XW_WIRELESS_MODE_UNKNOWN&&xw_player_host_wireless_backend_close()==XW_MODE_PENDING);
    assert(write(proceed[1],"T",1)==1);
   }else {assert(marker=='D'&&renewed);finished=1;}
  }
  usleep(1000);
 }
 assert(!pthread_join(thread,0)&&!p->state.active&&!xw_player_host_wireless_backend_close()&&retirement_state_reads==(fail_off==2?3u:2u));
 assert(stop_attempts==3&&stop_accepted==2);
 assert((fail_off==1||fail_off==2)?p->state.phase==XW_MODE_FAILED&&xw_mode_policy_admitted(p)==XW_WIRELESS_MODE_UNKNOWN:p->state.phase==XW_MODE_STABLE&&p->state.selected==(fail_off?XW_WIRELESS_MODE_OFF:XW_WIRELESS_MODE_WIFI));
 if(!fail_off){
  assert(!xw_player_host_wireless_prepare_stop(42));
  assert(xw_player_host_wireless_prepare_stop(43)==XW_MODE_STALE);
  assert(xw_player_host_wireless_request(0x4c0007)==XW_MODE_DENIED);
 }
 close(reports[0]);close(reports[1]);close(proceed[0]);close(proceed[1]);
 assert(count_fds()==baseline);
}
static void *warm_thread(void *unused){return unused;}
static void settings_radio_authority(int fail){
 pid_t child=fork();assert(child>=0);
 if(!child){
  struct xw_wireless_mode_policy p={0};struct xw_wireless_lease old={0},next={0},other={0},before=old;
  assert(!xw_mode_policy_init(&p,929)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_OFF,1));
  assert(!xw_player_host_wireless_bound(&p));
  assert(xw_player_host_wireless_remote_acquire(&old)==XW_MODE_DENIED&&!memcmp(&old,&before,sizeof old));
  assert(!xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW));
  assert(!xw_player_host_wireless_remote_acquire(&old)&&old.consumer==XW_PLAYER_REMOTE_CONSUMER&&p.state.active);
  uint64_t serial=p.serial;assert(!xw_player_host_wireless_remote_acquire(&old)&&p.serial==serial);
  assert(xw_player_host_wireless_remote_acquire(&other)==XW_MODE_BUSY&&!other.serial);
  assert(xw_mode_policy_request(&p,XW_WIRELESS_MODE_WIFI)==XW_MODE_PENDING);
  assert(xw_player_host_wireless_remote_mode()==XW_WIRELESS_MODE_UNKNOWN&&xw_player_host_wireless_remote_acquire(&old)==XW_MODE_DENIED);
  if(fail){
   assert(xw_player_host_wireless_remote_retired(&old,0)==XW_MODE_FAULT&&p.state.active);
   assert(!xw_player_host_wireless_remote_retired(&old,1)&&p.state.phase==XW_MODE_FAILED);
   assert(xw_player_host_wireless_remote_acquire(&next)==XW_MODE_DENIED);_exit(0);
  }
  assert(!xw_player_host_wireless_remote_retired(&old,1)&&p.state.selected==XW_WIRELESS_MODE_WIFI&&!p.state.active);
  assert(!xw_mode_policy_request(&p,XW_WIRELESS_MODE_ESPNOW)&&!xw_player_host_wireless_remote_acquire(&next));
  assert(next.serial>old.serial&&xw_player_host_wireless_remote_retired(&old,1)==XW_MODE_STALE&&p.state.active);
  assert(!xw_player_host_wireless_remote_retired(&next,1));
  assert(!xw_player_host_wireless_prepare_handoff(100)&&xw_player_host_wireless_remote_mode()==XW_WIRELESS_MODE_UNKNOWN);
  assert(xw_player_host_wireless_remote_acquire(&other)==XW_MODE_DENIED);
  assert(!xw_player_host_wireless_resume_handoff(100)&&xw_player_host_wireless_remote_mode()==XW_WIRELESS_MODE_ESPNOW);
  assert(!xw_player_host_wireless_backend_close());_exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child&&!status);
}
static void wireless_handoff_independent(void){
 pid_t child=fork();assert(child>=0);
 if(!child){
  struct xw_wireless_mode_policy p={0};struct xw_wireless_lease first,external;
  assert(!xw_mode_policy_init(&p,919)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_ESPNOW,1));
  assert(!xw_player_host_wireless_bound(&p));
  assert(xw_player_host_wireless_prepare_handoff(0)==XW_MODE_INVALID);
  assert(xw_player_host_wireless_player_active());
  assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_ESPNOW,0xee,&first));
  assert(xw_player_host_wireless_prepare_handoff(41)==XW_MODE_PENDING);
  assert(!xw_player_host_wireless_player_active());
  assert(xw_mode_policy_data_allowed(&p,&first)==XW_MODE_DENIED);
  assert(xw_player_host_wireless_resume_handoff(41)==XW_MODE_PENDING);
  assert(xw_player_host_wireless_resume_handoff(40)==XW_MODE_STALE);
  assert(!xw_mode_policy_release(&p,&first,1)&&!xw_player_host_wireless_prepare_handoff(41));
  /* Another app can use the system radio while this player is inactive. Its
   * new lease must not be quiesced by repeated player handoff polling. */
  assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_ESPNOW,0xef,&external));
  assert(xw_player_host_wireless_prepare_handoff(41)==XW_MODE_PENDING);
  assert(!xw_mode_policy_data_allowed(&p,&external));
  assert(xw_player_host_wireless_resume_handoff(41)==XW_MODE_PENDING);
  assert(xw_player_host_wireless_request(0x4c0007)==XW_MODE_DENIED);
  assert(!xw_mode_policy_release(&p,&external,1));
  assert(!xw_player_host_wireless_resume_handoff(41));
  assert(xw_player_host_wireless_player_active());
  assert(xw_player_host_wireless_resume_handoff(41)==XW_MODE_STALE);
  assert(xw_player_host_wireless_prepare_handoff(41)==XW_MODE_STALE);
  uint64_t epoch=0;assert(!xw_player_host_wireless_next_epoch(&epoch)&&epoch==42);
  assert(!xw_player_host_wireless_prepare_handoff(epoch));
  epoch=123;assert(xw_player_host_wireless_next_epoch(&epoch)==XW_MODE_BUSY&&epoch==123);
  assert(!xw_player_host_wireless_prepare_stop(43));
  assert(xw_player_host_wireless_next_epoch(&epoch)==XW_MODE_DENIED&&epoch==123);
  assert(!xw_player_host_wireless_player_active());
  assert(xw_player_host_wireless_resume_handoff(42)==XW_MODE_DENIED);
  assert(xw_player_host_wireless_prepare_handoff(44)==XW_MODE_DENIED);
  assert(!xw_player_host_wireless_backend_close());_exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child&&!status);
}
static void wireless_stop_independent(void){
 pid_t child=fork();assert(child>=0);
 if(!child){
  struct xw_wireless_mode_policy p={0};struct xw_wireless_lease lease;
  assert(xw_player_host_wireless_prepare_stop(42)==XW_MODE_DENIED);
  assert(!xw_mode_policy_init(&p,909)&&!xw_mode_policy_confirm_off(&p,XW_WIRELESS_MODE_ESPNOW,1));
  assert(!xw_player_host_wireless_bound(&p));
  assert(!xw_mode_policy_acquire(&p,XW_WIRELESS_MODE_ESPNOW,0xee,&lease));
  assert(xw_player_host_wireless_prepare_stop(42)==XW_MODE_PENDING);
  assert(xw_mode_policy_data_allowed(&p,&lease)==XW_MODE_DENIED);
  assert(xw_player_host_wireless_backend_close()==XW_MODE_PENDING);
  assert(!xw_mode_policy_owns(&p,&lease));
  assert(xw_player_host_wireless_prepare_stop(42)==XW_MODE_PENDING);
  assert(xw_player_host_wireless_request(0x4c0007)==XW_MODE_DENIED);
  assert(!xw_mode_policy_release(&p,&lease,1));
  assert(!xw_player_host_wireless_prepare_stop(42));
  assert(p.state.selected==XW_WIRELESS_MODE_ESPNOW&&p.state.off_verified);
  assert(xw_player_host_wireless_prepare_stop(43)==XW_MODE_STALE);
  assert(!xw_player_host_wireless_backend_close());_exit(0);
 }
 int status;assert(waitpid(child,&status,0)==child&&!status);
}
static void automatic_failure_case(int kind){
 pid_t child=fork();assert(child>=0);
 if(!child){pthread_t warm;assert(!pthread_create(&warm,0,warm_thread,0)&&!pthread_join(warm,0));native_worker_automatic_delivery(kind);_exit(0);}
 int status;assert(waitpid(child,&status,0)==child&&!status);
}
static void retirement_codec(void){
 struct xw_native_retirement r={{1,2,3,XW_WIRELESS_MODE_WIFI},0,2,XW_MODE_DRAINING,1,1,XW_NATIVE_RETIRE_OFF_CALL},out,before;
 unsigned char raw[64];assert(!xw_native_retirement_encode(raw,&r)&&!xw_native_retirement_decode(&out,raw,64));
 assert(out.lease.serial==2&&out.modules_clear==1&&out.phase==XW_MODE_DRAINING);
 memset(&out,0xa5,sizeof out);before=out;raw[63]=1;
 assert(xw_native_retirement_decode(&out,raw,64)==XW_MODE_INVALID&&!memcmp(&out,&before,sizeof out));
 assert(xw_native_retirement_decode(&out,raw,63)==XW_MODE_INVALID&&!memcmp(&out,&before,sizeof out));
 r.phase=XW_MODE_STABLE;assert(xw_native_retirement_encode(raw,&r)==XW_MODE_INVALID);
 r.phase=XW_MODE_FAILED;r.modules_clear=0;r.native_result=16;r.public_state=-1;r.sealed=0;
 assert(!xw_native_retirement_encode(raw,&r)&&!xw_native_retirement_decode(&out,raw,64)&&out.native_result==16&&!out.modules_clear);
}
static int admission_query(struct wr_owner_admission *gate,struct xw_mode_channel *channel){
 assert(!wr_owner_admission_refresh(gate));
 for(unsigned i=0;i<16;i++){
  int rc=wr_owner_admission_step(gate);
  if(rc!=XW_MODE_PENDING)return rc;
  rc=xw_mode_channel_step(channel);assert(rc==0||rc==XW_MODE_PENDING);
 }
 assert(0);return -1;
}
static void owner_admission_case(unsigned kind){
 struct xw_wireless_mode_policy policy={0};struct xw_wireless_lease lease;
 struct xw_mode_channel channel={0};struct wr_owner_admission gate={0};int pair[2];
 assert(!xw_mode_policy_init(&policy,778)&&!xw_mode_policy_confirm_off(&policy,XW_WIRELESS_MODE_ESPNOW,1));
 assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,0x12345,&lease));
 assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,pair));
 assert(!xw_mode_channel_open(&channel,&policy,pair[0],lease.consumer,XW_MODE_GRANT_READ));
 assert(!xw_mode_channel_observe(&channel,&lease));close(pair[0]);
 struct xw_wireless_lease expected=lease;
 if(kind==1)expected.serial++;
 if(kind==2){
  expected.mode=XW_WIRELESS_MODE_WIFI;
  assert(wr_owner_admission_open(&gate,pair[1],&expected)==XW_MODE_INVALID&&!gate.client.bound);
  close(pair[1]);assert(!xw_mode_channel_close(&channel));
 }else{
  assert(!wr_owner_admission_open(&gate,pair[1],&expected));close(pair[1]);
  assert(!wr_owner_admission_allowed(&gate));
  if(kind==3){
   assert(!xw_mode_channel_close(&channel));assert(!wr_owner_admission_refresh(&gate));
   assert(wr_owner_admission_step(&gate)==XW_MODE_FAULT&&!wr_owner_admission_allowed(&gate));
  }else{
   int rc=admission_query(&gate,&channel);
   if(kind==1)assert(rc==XW_MODE_DENIED&&!wr_owner_admission_allowed(&gate));
   else{
    assert(!rc&&wr_owner_admission_allowed(&gate));
    pid_t child=fork();assert(child>=0);if(!child)_exit(wr_owner_admission_allowed(&gate)?1:0);
    int status;assert(waitpid(child,&status,0)==child&&!status);
    if(kind!=4){
     assert(xw_mode_policy_request(&policy,XW_WIRELESS_MODE_WIFI)==XW_MODE_PENDING);
     assert(admission_query(&gate,&channel)==XW_MODE_DENIED&&!wr_owner_admission_allowed(&gate));
     if(kind==5){
      assert(!xw_mode_policy_release(&policy,&lease,1));
      assert(!xw_mode_policy_request(&policy,XW_WIRELESS_MODE_ESPNOW));
      assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,lease.consumer,&lease));
      assert(wr_owner_admission_refresh(&gate)==XW_MODE_DENIED&&!wr_owner_admission_allowed(&gate));
     }
    }
   }
  }
  assert(wr_owner_admission_close(&gate)>=0&&!wr_owner_admission_allowed(&gate));
  assert(!wr_owner_admission_close(&gate));
  if(channel.bound)assert(!xw_mode_channel_close(&channel));
 }
 assert(policy.state.active); /* Closing the READ view is never radio release. */
 int rc=xw_mode_policy_quiesce(&policy,&lease);assert(rc==0||rc==XW_MODE_PENDING);
 assert(!xw_mode_policy_release(&policy,&lease,1));
}
static void owner_admission_periodic(unsigned kind){
 struct xw_wireless_mode_policy policy={0};struct xw_wireless_lease lease;
 struct xw_mode_channel channel={0};struct wr_owner_admission gate={0};int pair[2];
 assert(!xw_mode_policy_init(&policy,779)&&!xw_mode_policy_confirm_off(&policy,XW_WIRELESS_MODE_ESPNOW,1));
 assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,0x789,&lease));
 assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,pair));
 assert(!xw_mode_channel_open(&channel,&policy,pair[0],lease.consumer,XW_MODE_GRANT_READ));close(pair[0]);
 assert(!xw_mode_channel_observe(&channel,&lease)&&!wr_owner_admission_open(&gate,pair[1],&lease));close(pair[1]);
 int rc=wr_owner_admission_poll(&gate,1000);assert(rc==XW_MODE_PENDING&&!wr_owner_admission_allowed(&gate));
 for(unsigned i=0;rc==XW_MODE_PENDING;i++){
  assert(i<10);int step=xw_mode_channel_step(&channel);assert(step==0||step==XW_MODE_PENDING);
  rc=wr_owner_admission_poll(&gate,1001+i);
 }
 assert(!rc&&wr_owner_admission_allowed(&gate));uint64_t stamp=gate.observed_at,serial=gate.client.serial;
 for(unsigned i=1;i<200;i++)assert(!wr_owner_admission_poll(&gate,stamp+i)&&gate.client.serial==serial);
 if(kind==0){
  assert(xw_mode_policy_request(&policy,XW_WIRELESS_MODE_WIFI)==XW_MODE_PENDING);
  rc=wr_owner_admission_poll(&gate,stamp+200);assert(rc==XW_MODE_PENDING);
  for(unsigned i=0;rc==XW_MODE_PENDING;i++){
   assert(i<10);int step=xw_mode_channel_step(&channel);assert(step==0||step==XW_MODE_PENDING);
   rc=wr_owner_admission_poll(&gate,stamp+201+i);
  }
  assert(rc==XW_MODE_DENIED);
 }else if(kind==1){
  assert(wr_owner_admission_poll(&gate,stamp+200)==XW_MODE_PENDING);
  assert(wr_owner_admission_poll(&gate,stamp+900)==XW_MODE_PENDING);
  assert(wr_owner_admission_poll(&gate,stamp+1000)==XW_MODE_FAULT);
 }else if(kind==2){
  assert(wr_owner_admission_poll(&gate,stamp+100)==XW_MODE_FAULT);
 }else{
  assert(!xw_mode_channel_close(&channel));
  assert(wr_owner_admission_poll(&gate,stamp+200)==XW_MODE_FAULT);
 }
 assert(!wr_owner_admission_allowed(&gate)&&policy.state.active);
 assert(wr_owner_admission_close(&gate)>=0);if(channel.bound)assert(!xw_mode_channel_close(&channel));
 rc=xw_mode_policy_quiesce(&policy,&lease);assert(rc==0||rc==XW_MODE_PENDING);
 assert(!xw_mode_policy_release(&policy,&lease,1));
}
int main(void){assert(!pthread_key_create(&poll_trace,0));for(unsigned kind=0;kind<6;kind++)owner_admission_case(kind);for(unsigned kind=0;kind<4;kind++)owner_admission_periodic(kind);retirement_codec();scenario(0);scenario(1);scenario(2);admin_scenario();managed_client_scenario(0);managed_client_scenario(1);observed_worker();reused_client_fd();native_worker_permission(0);native_worker_permission(1);native_worker_permission(2);native_worker_renewal();native_worker_delivery();publisher_failure_cleanup();boot_condition_case(0);boot_condition_case(1);automatic_failure_case(1);automatic_failure_case(2);automatic_failure_case(3);settings_radio_authority(0);settings_radio_authority(1);wireless_stop_independent();wireless_handoff_independent();native_worker_automatic_delivery(0);assert(!pthread_key_delete(poll_trace));puts("WIRELESS_MODE_CHANNEL_PASS");return 0;}
