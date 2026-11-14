/* Explicit detached full-radio experiment; no dependency on a live Terminal. */
#include "../../platform/espnow/native_entry.h"
#include "runner.h"
#include "detached.h"
static unsigned encrypted_mode, test_tx;
static int user_log(char path[160],const char *prefix) {
    FILE *mounts;char line[1024],device[256],mount[256],type[64],options[256],nextpath[128];
    const char *parts[]={"HOMEBREW","data","espnow"};
    struct stat volume,root,entry;struct statvfs space;
    unsigned found=0,i;int bad=0,dir,rootfd,fd;
    mounts=fopen("/proc/mounts","r");if(!mounts)return -1;
    while(fgets(line,sizeof(line),mounts)) {
        if(!strchr(line,'\n') || stock_sscanf(line,"%255s %255s %63s %255s",device,mount,type,options)!=4){bad=1;break;}
        if(!strcmp(mount,"/contents")){found++;if(strcmp(device,"/dev/mtdblock/2")||strcmp(type,"vfat")||
           (strcmp(options,"rw")&&strncmp(options,"rw,",3)))bad=1;}
        else if(!strncmp(mount,"/contents/",10))bad=1;
    }
    if(ferror(mounts))bad=1;
    if(fclose(mounts))bad=1;
    if(bad||found!=1)return -1;
    dir=open("/contents",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(dir<0)return -1;
    rootfd=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if(rootfd<0){close(dir);return -1;}
    bad=fstat(dir,&volume)||fstat(rootfd,&root)||volume.st_dev==root.st_dev;close(rootfd);
    for(i=0;!bad&&i<3;i++) {
        snprintf(nextpath,sizeof(nextpath),"/proc/self/fd/%d/%s",dir,parts[i]);
        fd=open(nextpath,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
        if(fd<0){bad=1;break;}
        bad=fstat(fd,&entry)||!S_ISDIR(entry.st_mode)||entry.st_dev!=volume.st_dev;
        close(dir);dir=fd;
    }
    if(bad||fstatvfs(dir,&space)||!space.f_frsize||space.f_bavail<65536/space.f_frsize+1){close(dir);return -1;}
    snprintf(path,160,"/contents/HOMEBREW/data/espnow/%s-%ld.log",prefix,(long)getpid());
    snprintf(nextpath,sizeof(nextpath),"/proc/self/fd/%d/%s-%ld.log",dir,prefix,(long)getpid());
    fd=open(nextpath,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);close(dir);
    if(fd<0)return -1;
    if(fstat(fd,&entry)||!S_ISREG(entry.st_mode)||entry.st_dev!=volume.st_dev||entry.st_nlink!=1){close(fd);return -1;}
    return fd;
}
static volatile sig_atomic_t retry_requested;
static void retry_signal(int number) { (void)number; retry_requested = 1; }
static int log_event(void *unused,const char *name,int value){(void)unused;return journal(name,value);}
static int log_frame(void *unused,const uint8_t *frame,size_t bytes){
 (void)unused;if(journal_descriptor<0||bytes>1560)return -1;
 char line[3200];int prefix=snprintf(line,sizeof line,"RAW_ACTION fcs=0 bytes=%u hex=",(unsigned)bytes);if(prefix<0)return -1;
 size_t n=(size_t)prefix;for(size_t i=0;i<bytes;i++){line[n++]="0123456789abcdef"[frame[i]>>4];line[n++]="0123456789abcdef"[frame[i]&15];}line[n++]='\n';
 if(n>8192-journal_bytes)return -1;
 for(size_t used=0;used<n;){ssize_t k=write(journal_descriptor,line+used,n-used);if(k<0&&errno==EINTR)continue;if(k<=0)return -1;used+=(size_t)k;}
 journal_bytes+=(unsigned)n;return fsync(journal_descriptor);
}
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
 native_security.pn.directory=-1;if(encrypted_mode&&probe_use_security(&run,native_security.keys+16,0,prepare_security))return 69;
 for(;;){
  uint32_t now=milliseconds();if(!now)stop_requested=1;
  int result=probe_step(&run,now,(unsigned)stop_requested);
  if(result==PROBE_DONE){if(native_security.pn.directory>=0)close(native_security.pn.directory);volatile uint8_t *key=native_security.keys;for(unsigned i=0;i<32;i++)key[i]=0;int released=xnow_owner_gate_release(&gate,&control);close(commands[0]);close(commands[1]);return run.failure||released?1:0;}
  if(result==PROBE_REPAIR){
   /* Never depend on the remote terminal for the normal completion path.
    * Abnormal restoration retains ownership; no blind retry or forced kill. */
   while(!retry_requested)usleep(500000);
   retry_requested=0;if(xnow_full_control_retry_restore(&control))for(;;)pause();
  }else if(result==PROBE_UNCERTAIN)for(;;)pause();
  usleep(20000);
 }
}
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
