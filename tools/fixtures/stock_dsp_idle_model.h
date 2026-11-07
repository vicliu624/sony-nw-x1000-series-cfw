/* PC guest-only idle InterDSP model. No DSP code or response generation.
 * ABI/idle-read rules: Sony GPL inter_dsp.c, new_chinfo/interdsp_read.
 * Offsets below belong to a private virtual arena, not MP200 physical memory.
 */
static int dsp_idle_fd=-1,dsp_idle_writer=-1,dsp_idle_nonblock;
static unsigned dsp_idle_channels[2][3][4],dsp_idle_tasks[10];
static unsigned short dsp_idle_dcv[16];
static unsigned dsp_idle_reset=1,dsp_idle_clock,dsp_idle_autoclock;
static unsigned char *dsp_idle_sdram,*dsp_idle_ssram;
static int dsp_idle_open(int flags){
 if(dsp_idle_fd>=0){errno=EBUSY;return -1;}
 int ends[2];if(pipe(ends))return -1;
 dsp_idle_fd=ends[0];dsp_idle_writer=ends[1];dsp_idle_nonblock=!!(flags&O_NONBLOCK);
 guest_fcntl(ends[0],F_SETFD,FD_CLOEXEC);guest_fcntl(ends[1],F_SETFD,FD_CLOEXEC);
 if(dsp_idle_nonblock)guest_fcntl(ends[0],F_SETFL,O_NONBLOCK);
 for(unsigned i=0;i<10;i++)dsp_idle_tasks[i]=~0u;
 return dsp_idle_fd;
}
static int dsp_idle_ioctl(unsigned long command,void *value){
 unsigned *p=value;
 char line[240];int n=snprintf(line,sizeof line,"MANAGER_DEVICE DSP_IDLE_IOCTL %08lx\n",command);write(2,line,n);
 if(!p){errno=EFAULT;return -1;}
 if(command==0x40184411||command==0x80184410){
  if(p[0]>1||p[1]>2){errno=EINVAL;return -1;}
  unsigned *ch=dsp_idle_channels[p[0]][p[1]],slot=p[0]*3+p[1];
  if(command==0x40184411){
   if(!p[2]&&!p[3]&&!p[4]&&!p[5])memset(ch,0,16);
   else{
    if(p[2]!=~0u||p[3]!=~0u||p[4]!=1||p[5]!=0x1000){errno=EOPNOTSUPP;return -1;}
    ch[0]=0xd0+slot*8;ch[1]=0x1000+slot*0x4000;ch[2]=1;ch[3]=0x1000;
   }
  }
  memcpy(p+2,ch,16);return 0;
 }
 if(command==0xc0084413||command==0x80084412){
  if(p[0]>=10){errno=EINVAL;return -1;}
  if(command==0xc0084413){if(p[1]>2&&p[1]!=~0u){errno=EINVAL;return -1;}dsp_idle_tasks[p[0]]=p[1];}
  else p[1]=dsp_idle_tasks[p[0]];
  return 0;
 }
 if(command==0x80184401){
  /* Empty DSP queue: block interruptibly, or return EAGAIN for O_NONBLOCK.
   * Never modify the caller's packet and never fabricate completion. */
  char byte;int result=read(dsp_idle_fd,&byte,1);
  if(result>=0)errno=EIO;
  return -1;
 }
 if(command==0xc0244430){
  int count=snprintf(line,sizeof line,"MANAGER_DEVICE DSP_IDLE_DOWNLOAD %08x %u %08x %u reset=%u clock=%u auto=%u\n",p[0],p[2],p[3],p[4],p[5],p[7],p[8]);write(2,line,count);
  /* Virtual register/memory transfers only. Clearing reset does not implement
   * DSP instruction execution or synthesize the OMF boot-ready response. */
  if((p[0]&~0x1du)||((p[0]&4)&&p[5]>2)||((p[0]&8)&&p[7]>1)||((p[0]&16)&&p[8]>1)){errno=EINVAL;return -1;}
  if((p[0]&1)&&p[4]){
   unsigned limit=p[2]==3?0x4000000:p[2]==2?0x80000:0;
   if(!limit||p[3]>=limit||p[4]>limit-p[3]){errno=EOPNOTSUPP;return -1;}
   if(!p[1]){errno=EFAULT;return -1;}
   unsigned char **memory=p[2]==3?&dsp_idle_sdram:&dsp_idle_ssram;
   if(!*memory)*memory=calloc(1,limit);
   if(!*memory){errno=ENOMEM;return -1;}
   memcpy(*memory+p[3],(const void *)(unsigned long)p[1],p[4]);
   dsp_idle_reset=1;
  }
  if(p[0]&4)dsp_idle_reset=p[5]==1;
  if(p[0]&8)dsp_idle_clock=p[7];
  if(p[0]&16)dsp_idle_autoclock=p[8];
  return 0;
 }
 if(command==0x40084450||command==0x40084451){
  if(p[0]>16){errno=EINVAL;return -1;}
  if(p[0]&&!p[1]){errno=EFAULT;return -1;}
  unsigned short *regs=(unsigned short *)(unsigned long)p[1];
  for(unsigned i=0;i<p[0];i++)if(regs[i*2]>=16){errno=EINVAL;return -1;}
  for(unsigned i=0;i<p[0];i++){
   if(command==0x40084450)dsp_idle_dcv[regs[i*2]]=regs[i*2+1];
   else regs[i*2+1]=dsp_idle_dcv[regs[i*2]];
  }
  return 0;
 }
 errno=EOPNOTSUPP;return -1;
}
