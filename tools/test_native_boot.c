#define _DEFAULT_SOURCE
#include "../runtime/platform/wireless/native_boot.h"
#include "../runtime/platform/wireless/mode_policy.h"
#include <assert.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
static const char *modules="";
static unsigned position,opened,reads,state_reads;
static int before=2,after=2,modules_error,entropy_error,zero_entropy,short_entropy;
int xw_native_boot_manager_state(void){return state_reads++?after:before;}
int boot_open(const char *path,int flags,...){
 assert(flags==(O_RDONLY|O_NONBLOCK|O_NOFOLLOW));int fd;
 if(!strcmp(path,"/proc/modules")){if(modules_error){errno=EIO;return -1;}position=0;fd=3;}
 else {assert(!strcmp(path,"/dev/urandom"));if(entropy_error){errno=EIO;return -1;}fd=4;}
 assert(!(opened&(1u<<fd)));opened|=1u<<fd;return fd;
}
int boot_fcntl(int fd,int operation,...){
 va_list args;va_start(args,operation);int value=va_arg(args,int);va_end(args);
 assert((fd==3||fd==4)&&(opened&(1u<<fd))&&operation==F_SETFD&&value==FD_CLOEXEC);return 0;
}
ssize_t boot_read(int fd,void *buffer,size_t bytes){
 assert(opened&(1u<<fd));reads++;
 if(fd==3){size_t left=strlen(modules)-position;if(bytes>left)bytes=left;memcpy(buffer,modules+position,bytes);position+=(unsigned)bytes;return (ssize_t)bytes;}
 assert(fd==4&&bytes>0&&bytes<=8);if(short_entropy)bytes=1;memset(buffer,zero_entropy?0:0x5a,bytes);return (ssize_t)bytes;
}
int boot_close(int fd){assert(opened&(1u<<fd));opened&=~(1u<<fd);return 0;}
static void observe(int expected){
 reads=state_reads=0;struct xw_native_boot_observation o;
 int rc=xw_native_boot_observe(&o);assert((rc==0)==expected&&!opened);
 if(expected)assert(o.before==2&&o.after==2&&o.modules_clear==1&&o.entropy_valid==1&&o.generation);
}
int main(void){
 modules="";observe(1);
 modules="dummy 10 0 - Live 0x0\n";observe(1);
 modules="sd8xxx_extra 10 0 - Live 0x0\n";observe(1);
 const char *names[]={"sd8xxx","mp200_sdio","wlan_pm_register","wlan_pwr_ctrl"};char record[128];
 for(unsigned i=0;i<4;i++){snprintf(record,sizeof record,"%s 10 0 - Live 0x0\n",names[i]);modules=record;observe(0);}
 modules=" dummy 1\n";observe(0);modules="dummy 1";observe(0);modules="\n";observe(0);
 static char split[600];memset(split,'x',sizeof split);memcpy(split,"dummy ",6);split[250]='\n';
 const char *radio="sd8xxx 10 0 - Live 0x0\n";memcpy(split+251,radio,strlen(radio)+1);modules=split;observe(0);
 static char large[17001];memset(large,'x',sizeof large);memcpy(large,"dummy ",6);large[16999]='\n';large[17000]=0;modules=large;observe(0);
 modules="";before=3;observe(0);assert(!reads);before=2;after=3;observe(0);after=2;
 modules_error=1;observe(0);modules_error=0;entropy_error=1;observe(0);entropy_error=0;zero_entropy=1;observe(0);zero_entropy=0;
 short_entropy=1;observe(0);short_entropy=0;
 unsigned cases=0;
 for(int a=2;a<=3;a++)for(int b=2;b<=3;b++)for(unsigned clear=0;clear<2;clear++)for(unsigned entropy=0;entropy<2;entropy++)for(unsigned nonce=0;nonce<2;nonce++)for(int flag=0;flag<4;flag++){
  struct xw_native_boot_observation o={nonce,a,b,clear,entropy};int mode=0x5a;
  int expected=a==2&&b==2&&clear&&entropy&&nonce&&flag<2;
  assert((xw_native_boot_mode(&o,flag,&mode)==0)==expected);
  assert(mode==(expected?(flag==0?XW_WIRELESS_MODE_WIFI:XW_WIRELESS_MODE_OFF):0x5a));cases++;
 }
 struct xw_native_boot_observation o={7,2,2,1,1},decoded,poison;unsigned char raw[64];
 assert(!xw_native_boot_encode(raw,&o)&&!xw_native_boot_decode(&decoded,raw,64)&&decoded.generation==7);
 memset(&decoded,0xa5,sizeof decoded);poison=decoded;raw[63]=1;
 assert(xw_native_boot_decode(&decoded,raw,64)==XW_MODE_INVALID&&!memcmp(&decoded,&poison,sizeof decoded));
 assert(xw_native_boot_decode(&decoded,raw,63)==XW_MODE_INVALID&&!memcmp(&decoded,&poison,sizeof decoded));
 assert(cases==128);puts("NATIVE_BOOT_PASS");return 0;
}
