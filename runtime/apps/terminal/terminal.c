/* On-demand TLS 1.2 terminal. All application persistence is user-storage only.
 * One authenticated session; bounded nonblocking network/PTY buffers. */
#define _GNU_SOURCE
#include "terminal.h"
#include "terminal_firewall.h"
#include <bearssl.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/abi.h"
/* Old Sony ioctl is variadic; modern headers redirect some tty calls to time64. */
extern int term_ioctl(int, unsigned long, ...) __asm__("ioctl");
extern int term_fcntl(int, int, ...) __asm__("fcntl");
extern int term_setsockopt(int,int,int,const void *,socklen_t) __asm__("setsockopt");
extern int term_sscanf(const char *,const char *,...) __asm__("sscanf");
struct term_timeval {long seconds,microseconds;};
extern int term_gettimeofday(struct term_timeval *,void *) __asm__("gettimeofday");
#define CAP 8192
static struct {
 struct hb_terminal_firewall firewall;
 int listener,client,pty,directory,authenticated,failures;
 pid_t child;
 unsigned long long deadline,last_activity,cooldown;
 char code[33],status[40];
 unsigned char certificate[4096],private_key[2048],tlsbuf[BR_SSL_BUFSIZE_BIDI];
 unsigned char incoming[CAP],outgoing[CAP];
 size_t certlen,inlen,outlen;
 br_skey_decoder_context decoder;
 br_ssl_server_context ssl;
 br_x509_certificate cert;
} t;
static unsigned long long now_ms(void) {
 struct term_timeval v;if(term_gettimeofday(&v,0)||v.seconds<0)return 0;
 return (unsigned long long)v.seconds*1000+(unsigned)v.microseconds/1000;
}
static void wipe(void *p,size_t n){volatile unsigned char *v=p;while(n--)*v++=0;}
static int random_bytes(void *p,size_t n){
 int fd=open("/dev/urandom",O_RDONLY|O_NOFOLLOW);if(fd<0)return -1;
 unsigned char *b=p;size_t used=0;
 while(used<n){ssize_t r=read(fd,b+used,n-used);if(r<0&&errno==EINTR)continue;if(r<=0){close(fd);return -1;}used+=(size_t)r;}
 return close(fd);
}
static int nonblock(int fd){int f=term_fcntl(fd,F_GETFL);return f<0||term_fcntl(fd,F_SETFL,f|O_NONBLOCK)<0||term_fcntl(fd,F_SETFD,FD_CLOEXEC)<0?-1:0;}
static int read_file(int directory,const char *name,unsigned char *out,size_t cap,size_t *length){
 char path[96];snprintf(path,sizeof path,"/proc/self/fd/%d/%s",directory,name);
 int fd=open(path,O_RDONLY|O_NOFOLLOW);if(fd<0)return -1;
 struct stat s;int rc=-1;
 if(fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_size<=0||(unsigned long long)s.st_size>cap)goto done;
 size_t used=0;while(used<(size_t)s.st_size){ssize_t n=read(fd,out+used,(size_t)s.st_size-used);if(n<0&&errno==EINTR)continue;if(n<=0)goto done;used+=(size_t)n;}
 *length=used;rc=0;
done:if(close(fd))rc=-1;return rc;
}
/* Read-only inspection; no fallback to a directory on the system filesystem. */
static int user_volume(void){
 FILE *f=fopen("/proc/mounts","r");if(!f)return -1;
 char line[1024],dev[256],path[256],fs[64],opts[256];int found=0,bad=0;
 while(fgets(line,sizeof line,f)){
  if(!strchr(line,'\n')||term_sscanf(line,"%255s %255s %63s %255s",dev,path,fs,opts)!=4){bad=1;break;}
  if(!strcmp(path,"/contents")){found++;if(strcmp(dev,"/dev/mtdblock/2")||strcmp(fs,"vfat"))bad=1;}
  else if(!strncmp(path,"/contents/",10))bad=1;
 }
 if(ferror(f))bad=1;if(fclose(f))bad=1;
 return found==1&&!bad?0:-1;
}
static int open_directory(const char *path,int test){
 if(!test&&user_volume())return -1;
 int fd=open(test?path:"/contents",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;
 if(test)return fd;
 struct stat root,volume,s;int rootfd=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
 if(rootfd<0){close(fd);return -1;}
 int bad=fstat(rootfd,&root)||fstat(fd,&volume)||root.st_dev==volume.st_dev;close(rootfd);
 if(bad){close(fd);return -1;}
 const char *parts[]={"HOMEBREW",!strcmp(path,"/contents/HOMEBREW/data/terminal")?"data":"apps","terminal"};
 for(unsigned i=0;i<3;i++){
  char p[96];snprintf(p,sizeof p,"/proc/self/fd/%d/%s",fd,parts[i]);
  int next=open(p,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
  if(next<0||fstat(next,&s)||!S_ISDIR(s.st_mode)||s.st_dev!=volume.st_dev){if(next>=0)close(next);close(fd);return -1;}
  close(fd);fd=next;
 }
 return fd;
}
static void stop_shell(void){
 if(t.child>0){
  int foreground=0;if(t.pty>=0&&!term_ioctl(t.pty,0x540f,&foreground)&&foreground>1&&foreground!=getpgrp())kill(-foreground,SIGHUP);
  kill(-t.child,SIGHUP);kill(t.child,SIGHUP);
  for(unsigned i=0;i<20;i++){pid_t r=waitpid(t.child,0,WNOHANG);if(r==t.child||(r<0&&errno==ECHILD)){t.child=0;break;}usleep(10000);}
  if(t.child>0){kill(-t.child,SIGKILL);kill(t.child,SIGKILL);while(waitpid(t.child,0,0)<0&&errno==EINTR){}t.child=0;}
 }
 if(t.pty>=0){close(t.pty);t.pty=-1;}
}
static void end_session(const char *status){
 stop_shell();if(t.client>=0)close(t.client);t.client=-1;t.authenticated=0;t.inlen=t.outlen=0;
 wipe(&t.ssl,sizeof t.ssl);wipe(t.tlsbuf,sizeof t.tlsbuf);wipe(t.incoming,sizeof t.incoming);wipe(t.outgoing,sizeof t.outgoing);
 snprintf(t.status,sizeof t.status,"%s",status);
}
int hb_terminal_close(void){end_session("STOPPED");if(t.listener>=0)close(t.listener);if(t.directory>=0)close(t.directory);t.listener=t.directory=-1;wipe(t.code,sizeof t.code);wipe(t.private_key,sizeof t.private_key);wipe(&t.decoder,sizeof t.decoder);int rc=hb_terminal_firewall_close(&t.firewall,hb_terminal_firewall_native);if(rc)snprintf(t.status,sizeof t.status,"FIREWALL RESTORE FAILED");return rc;}
static int queue_frame(const void *p,size_t n){
 if(n>4096||t.outlen+n+3>CAP)return -1;
 t.outgoing[t.outlen++]='D';t.outgoing[t.outlen++]=(unsigned char)(n>>8);t.outgoing[t.outlen++]=(unsigned char)n;
 memcpy(t.outgoing+t.outlen,p,n);t.outlen+=n;return 0;
}
static int start_shell(unsigned rows,unsigned cols){
 int master=open("/dev/ptmx",O_RDWR|O_NOCTTY|O_NOFOLLOW);if(master<0)return -1;
 int unlock=0;unsigned number=0;
 if(term_ioctl(master,0x40045431u,&unlock)||term_ioctl(master,0x80045430u,&number)||number>1048575){close(master);return -1;}
 char path[64];snprintf(path,sizeof path,"/dev/pts/%u",number);
 struct winsize size;memset(&size,0,sizeof size);size.ws_row=(unsigned short)rows;size.ws_col=(unsigned short)cols;
 if(term_ioctl(master,0x5414,&size)||nonblock(master)){close(master);return -1;}
 /* No framebuffer/touch fds are inherited by exec: close all except stdio. */
 pid_t pid=fork();if(pid<0){close(master);return -1;}
 if(!pid){
  if(setsid()<0)_exit(125);
  int slave=open(path,O_RDWR|O_NOCTTY);if(slave<0||term_ioctl(slave,0x540e,0)||fchdir(t.directory))_exit(125);
  char cwd[4096],home[4102],temporary[4104];if(!getcwd(cwd,sizeof cwd))_exit(125);
  snprintf(home,sizeof home,"HOME=%s",cwd);snprintf(temporary,sizeof temporary,"TMPDIR=%s",cwd);
  if(dup2(slave,0)<0||dup2(slave,1)<0||dup2(slave,2)<0)_exit(125);
  long max=sysconf(_SC_OPEN_MAX);if(max<0||max>65536)max=65536;for(int i=3;i<max;i++)close(i);
  signal(SIGTERM,SIG_DFL);signal(SIGINT,SIG_DFL);signal(SIGPIPE,SIG_DFL);signal(SIGHUP,SIG_DFL);signal(SIGCHLD,SIG_DFL);
  /* No history, sessions, keys or logs are automatically written by the app.
   * Explicit commands still execute with the real user's full permissions. */
  char *env[]={"PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin","TERM=xterm",home,temporary,"HISTFILE=/dev/null","LC_ALL=C",0};
  char *args[]={"/bin/sh","-i",0};execve(args[0],args,env);_exit(127);
 }
 t.child=pid;t.pty=master;
 char b[160];int n=snprintf(b,sizeof b,"\r\nX1060 terminal: uid=%u euid=%u gid=%u\r\nType exit to disconnect. Ctrl-C interrupts.\r\n",(unsigned)getuid(),(unsigned)geteuid(),(unsigned)getgid());
 return queue_frame(b,(size_t)n);
}
static int valid_window(unsigned r,unsigned c){return r>=1&&r<=500&&c>=1&&c<=500;}
int hb_terminal_protocol_selftest(void){return valid_window(24,80)&&!valid_window(0,80)&&!valid_window(24,501)?0:1;}
static int consume(void){
 if(!t.authenticated){
  /* Fixed-length login; no shell is forked before complete authentication. */
  const size_t need=40;if(t.inlen<need)return 0;
  unsigned difference=0;const char prefix[]="XTERM1 ";
  for(unsigned i=0;i<7;i++)difference|=t.incoming[i]^(unsigned char)prefix[i];
  for(unsigned i=0;i<32;i++)difference|=t.incoming[i+7]^(unsigned char)t.code[i];
  difference|=t.incoming[39]^'\n';if(difference)return -2;
  memmove(t.incoming,t.incoming+need,t.inlen-need);t.inlen-=need;
  if(start_shell(24,80))return -1;
  t.authenticated=1;t.failures=0;snprintf(t.status,sizeof t.status,"CONNECTED");
 }
 while(t.inlen>=3){
  unsigned type=t.incoming[0];size_t n=((size_t)t.incoming[1]<<8)|t.incoming[2];
  if(n>4096||!n||!((type=='D')||(type=='W'&&n==4)))return -1;
  if(t.inlen<n+3)return 0;
  if(type=='W'){
   unsigned rows=((unsigned)t.incoming[3]<<8)|t.incoming[4],cols=((unsigned)t.incoming[5]<<8)|t.incoming[6];
   if(!valid_window(rows,cols))return -1;
   struct winsize size;memset(&size,0,sizeof size);size.ws_row=(unsigned short)rows;size.ws_col=(unsigned short)cols;if(term_ioctl(t.pty,0x5414,&size))return -1;
  }else{
   ssize_t written=write(t.pty,t.incoming+3,n);
   if(written<0&&(errno==EINTR||errno==EAGAIN))return 0;
   if(written<=0)return -1;
   if((size_t)written<n){
    memmove(t.incoming+3,t.incoming+3+written,t.inlen-3-(size_t)written);t.inlen-=(size_t)written;n-=(size_t)written;
    t.incoming[1]=(unsigned char)(n>>8);t.incoming[2]=(unsigned char)n;return 0;
   }
  }
  memmove(t.incoming,t.incoming+n+3,t.inlen-n-3);t.inlen-=n+3;
 }
 return 0;
}
int hb_terminal_open(const char *directory,unsigned port,int test_mode){
 memset(&t,0,sizeof t);t.listener=t.client=t.pty=t.directory=-1;
 if(!directory||port<1||port>65535)return -1;
 t.directory=open_directory(directory,test_mode);if(t.directory<0)goto fail;
 int identity=test_mode?-1:open_directory("/contents/HOMEBREW/data/terminal",0);
 int keys=identity>=0?identity:t.directory;size_t keylen=0;
 int identity_error=read_file(keys,"server-cert.der",t.certificate,sizeof t.certificate,&t.certlen)||read_file(keys,"server-key.der",t.private_key,sizeof t.private_key,&keylen);
 if(identity>=0)close(identity);
 if(identity_error){hb_terminal_close();snprintf(t.status,sizeof t.status,"PAIRING SETUP REQUIRED");return -1;}
 br_skey_decoder_init(&t.decoder);br_skey_decoder_push(&t.decoder,t.private_key,keylen);
 const br_ec_private_key *key=br_skey_decoder_get_ec(&t.decoder);if(!key||key->curve!=BR_EC_secp256r1||br_skey_decoder_last_error(&t.decoder))goto fail;
 /* Stable for this personal device identity. Never derive the login secret
  * from the public certificate fingerprint or regenerate it per connection. */
 static const char domain[]="X1000-WIFI-TERMINAL-CODE-v1";
 br_hmac_key_context code_key;br_hmac_context code_hash;unsigned char digest[32];
 br_hmac_key_init(&code_key,&br_sha256_vtable,t.private_key,keylen);
 br_hmac_init(&code_hash,&code_key,0);br_hmac_update(&code_hash,domain,sizeof domain-1);br_hmac_out(&code_hash,digest);
 for(unsigned i=0;i<16;i++)snprintf(t.code+i*2,3,"%02x",digest[i]);
 wipe(digest,sizeof digest);wipe(&code_key,sizeof code_key);wipe(&code_hash,sizeof code_hash);
 signal(SIGPIPE,SIG_IGN);
 t.listener=socket(AF_INET,SOCK_STREAM,0);if(t.listener<0||nonblock(t.listener))goto fail;
 int yes=1;if(term_setsockopt(t.listener,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof yes))goto fail;
 struct sockaddr_in address;memset(&address,0,sizeof address);address.sin_family=AF_INET;address.sin_port=htons((unsigned short)port);address.sin_addr.s_addr=htonl(test_mode?INADDR_LOOPBACK:INADDR_ANY);
 if(bind(t.listener,(struct sockaddr *)&address,sizeof address)||listen(t.listener,2))goto fail;
 if(!test_mode&&(port!=HB_TERM_PORT||hb_terminal_firewall_open(&t.firewall,hb_terminal_firewall_native)))goto firewall_fail;
 snprintf(t.status,sizeof t.status,"WAITING FOR COMPUTER");return 0;
firewall_fail:hb_terminal_close();snprintf(t.status,sizeof t.status,"FIREWALL OPEN FAILED");return -1;
fail:hb_terminal_close();snprintf(t.status,sizeof t.status,"START FAILED");return -1;
}
void hb_terminal_tick(void){
 unsigned long long now=now_ms();if(!now){end_session("CLOCK ERROR");return;}
 if(t.client<0){
  if(now<t.cooldown)return;
  int fd=accept(t.listener,0,0);if(fd<0)return;
  if(nonblock(fd)){close(fd);return;}
  t.client=fd;t.inlen=t.outlen=0;t.authenticated=0;t.deadline=now+20000;t.last_activity=now;
  t.cert.data=t.certificate;t.cert.data_len=t.certlen;
  br_ssl_server_init_minf2g(&t.ssl,&t.cert,1,br_skey_decoder_get_ec(&t.decoder));
  br_ssl_engine_set_versions(&t.ssl.eng,BR_TLS12,BR_TLS12);
  br_ssl_engine_set_buffer(&t.ssl.eng,t.tlsbuf,sizeof t.tlsbuf,1);
  unsigned char seed[48];if(random_bytes(seed,sizeof seed)){end_session("RANDOM ERROR");return;}
  br_ssl_engine_inject_entropy(&t.ssl.eng,seed,sizeof seed);wipe(seed,sizeof seed);
  if(!br_ssl_server_reset(&t.ssl)){end_session("TLS ERROR");return;}
  snprintf(t.status,sizeof t.status,"AUTHENTICATING");
 }
 if((!t.authenticated&&now>t.deadline)||(t.authenticated&&now-t.last_activity>1800000)){
  t.failures++;t.cooldown=now+1000;end_session("SESSION TIMED OUT");return;
 }
 int rc=consume();if(rc){t.failures++;t.cooldown=now+(t.failures>=5?30000:1000);end_session(rc==-2?"WRONG CONNECTION CODE":"SESSION ERROR");return;}
 /* A bounded amount of work per UI frame; no blocking socket callbacks. */
 for(unsigned round=0;round<24;round++){
  unsigned state=br_ssl_engine_current_state(&t.ssl.eng);int progress=0;size_t n;unsigned char *p;
  if(state&BR_SSL_CLOSED){t.failures++;t.cooldown=now+1000;end_session("DISCONNECTED");return;}
  if(state&BR_SSL_SENDREC){p=br_ssl_engine_sendrec_buf(&t.ssl.eng,&n);ssize_t r=send(t.client,p,n,MSG_NOSIGNAL);if(r>0){br_ssl_engine_sendrec_ack(&t.ssl.eng,(size_t)r);progress=1;}else if(r<0&&errno!=EAGAIN&&errno!=EINTR){end_session("DISCONNECTED");return;}}
  if(state&BR_SSL_RECVREC){p=br_ssl_engine_recvrec_buf(&t.ssl.eng,&n);ssize_t r=recv(t.client,p,n,0);if(r>0){br_ssl_engine_recvrec_ack(&t.ssl.eng,(size_t)r);progress=1;}else if(!r||(r<0&&errno!=EAGAIN&&errno!=EINTR)){end_session("DISCONNECTED");return;}}
  state=br_ssl_engine_current_state(&t.ssl.eng);
  if((state&BR_SSL_RECVAPP)&&t.inlen<CAP){p=br_ssl_engine_recvapp_buf(&t.ssl.eng,&n);if(n>CAP-t.inlen)n=CAP-t.inlen;memcpy(t.incoming+t.inlen,p,n);t.inlen+=n;br_ssl_engine_recvapp_ack(&t.ssl.eng,n);progress=1;t.last_activity=now;}
  if((state&BR_SSL_SENDAPP)&&t.outlen){p=br_ssl_engine_sendapp_buf(&t.ssl.eng,&n);if(n>t.outlen)n=t.outlen;memcpy(p,t.outgoing,n);memmove(t.outgoing,t.outgoing+n,t.outlen-n);t.outlen-=n;br_ssl_engine_sendapp_ack(&t.ssl.eng,n);br_ssl_engine_flush(&t.ssl.eng,0);progress=1;}
  if(!progress)break;
 }
 if(t.authenticated&&t.outlen+4099<=CAP){
  unsigned char b[4096];ssize_t n=read(t.pty,b,sizeof b);
  if(n>0){queue_frame(b,(size_t)n);t.last_activity=now;}
  else if(!n||(n<0&&errno==EIO)){
   /* Drain all already encrypted/output bytes before closing on PTY EOF. */
   if(!t.outlen&&!(br_ssl_engine_current_state(&t.ssl.eng)&BR_SSL_SENDREC)){end_session("SHELL EXITED");return;}
  }else if(errno!=EAGAIN&&errno!=EINTR){end_session("PTY ERROR");return;}
 }
}
const char *hb_terminal_code(void){return t.code;}
const char *hb_terminal_status(void){return t.status;}
unsigned hb_terminal_uid(void){return (unsigned)geteuid();}
unsigned hb_terminal_gid(void){return (unsigned)getegid();}
void hb_terminal_addresses(char out[3][24]){
 memset(out,0,3*24);int fd=socket(AF_INET,SOCK_DGRAM,0);if(fd<0)return;
 struct ifreq requests[16];struct ifconf c;c.ifc_len=sizeof requests;c.ifc_req=requests;
 if(!term_ioctl(fd,0x8912,&c)){
  unsigned count=0;for(unsigned i=0;i<(unsigned)c.ifc_len/sizeof requests[0]&&i<16&&count<3;i++){
   struct sockaddr_in *a=(struct sockaddr_in *)&requests[i].ifr_addr;
   if(a->sin_family==AF_INET&&(ntohl(a->sin_addr.s_addr)>>24)!=127){const char *ip=inet_ntoa(a->sin_addr);snprintf(out[count++],24,"%s",ip);}
  }
 }close(fd);
}
