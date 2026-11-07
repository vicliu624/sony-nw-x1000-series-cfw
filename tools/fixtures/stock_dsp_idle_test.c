/* PC guest only: prove transfer bounds and absence of fabricated DSP messages. */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
extern int guest_fcntl(int,int,...) __asm__("fcntl");
#include "stock_dsp_idle_model.h"
static void release_model(void){close(dsp_idle_fd);close(dsp_idle_writer);dsp_idle_fd=dsp_idle_writer=-1;}
int main(void){
 assert(dsp_idle_open(O_NONBLOCK)>=0);
 unsigned packet[6]={0,0,0,0x4000,0,0},original[6];memcpy(original,packet,sizeof packet);
 assert(dsp_idle_ioctl(0x80184401,packet)==-1&&errno==EAGAIN);
 assert(!memcmp(original,packet,sizeof packet));
 unsigned ch[6]={0,0,~0u,~0u,1,0x1000};assert(!dsp_idle_ioctl(0x40184411,ch));
 assert(ch[2]==0xd0&&ch[3]==0x1000&&ch[4]==1&&ch[5]==0x1000);
 unsigned invalid[6]={2,0,~0u,~0u,1,0x1000};assert(dsp_idle_ioctl(0x40184411,invalid)==-1&&errno==EINVAL);
 unsigned char data[]={1,2,3,4};unsigned dl[9]={1,(unsigned long)data,3,0x3600000,4,0,0,0,0};
 assert(!dsp_idle_ioctl(0xc0244430,dl)&&!memcmp(dsp_idle_sdram+0x3600000,data,4));
 dl[3]=0x3fffffe;assert(dsp_idle_ioctl(0xc0244430,dl)==-1&&errno==EOPNOTSUPP);
 dl[2]=2;dl[3]=0x11000;assert(!dsp_idle_ioctl(0xc0244430,dl)&&!memcmp(dsp_idle_ssram+0x11000,data,4));
 dl[0]=4;dl[5]=3;assert(dsp_idle_ioctl(0xc0244430,dl)==-1&&errno==EINVAL);
 dl[0]=0x1c;dl[5]=2;dl[7]=1;dl[8]=1;assert(!dsp_idle_ioctl(0xc0244430,dl));
 assert(!dsp_idle_reset&&dsp_idle_clock&&dsp_idle_autoclock);
 unsigned short regs[2]={4,0x1234};unsigned dcv[2]={1,(unsigned long)regs};
 assert(!dsp_idle_ioctl(0x40084450,dcv));regs[1]=0;
 assert(!dsp_idle_ioctl(0x40084451,dcv)&&regs[1]==0x1234);
 regs[0]=16;assert(dsp_idle_ioctl(0x40084450,dcv)==-1&&errno==EINVAL);
 assert(dsp_idle_ioctl(0x1234,packet)==-1&&errno==EOPNOTSUPP);
 release_model();assert(dsp_idle_open(0)>=0);
 int sync[2];assert(!pipe(sync));pid_t child=fork();assert(child>=0);
 if(!child){close(sync[0]);assert(write(sync[1],"R",1)==1);dsp_idle_ioctl(0x80184401,packet);_exit(99);}
 close(sync[1]);char marker;assert(read(sync[0],&marker,1)==1&&marker=='R');
 usleep(20000);int status=0;assert(waitpid(child,&status,WNOHANG)==0);
 assert(!kill(child,SIGTERM)&&waitpid(child,&status,0)==child&&WIFSIGNALED(status)&&WTERMSIG(status)==SIGTERM);
 close(sync[0]);release_model();puts("STOCK_DSP_IDLE_MODEL_PASS");return 0;
}
