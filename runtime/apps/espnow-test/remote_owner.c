/* Finite hardware qualification entry, not a production system daemon.
 * Retain the existing physically exercised lab guards/security setup unchanged.
 * The legacy entry is excluded; only this explicit FD entry runs. */
#define XNOW_TEST_NO_MAIN
#include "main.c"
#include "../../platform/espnow/xnow_owner_runtime.h"
#if defined(XNOW_REMOTE_MANAGED) && (!defined(XNOW_REMOTE_MODE_VIEW) || !defined(XNOW_REMOTE_POWER_OFF))
#error Managed owner requires mode-view admission and power-off retirement
#endif
#ifdef XNOW_REMOTE_MODE_VIEW
#include "../wireless-remote/owner_admission.h"
#include "../../store/deadline.h"
static struct wr_owner_admission mode_admission;
static int owner_number64(const char *p,uint64_t *out){
 if(!p||!*p||!out)return -1;
 uint64_t n=0;
 for(;*p;p++){if(*p<'0'||*p>'9'||n>(UINT64_MAX-(unsigned)(*p-'0'))/10)return -1;n=n*10+(unsigned)(*p-'0');}
 if(!n)return -1;
 *out=n;return 0;
}
static int owner_mode_await(void){
 unsigned long long began;if(hb_monotonic_millis(&began))return -1;
 for(;;){
  if(stop_requested)return -1;
  unsigned long long now;if(hb_monotonic_millis(&now)||now<began||now-began>=15000u)return -1;
  int rc=wr_owner_admission_poll(&mode_admission,now);
  if(!rc){puts("REMOTE_RF_MODE_VIEW_AUTHORIZED");return 0;}
  if(rc!=XW_MODE_PENDING)return -1;
  usleep(10000);
 }
}
static int owner_mode_start(int fd,const struct xw_wireless_lease *lease){
 if(wr_owner_admission_open(&mode_admission,fd,lease)||close(fd))return -1;
 return owner_mode_await();
}
#endif
#ifdef XNOW_REMOTE_POWER_OFF
#include "../wireless-remote/radio_stop.h"
#endif
extern int owner_fcntl(int,int,...) __asm__("fcntl");
static struct xnow_full_control owner_control;
static struct xnow_owner_runtime owner_runtime;
static struct xnow_owner_gate owner_gate;
static struct xnow_owner_commands owner_commands;
static struct xnow_owner_stream owner_stream;
#ifdef XNOW_REMOTE_POWER_OFF
/* Operator-qualified finite lab profile only. The cooperative gate and IPC
 * identity do not prove global Sony/APF ownership; keep that limit explicit. */
static int power_off_admission(void *context){
 return context==&owner_gate&&xnow_owner_gate_radio_valid(context)&&
        !xnow_manager_stock_ipc_guard(0,XNOW_SESSION_RELEASE);
}
static int remote_controller_step(void *context,struct xnow_full_control *control){
 if(control!=&owner_control)return XNOW_ARGUMENT;
 return control->stop_requested?wr_radio_stop_step(control,context,power_off_admission):xnow_full_control_step(control);
}
#endif
#ifndef XNOW_REMOTE_WINDOW_MS
#define XNOW_REMOTE_WINDOW_MS 60000u
#endif
static unsigned completed_packets,failed_packets;static uint32_t last_completion;
static unsigned storage_calls;static uint32_t storage_ms,storage_max;
/* Full root/candidate hashes remain in candidate_guard before every controller
 * mutation. READY data processing needs current mount/ownership checks, not
 * repeated hashing of the same read-only root and already loaded image. */
static int live_storage(void *context){
 (void)context;if(pn_guard(0))return -1;
 FILE *f=fopen("/proc/mounts","r");if(!f)return -1;
 char line[1024],dev[256],mount[256],type[64],opts[256];unsigned roots=0;int bad=0;
 while(fgets(line,sizeof line,f)){
  if(!strchr(line,'\n')||stock_sscanf(line,"%255s %255s %63s %255s",dev,mount,type,opts)!=4){bad=1;break;}
  if(!strcmp(mount,"/")&&strcmp(type,"rootfs")){roots++;if(strcmp(dev,"/dev/root")||strcmp(type,"ext2")||strncmp(opts,"ro,",3))bad=1;}
 }
 if(ferror(f))bad=1;
 if(fclose(f))bad=1;
 return bad||roots!=1?-1:0;
}
static int measured_storage(void *context){
 uint32_t before=milliseconds();int rc=live_storage(context);uint32_t elapsed=milliseconds()-before;
 storage_calls++;if(elapsed<0x80000000u){storage_ms+=elapsed;if(elapsed>storage_max)storage_max=elapsed;}return rc;
}
static struct xnow_endpoint *owner_endpoint(void *context){return xnow_full_control_endpoint(context);}
static void owner_stop(void *context){xnow_full_control_stop(context);}
static int owner_prepare(void *context,struct xnow_endpoint *endpoint,const uint8_t local[6]){
 (void)context;if(endpoint!=&owner_control.endpoint||memcmp(local,owner_control.local_mac,6))return -1;
 int rc=prepare_security(0,&owner_control);if(rc)return rc;
 struct xnow_peer peer;memset(&peer,0,sizeof peer);memcpy(peer.address,peer_address,6);
 memcpy(peer.lmk,session_keys+16,16);peer.channel=8;peer.version=2;peer.encrypt=1;
 rc=xnow_endpoint_add(endpoint,&peer);volatile uint8_t *p=(volatile uint8_t *)&peer;for(size_t i=0;i<sizeof peer;i++)p[i]=0;
 if(!rc){printf("REMOTE_RF_READY mac=%02x%02x%02x%02x%02x%02x\n",local[0],local[1],local[2],local[3],local[4],local[5]);fflush(stdout);}return rc;
}
static int owner_close_data(void *context){
 (void)context;int failed=0;if(pn_files.directory>=0){failed=close(pn_files.directory);pn_files.directory=-1;}
#ifdef XNOW_REMOTE_MODE_VIEW
 if(mode_admission.client.bound&&!mode_admission.closed&&wr_owner_admission_close(&mode_admission)<0)failed=1;
#endif
 volatile uint8_t *p=session_keys;for(unsigned i=0;i<sizeof session_keys;i++)p[i]=0;
 if(chdir("/"))failed=1;
 return failed?-1:0;
}
static int owner_fd(const char *s){unsigned n=0;if(!s||!*s)return -1;for(;*s;s++){if(*s<'0'||*s>'9'||n>6553)return -1;n=n*10+(unsigned)(*s-'0');}return n>=3&&n<=65535?(int)n:-1;}
/* Only used before the first owner_runtime_step: no driver/manager mutation
 * has occurred. EOF follows process exit, closing any local initialization FDs. */
static int owner_startup_failed(int writer,const uint8_t cookie[16]){
 struct stat st;int flags=owner_fcntl(writer,F_GETFL);
 if(flags>=0&&(flags&O_ACCMODE)==O_WRONLY&&!fstat(writer,&st)&&S_ISFIFO(st.st_mode)){
  uint8_t record[32]={0};memcpy(record,"XRFDONE1",8);memcpy(record+8,cookie,16);record[24]=1;record[28]=1;
  ssize_t n;do{n=write(writer,record,sizeof record);}while(n<0&&errno==EINTR);(void)n;
 }
 owner_close_data(0);return 69;
}
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--measure-storage")){
  uint32_t before=milliseconds();int result=storage(0);uint32_t elapsed=milliseconds()-before;
  printf("REMOTE_STORAGE_READONLY result=%d elapsed_ms=%u\n",result,elapsed);return result?1:0;
 }
 if(argc==2&&!strcmp(argv[1],"--measure-live-storage")){
  uint32_t before=milliseconds();int result=live_storage(0);uint32_t elapsed=milliseconds()-before;
  printf("REMOTE_LIVE_STORAGE_READONLY result=%d elapsed_ms=%u\n",result,elapsed);return result?1:0;
 }
 if(argc==2&&!strcmp(argv[1],"--help")){
#ifdef XNOW_REMOTE_MODE_VIEW
  puts("MODE_VIEW_REQUIRED: append --mode-view FD GENERATION SERIAL CONSUMER. No RF initialization before matching READ capability admission.");
#endif
#ifdef XNOW_REMOTE_POWER_OFF
  puts("POWER_OFF_EXIT: requires initially idle ordinary Wi-Fi; no borrowed connection; stock power-off before fin. Operator-qualified lab admission only.");
#endif
#ifdef XNOW_REMOTE_MANAGED
  puts("Supervised RF owner: inherited mode-view admission, parent command lifetime and continuous authorization refresh. No fixed run window. Cooperative retirement and verified DONE+EOF remain required. Device qualification is incomplete.");
#else
  printf("Remote RF qualification owner: --owner COMMAND_FD RESPONSE_FD COMPLETION_FD COOKIE32 PEER_MAC12 --charger-confirmed --exclusive-radio-confirmed\nFinite %u-second encrypted owner. Uses existing espnow-test candidate/session.keys/pn inputs.\nOriginal root/firmware guards remain active. No updater or root writes.\nMust be supervised through actual DONE+EOF; uncertain ownership retains process.\nLab-only test context; not a permanent system service or global Wi-Fi exclusion proof.\n",XNOW_REMOTE_WINDOW_MS/1000u);
#endif
  return 0;
 }
 if(argc!=
#ifdef XNOW_REMOTE_MODE_VIEW
 14
#else
 9
#endif
 ||strcmp(argv[1],"--owner")||strcmp(argv[7],"--charger-confirmed")||strcmp(argv[8],"--exclusive-radio-confirmed")||strlen(argv[5])!=32||strlen(argv[6])!=12)return 64;
 int input=owner_fd(argv[2]),output=owner_fd(argv[3]),writer=owner_fd(argv[4]);
 if(input<0||output<0||writer<0||input==output||input==writer||output==writer)return 64;
#ifdef XNOW_REMOTE_MODE_VIEW
 int mode_fd=owner_fd(argv[10]);struct xw_wireless_lease mode_lease={0};mode_lease.mode=XW_WIRELESS_MODE_ESPNOW;
 if(strcmp(argv[9],"--mode-view")||mode_fd<3||mode_fd==input||mode_fd==output||mode_fd==writer||
    owner_number64(argv[11],&mode_lease.generation)||owner_number64(argv[12],&mode_lease.serial)||owner_number64(argv[13],&mode_lease.consumer))return 64;
#endif
 uint8_t cookie[16];unsigned any=0;
 for(unsigned i=0;i<16;i++){int a=hex_digit(argv[5][2*i]),b=hex_digit(argv[5][2*i+1]);if(a<0||b<0)return 64;cookie[i]=(uint8_t)(a*16+b);any|=cookie[i];}if(!any)return 64;
 any=0;for(unsigned i=0;i<6;i++){int a=hex_digit(argv[6][2*i]),b=hex_digit(argv[6][2*i+1]);if(a<0||b<0)return 64;peer_address[i]=(uint8_t)(a*16+b);any|=peer_address[i];}if(!any||(peer_address[0]&1))return 64;
 if(signal(SIGTERM,request_stop)==SIG_ERR||signal(SIGHUP,request_stop)==SIG_ERR||signal(SIGPIPE,SIG_IGN)==SIG_ERR)return 71;
 pn_files.directory=-1;
#ifdef XNOW_REMOTE_MODE_VIEW
 if(owner_mode_start(mode_fd,&mode_lease))return owner_startup_failed(writer,cookie);
#endif
 if(candidate_guard(0,XNOW_SESSION_PREFLIGHT)||xnow_manager_stock_ipc_guard(0,XNOW_SESSION_ACQUIRE)||read_session_keys())return owner_startup_failed(writer,cookie);
#ifdef XNOW_REMOTE_MODE_VIEW
 if(owner_mode_await())return owner_startup_failed(writer,cookie);
#endif
 if(xnow_owner_gate_open(&owner_gate,input,&stop_requested,0,measured_storage))return owner_startup_failed(writer,cookie);
 struct xnow_full_control_options options={&owner_gate,&xnow_full_compiled_profile,candidate_guard,xnow_manager_stock_ipc_guard,xnow_owner_gate_radio_valid,rng4,8,1,17};
#ifdef XNOW_REMOTE_POWER_OFF
 options.allow_disconnect=0;
#endif
 if(xnow_full_control_init(&owner_control,&options)||xnow_owner_commands_init(&owner_commands,&owner_control,owner_endpoint,owner_stop))return owner_startup_failed(writer,cookie);
 if(xnow_owner_stream_open(&owner_stream,&owner_commands,input,output))return owner_startup_failed(writer,cookie);
 close(input);close(output);
 if(xnow_owner_runtime_init(&owner_runtime,&owner_control,&owner_gate,&owner_stream,&owner_commands,writer,cookie,0,owner_prepare,owner_close_data))return owner_startup_failed(writer,cookie);
 volatile uint8_t *secret=cookie;for(unsigned i=0;i<16;i++)secret[i]=0;
#ifdef XNOW_REMOTE_MODE_VIEW
 unsigned long long began=0;if(hb_monotonic_millis(&began))stop_requested=1;
#else
 uint32_t began=milliseconds();if(!began)stop_requested=1;
#endif
 puts("REMOTE_RF_OWNER_STARTING");fflush(stdout);
 for(;;){
#ifdef XNOW_REMOTE_MODE_VIEW
  unsigned long long now=began;
  if(hb_monotonic_millis(&now)||now<began)stop_requested=1;
#ifndef XNOW_REMOTE_MANAGED
  if(now-began>=XNOW_REMOTE_WINDOW_MS)stop_requested=1;
#endif
  if(!stop_requested&&wr_owner_admission_poll(&mode_admission,now)<0)stop_requested=1;
#else
  uint32_t now=milliseconds();if(!now||(uint32_t)(now-began)>=XNOW_REMOTE_WINDOW_MS)stop_requested=1;
#endif
  int rc;
#ifdef XNOW_REMOTE_POWER_OFF
  rc=xnow_owner_runtime_step_with_controller(&owner_runtime,&owner_gate,remote_controller_step);
#else
  rc=xnow_owner_runtime_step(&owner_runtime);
#endif
  if(owner_stream.output_bytes==32&&!memcmp(owner_stream.response,"XNT1",4)){
   const uint8_t *p=owner_stream.response;uint32_t token=(uint32_t)p[8]|(uint32_t)p[9]<<8|(uint32_t)p[10]<<16|(uint32_t)p[11]<<24;
   if(token!=last_completion){last_completion=token;completed_packets++;
    if(p[12]||p[13]||p[14]||p[15]||p[24]||p[25]||p[26]||p[27]){failed_packets++;if(failed_packets==1)printf("REMOTE_RF_FIRST_TX_FAILURE result=%u stock=%u\n",(unsigned)p[12],(unsigned)p[24]);}
   }
  }
  if(!rc){printf("REMOTE_RF_TX_SUMMARY completed=%u failed=%u\n",completed_packets,failed_packets);printf("REMOTE_PERF_STORAGE calls=%u total_ms=%u max_ms=%u\n",storage_calls,storage_ms,storage_max);printf("REMOTE_RF_OWNER_RETIRED application_failure=%d\n",owner_runtime.application_failure);return owner_runtime.application_failure?1:0;}
  if(rc<0){puts("REMOTE_RF_OWNER_UNCERTAIN");fflush(stdout);for(;;)pause();}
  usleep(10000);
 }
}
