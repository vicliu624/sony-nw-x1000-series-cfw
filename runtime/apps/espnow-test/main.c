/* Explicit detached full-radio experiment; no dependency on a live Terminal. */
#define EXCHANGE_GUARDS_ONLY
#include "../../platform/espnow/exchange_lab.c"
#include "../../platform/espnow/xnow_owner_gate.h"
#include "runner.h"
#include "detached.h"
#include "full_profile.h"
#include "../../platform/espnow/xnow_endpoint_security.h"
#include "../../platform/espnow/xnow_pn_file.h"
static unsigned encrypted_mode,resume_keys;static uint8_t session_keys[32];
static uint8_t peer_address[6];
static struct xnow_pn_file pn_files;static struct xnow_endpoint_security security;
static int user_directory(const char *leaf){
 struct stat volume,root,entry;int fd=open("/contents",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;
 if(fstat(fd,&volume)||lstat("/",&root)||volume.st_dev==root.st_dev){close(fd);return -1;}
 const char *parts[]={"HOMEBREW","data","espnow-test",leaf};
 for(unsigned i=0;i<(leaf?4u:3u);i++){char p[128];snprintf(p,sizeof p,"/proc/self/fd/%d/%s",fd,parts[i]);int next=open(p,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(next<0||fstat(next,&entry)||!S_ISDIR(entry.st_mode)||entry.st_dev!=volume.st_dev){if(next>=0)close(next);close(fd);return -1;}close(fd);fd=next;}
 return fd;
}
static int pn_guard(void *unused){
 (void)unused;FILE *f=fopen("/proc/mounts","r");if(!f)return -1;
 char line[1024],dev[256],mount[256],type[64],opts[256];unsigned found=0;int bad=0;
 while(fgets(line,sizeof line,f)){if(!strchr(line,'\n')||stock_sscanf(line,"%255s %255s %63s %255s",dev,mount,type,opts)!=4){bad=1;break;}if(!strcmp(mount,"/contents")){found++;if(strcmp(dev,"/dev/mtdblock/2")||strcmp(type,"vfat")||strncmp(opts,"rw,",3))bad=1;}else if(!strncmp(mount,"/contents/",10))bad=1;}
 if(ferror(f))bad=1;
 if(fclose(f))bad=1;
 return bad||found!=1?-1:0;
}
static int read_session_keys(void){
 if(pn_guard(0))return -1;
 int dir=user_directory(0);if(dir<0)return -1;char p[128];snprintf(p,sizeof p,"/proc/self/fd/%d/session.keys",dir);
 int fd=open(p,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);struct stat s,volume;int bad=fd<0||fstat(dir,&volume)||fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_dev!=volume.st_dev||s.st_size!=32;close(dir);
 if(bad){if(fd>=0)close(fd);return -1;}unsigned n=0;while(n<32){ssize_t k=read(fd,session_keys+n,32-n);if(k<0&&errno==EINTR)continue;if(k<=0){close(fd);return -1;}n+=(unsigned)k;}return close(fd);
}
static int reserve_logged(void *context,const uint8_t scope[32],unsigned count,uint64_t *first,uint64_t *last){
 int result=xnow_pn_file_reserve(context,scope,count,first,last);if(result)return result;
 if(journal("pn-first-lo",(int)(uint32_t)*first)||journal("pn-first-hi",(int)(uint32_t)(*first>>32)))return XNOW_PN_UNCERTAIN;
 return 0;
}
static int prepare_security(void *unused,struct xnow_full_control *c){
 (void)unused;pn_files.directory=user_directory("pn");if(pn_files.directory<0)return -1;
 struct stat s;if(fstat(pn_files.directory,&s))return -1;pn_files.device=s.st_dev;pn_files.context=0;pn_files.guard=pn_guard;
 uint8_t wire[16],rx_scope[32];struct xnow_pn tx;int result=xnow_ccmp_espnow_wire_key(session_keys,session_keys+16,wire);
 if(!result)result=xnow_pn_init(&tx,c->local_mac,wire,1024,&pn_files,xnow_pn_file_reserve);
 if(!result)result=xnow_security_rx_scope(rx_scope,c->local_mac,peer_address,wire);
 if(!result&&!resume_keys)result=xnow_pn_file_provision(&pn_files,tx.scope);
 if(!result&&!resume_keys)result=xnow_pn_file_provision(&pn_files,rx_scope);
 struct xnow_security_io io={&pn_files,reserve_logged,xnow_pn_file_load_rx,xnow_pn_file_commit_rx};
 if(!result)result=xnow_endpoint_security_attach_espnow(&c->endpoint,&security,c->local_mac,session_keys,1024,&io);
 xnow_pn_clear(&tx);volatile uint8_t *p=wire;for(unsigned i=0;i<16;i++)p[i]=0;return result;
}
static unsigned test_tx;static volatile int stop_requested;
static void request_stop(int signal_number){(void)signal_number;stop_requested=1;}
static int rng4(void *unused,uint8_t bytes[4]){uint32_t value;(void)unused;int fd=open("/dev/urandom",O_RDONLY|O_NOFOLLOW);if(fd<0)return -1;ssize_t n=read(fd,&value,4);int closed=close(fd);if(n!=4||closed)return -1;memcpy(bytes,&value,4);return 0;}
static int log_event(void *unused,const char *name,int value){(void)unused;return journal(name,value);}
static int log_frame(void *unused,const uint8_t *frame,size_t bytes){
 (void)unused;if(journal_descriptor<0||bytes>1560)return -1;
 char line[3200];int prefix=snprintf(line,sizeof line,"RAW_ACTION fcs=0 bytes=%u hex=",(unsigned)bytes);if(prefix<0)return -1;
 size_t n=(size_t)prefix;for(size_t i=0;i<bytes;i++){line[n++]="0123456789abcdef"[frame[i]>>4];line[n++]="0123456789abcdef"[frame[i]&15];}line[n++]='\n';
 if(n>8192-journal_bytes)return -1;
 for(size_t used=0;used<n;){ssize_t k=write(journal_descriptor,line+used,n-used);if(k<0&&errno==EINTR)continue;if(k<=0)return -1;used+=(size_t)k;}
 journal_bytes+=(unsigned)n;return fsync(journal_descriptor);
}
static int storage(void *unused){return candidate_guard(unused,XNOW_SESSION_CONFIGURE);}
static int run_probe(int log_fd){
 journal_descriptor=log_fd;
 if(signal(SIGUSR1,retry_signal)==SIG_ERR)return 71;
 if(journal("start-delay-seconds",3))return 73;
 for(unsigned i=0;i<6;i++)usleep(500000);
 struct xnow_owner_gate gate;int commands[2];if(pipe(commands))return 71;
 if(signal(SIGTERM,request_stop)==SIG_ERR||signal(SIGHUP,request_stop)==SIG_ERR||signal(SIGPIPE,SIG_IGN)==SIG_ERR)return 71;
 if(xnow_owner_gate_open(&gate,commands[0],&stop_requested,0,storage)){close(commands[0]);close(commands[1]);return 69;}
 struct xnow_full_control control;
 struct xnow_full_control_options options={&gate,&xnow_full_compiled_profile,candidate_guard,xnow_manager_stock_ipc_guard,xnow_owner_gate_radio_valid,rng4,8,1,encrypted_mode?17u:0u};
 if(xnow_full_control_init(&control,&options))return 69;
 struct probe_log log={0,log_event,log_frame};struct probe_run run;
 if(probe_init(&run,&control,&log,peer_address,test_tx,60))return 69;
 pn_files.directory=-1;if(encrypted_mode&&probe_use_security(&run,session_keys+16,0,prepare_security))return 69;
 for(;;){
  uint32_t now=milliseconds();if(!now)stop_requested=1;
  int result=probe_step(&run,now,(unsigned)stop_requested);
  if(result==PROBE_DONE){if(pn_files.directory>=0)close(pn_files.directory);volatile uint8_t *key=session_keys;for(unsigned i=0;i<32;i++)key[i]=0;int released=xnow_owner_gate_release(&gate,&control);close(commands[0]);close(commands[1]);return run.failure||released?1:0;}
  if(result==PROBE_REPAIR){
   /* Never depend on the remote terminal for the normal completion path.
    * Abnormal restoration retains ownership; no blind retry or forced kill. */
   while(!retry_requested)usleep(500000);
   retry_requested=0;if(xnow_full_control_retry_restore(&control))for(;;)pause();
  }else if(result==PROBE_UNCERTAIN)for(;;)pause();
  usleep(20000);
 }
}
static int hex_digit(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){
  puts("ESP-NOW local test 0.1.0-alpha.3\n--detach-rx|--detach-tx|--detach-enc-rx|--detach-enc-tx|--detach-enc-tx-resume|--detach-enc-rx-resume PEER_MAC12 --charger-confirmed --exclusive-radio-confirmed\nEncrypted modes read session.keys (PMK16+API_LMK16) and pn/ on verified user storage; fresh mode refuses existing scopes, resume never resets counters.\n60-second window, stock restoration and bounded user-volume journal. Experimental RAM image; no Sony updater or system-partition changes.\nOperator assertions do not qualify APF/USB/sleep ownership. No encrypted RF acceptance claim. Default/unknown invocation performs no radio action.");return 0;
 }
 if(argc!=5||strcmp(argv[3],"--charger-confirmed")||strcmp(argv[4],"--exclusive-radio-confirmed")||strlen(argv[2])!=12)return 64;
 if(!strcmp(argv[1],"--detach-tx"))test_tx=1;
 else if(!strcmp(argv[1],"--detach-enc-tx")){test_tx=1;encrypted_mode=1;}
 else if(!strcmp(argv[1],"--detach-enc-rx"))encrypted_mode=1;
 else if(!strcmp(argv[1],"--detach-enc-rx-resume"))encrypted_mode=resume_keys=1;
 else if(!strcmp(argv[1],"--detach-enc-tx-resume")){test_tx=1;encrypted_mode=resume_keys=1;}
 else if(strcmp(argv[1],"--detach-rx"))return 64;
 unsigned any=0;for(unsigned i=0;i<6;i++){int a=hex_digit(argv[2][2*i]),b=hex_digit(argv[2][2*i+1]);if(a<0||b<0)return 64;peer_address[i]=(uint8_t)(a*16+b);any|=peer_address[i];}if(!any||(peer_address[0]&1))return 64;
 if(candidate_guard(0,XNOW_SESSION_PREFLIGHT)||xnow_manager_stock_ipc_guard(0,XNOW_SESSION_ACQUIRE))return 69;
 if(encrypted_mode&&read_session_keys())return 73;
 char path[160];int fd=user_log(path,test_tx?"full-tx":"full-rx");if(fd<0)return 73;
 return probe_detach(fd,path,run_probe);
}
