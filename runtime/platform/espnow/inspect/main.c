#include "observe.h"
#include "radio_inspect_profile.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/wireless.h>
extern int original_ioctl(int,unsigned long,...) __asm__("ioctl");
static unsigned get16(const uint8_t *p){return p[0]|(unsigned)p[1]<<8;}
static uint32_t get32(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static int read_word(void *context,uint32_t address,uint32_t *value){
 int fd=*(int *)context;uint8_t command[2048];struct iwreq request;memset(command,0,sizeof command);memset(&request,0,sizeof request);
 command[0]=0x86;command[2]=20;/* Action0 GET only; no SET code is supplied. */put32(command+12,address);strcpy(request.ifr_name,"eth0");request.u.data.pointer=command;request.u.data.length=20;
 if(original_ioctl(fd,0x8be4,&request)<0||request.u.data.length!=20||get16(command)!=0x8086||get16(command+2)!=20||get16(command+6))return -1;
 *value=get32(command+16);return 0;
}
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--version")){puts("Radio Inspect " RADIO_INSPECT_VERSION);return 0;}
 if(argc!=2||strcmp(argv[1],"--inspect")){puts("Radio Inspect " RADIO_INSPECT_VERSION "\n--inspect: explicit read-only stock/full-radio state snapshot. No SET, RF mode change, reload or file writes. Partial fingerprint and equal samples do not prove hardware readiness or ownership.");return argc==2&&!strcmp(argv[1],"--help")?0:64;}
 if(sizeof(struct iwreq)!=32)return 69;
 FILE *f=fopen("/proc/net/wlan/info","r");if(!f)return 69;char info[2048];size_t n=fread(info,1,sizeof info-1,f);int failed=ferror(f);if(fclose(f))failed=1;info[n]=0;if(failed||n==sizeof info-1||!strstr(info,"sd8686-9.70.3.p32-26409.p51-(FP4)"))return 69;
 int fd=socket(AF_INET,SOCK_DGRAM,0);if(fd<0)return 69;struct xnow_observe_result result;int rc=xnow_radio_observe(&fd,read_word,ranges,sizeof ranges/sizeof ranges[0],profiles,sizeof profiles/sizeof profiles[0],&result);int closed=close(fd);
 if(rc||closed){fprintf(stderr,"Radio snapshot unavailable: %d\n",rc);return 70;}
 printf("{\"tool\":\"" RADIO_INSPECT_VERSION "\",\"code_profile\":\"%s\",\"flags\":\"%08lx\",\"activation\":\"%08lx\",\"q\":\"%08lx\",\"mac_control_8000a300\":\"%08lx\",\"security_control_8000200c\":\"%08lx\",\"context_byte\":",profiles[result.profile].name,(unsigned long)result.flags,(unsigned long)result.activation,(unsigned long)result.q,(unsigned long)result.mac_control,(unsigned long)result.security_control);
 if(result.context_present)printf("%u",result.context_byte);else printf("null");puts(",\"hardware_admission_verified\":false}");return 0;
}
