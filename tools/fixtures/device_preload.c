/* QEMU-only device interposition. Not part of an app or firmware package. */
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <poll.h>
#include <unistd.h>
extern long x1000_oabi_call(long,long,long,long,long,long,long);
static unsigned short pixels[0xc0000/2];
static int fb,touch,mapped,event,frames,network_ready;
#include "../../runtime/native/font.inc"
static int has_text(int x,int y,const char *s,int scale){for(;*s;s++,x+=6*scale){int g=*s>='A'&&*s<='Z'?*s-'A'+10:-1;if(g<0)continue;for(int j=0;j<7;j++)for(int i=0;i<5;i++)if((pixels[(y+j*scale)*240+x+i*scale]==0xffff)!=(!!(glyph[g][j]&(1<<(4-i)))))return 0;}return 1;}
static int network(void){return getenv("HB_TEST_NETWORK")!=0;}
static int installing(void){const char *p=getenv("HB_TEST_NETWORK");return p&&!strcmp(p,"install");}
static const char *host_path(const char *p,char out[1024]){if(!strncmp(p,"/contents/",10)){const char *prefix=getenv("HB_TEST_PREFIX");if(prefix){unsigned i=0,j=0;while(prefix[i]){assert(i<1023);out[i]=prefix[i];i++;}while(p[j]){assert(i<1023);out[i++]=p[j++];}out[i]=0;return out;}}return p;}
static void append(char *d,const char *s){unsigned i=0,j=0;while(d[i])i++;while(s[j]){assert(i<1023);d[i++]=s[j++];}d[i]=0;}
static int loop(void){return getenv("HB_TEST_MODE")!=0;}
static int child(void){return getenv("HB_TEST_CHILD")!=0;}
static int store_target(void){const char *p=getenv("HB_TEST_TARGET");return p&&!strcmp(p,"store");}
static int max_events(void){return installing()&&child()?(getenv("HB_TEST_RECOVERY")?8:6):loop()&&!(child()&&store_target())?4:2;}
static void note(const char *s){if(child()){const char *prefix="VDEV CHILD ";x1000_oabi_call(4,2,(long)prefix,11,0,0,0);s+=5;}x1000_oabi_call(4,2,(long)s,strlen(s),0,0,0);}
int open64(const char *path,int flags,...) {
 if(!strcmp(path,"/dev/input/event0")){errno=ENOENT;return -1;}
 if(!strcmp(path,"/dev/fb/0")){assert(!fb&&!touch&&!mapped);fb=1;note("VDEV OPEN FB\n");return 200;}
 if(!strcmp(path,"/dev/icx_touch_screen")){assert(fb&&!touch);touch=1;note("VDEV OPEN TOUCH\n");return 201;}
 assert(strncmp(path,"/dev/",5)||!strcmp(path,"/dev/urandom"));char translated[1024];path=host_path(path,translated);long n=x1000_oabi_call(5,(long)path,flags,384,0,0,0);if(n<0){errno=-n;return -1;}return n;
}
int close(int fd){
 if(fd==200){assert(fb&&!mapped);fb=0;note("VDEV CLOSE FB\n");return 0;}
 if(fd==201){assert(touch);touch=0;assert(!fb&&!mapped&&(event==2||event==4||event==6||event==8||getenv("HB_TEST_STOP"))&&frames>=1);note("VDEV RELEASE COMPLETE\n");return 0;}
 long n=x1000_oabi_call(6,fd,0,0,0,0,0);if(n<0){errno=-n;return -1;}return n;
}
void *mmap64(void *address,size_t length,int prot,int flags,int fd,off_t offset){
 assert(!address&&length==sizeof pixels&&prot==3&&flags==1&&fd==200&&!offset&&fb&&!mapped);mapped=1;return pixels;
}
int munmap(void *address,size_t length){assert(address==pixels&&length==sizeof pixels&&mapped);mapped=0;note("VDEV UNMAP\n");return 0;}
int ioctl(int fd,unsigned long request,void *argument){
 unsigned *p=argument;assert((fd==200&&fb)||(fd==201&&touch));
 switch(request){
 case 0x4602:memset(p,0,128);p[5]=0x120000;p[11]=480;break;
 case 0x4600:memset(p,0,160);p[0]=240;p[1]=432;p[6]=16;p[8]=11;p[9]=5;p[11]=5;p[12]=6;p[15]=5;break;
 case 0x80044e04:assert(p[0]==0&&p[1]==33);break;
 case 0x5404:assert(fd==201);break;
 case 0x80044e00:assert(p[0]==0);p[1]=0;p[2]=1;break;
 case 0x40044e01:assert(mapped&&p[0]==1&&p[1]==1&&p[2]==255&&p[3]==0&&!p[4]&&!p[5]&&pixels[0]);frames++;note("VDEV FRAME\n");
 if(network()&&child()){if(has_text(12,14,"AVAILABLE APPS",2)){network_ready=1;note("VDEV STORE CATALOG\n");}else if(has_text(12,116,"STORE UNAVAILABLE",1)){network_ready=-1;note("VDEV STORE ERROR\n");}else if(installing()&&has_text(12,116,"PREVIOUS METADATA CACHE",1)){network_ready=4;note("VDEV STORE RECOVERY\n");}else if(installing()&&has_text(12,116,"READY TO INSTALL",1)){network_ready=2;note("VDEV STORE READY\n");}else if(installing()&&has_text(12,116,"INSTALLED",1)){network_ready=3;note("VDEV STORE INSTALLED\n");}else if(installing()&&has_text(12,116,"STOPPED",1)){network_ready=-1;note("VDEV STORE STOPPED\n");}}
 {const char *path=getenv("HB_TEST_FRAME");assert(path);
 long fd=x1000_oabi_call(5,(long)path,577,384,0,0,0);assert(fd>=0);
 const unsigned char *bytes=(const unsigned char*)pixels;unsigned left=240*432*2;
 while(left){long written=x1000_oabi_call(4,fd,(long)bytes,left,0,0,0);assert(written>0);left-=written;bytes+=written;}
 assert(x1000_oabi_call(6,fd,0,0,0,0,0)==0);}break;
 case 0x80045401:{assert(event<max_events());unsigned x=30,y=400;if(loop()&&event<2){x=80;y=child()?(store_target()?400:100):(store_target()?60:120);}if(network()&&child()){x=installing()&&(network_ready==2||network_ready==3||network_ready==4||(network_ready==-1&&getenv("HB_TEST_REJECT_CLEANUP")))?180:30;y=installing()&&network_ready==1?60:400;}unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;unsigned char *b=argument;memset(b,0,16);b[1]=event%2==0;b[2]=rx>>8;b[3]=rx;b[4]=ry>>8;b[5]=ry;event++;if(installing()&&event%2==0)network_ready=0;break;}
 default:assert(0);
 }
 return 0;
}
int hb_test_poll(struct pollfd *,nfds_t,int) __asm__("poll");
int hb_test_poll(struct pollfd *p,nfds_t count,int timeout){if(count!=1||p->fd!=201){long n=x1000_oabi_call(168,(long)p,count,timeout,0,0,0);if(n<0){errno=-n;return -1;}return n;}assert(touch&&timeout==50&&event<max_events());if(network()&&child()&&!network_ready)return 0;p->revents=POLLIN;return 1;}



int execve(const char *path,char *const argv[],char *const env[]) {
 (void)argv;assert(loop()&&!child()&&!fb&&!touch&&!mapped&&event==2);
 assert(!strcmp(path,store_target()?"/contents/HOMEBREW/apps/store/app":"/contents/HOMEBREW/apps/graphics-demo/app"));
 const char *prefix=getenv("HB_TEST_PREFIX"),*preload=getenv("HB_TEST_PRELOAD"),*frame=getenv("HB_TEST_CHILD_FRAME");
 assert(prefix&&preload&&frame&&strlen(prefix)+strlen(path)<1024&&strlen(preload)<1000&&strlen(frame)<1000);
 char executable[1024]="",preload_arg[1024]="",frame_env[1024]="";
 append(executable,prefix);append(executable,path);
 append(preload_arg,"LD_PRELOAD=");append(preload_arg,preload);
 append(frame_env,"HB_TEST_FRAME=");append(frame_env,frame);
 char *environment[256];unsigned count=0;
 for(unsigned i=0;env[i];i++){assert(count<252);if(strncmp(env[i],"LD_PRELOAD=",11)&&strncmp(env[i],"HB_TEST_FRAME=",14)&&strncmp(env[i],"HB_TEST_CHILD=",14))environment[count++]=env[i];}
 environment[count++]="HB_TEST_CHILD=1";environment[count++]=frame_env;environment[count]=0;
 char *arguments[]={"/usr/bin/qemu-arm","-cpu","arm926","-L",(char*)prefix,"-E",preload_arg,"-0",(char*)path,executable,0};
 note(store_target()?"VDEV EXEC STORE\n":"VDEV EXEC GRAPHICS\n");
 char *traced[]={"/usr/bin/qemu-arm","-strace","-cpu","arm926","-L",(char*)prefix,"-E",preload_arg,"-0",(char*)path,executable,0};
 char **selected=getenv("HB_TEST_TRACE_CHILD")?traced:arguments;
 long n=x1000_oabi_call(11,(long)selected[0],(long)selected,(long)environment,0,0,0);
 errno=-n;return -1;
}
int chdir(const char *path) {
 assert(loop()&&!child()&&!strcmp(path,store_target()?"/contents/HOMEBREW/apps/store":"/contents/HOMEBREW/apps/graphics-demo"));
 const char *prefix=getenv("HB_TEST_PREFIX");assert(prefix&&strlen(prefix)+strlen(path)<1024);
 char host[1024]="";append(host,prefix);append(host,path);
 long n=x1000_oabi_call(12,(long)host,0,0,0,0,0);if(n<0){errno=-n;return -1;}return n;
}



int unlink(const char *path){char translated[1024];path=host_path(path,translated);long n=x1000_oabi_call(10,(long)path,0,0,0,0,0);if(n<0){errno=-n;return -1;}return n;}
/* Test-only pathname translation for the verified stock v3/96-byte stat ABI.
 * Preserve real stat/lstat behaviour on the corresponding host fixture path. */
int __xstat64(int version,const char *path,void *out){assert(version==3);char translated[1024];path=host_path(path,translated);long n=x1000_oabi_call(195,(long)path,(long)out,0,0,0,0);if(n<0){errno=-n;return -1;}return n;}
int __lxstat64(int version,const char *path,void *out){assert(version==3);char translated[1024];path=host_path(path,translated);long n=x1000_oabi_call(196,(long)path,(long)out,0,0,0,0);if(n<0){errno=-n;return -1;}return n;}


int mkdir(const char *path,unsigned mode){char translated[1024];path=host_path(path,translated);long n=x1000_oabi_call(39,(long)path,mode,0,0,0,0);if(n<0){errno=-n;return -1;}return n;}
int rmdir(const char *path){char translated[1024];path=host_path(path,translated);long n=x1000_oabi_call(40,(long)path,0,0,0,0,0);if(n<0){errno=-n;return -1;}return n;}
int rename(const char *from,const char *to){char a[1024],b[1024];from=host_path(from,a);to=host_path(to,b);long n=x1000_oabi_call(38,(long)from,(long)to,0,0,0,0);if(n<0){errno=-n;return -1;}return n;}


