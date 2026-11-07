/* PC guest-only mixer/routing state. No PCM device, decoding or sound output.
 * OSS plus pinned GPL icx1087_audio.h ABI; unknown requests fail explicitly.
 */
static int silent_mixer=-1,silent_beep=-1;
static unsigned silent_volume,silent_pcm;
static unsigned silent_mute,silent_source,silent_output;
static unsigned char silent_volume_table[101];
static unsigned silent_beep_volume=6,silent_beep_interval=50;
static unsigned char silent_beep_pattern[80];
static int silent_beep_ioctl(unsigned long command,void *value){
 char line[120];int n=snprintf(line,sizeof line,"MANAGER_DEVICE SILENT_BEEP_IOCTL %08lx\n",command);write(2,line,n);
 if(command==0x6208)return 0;
 if(!value){errno=EFAULT;return -1;}unsigned *p=value;
 if(command==0xc0046205){*p=0;return 0;}
 if(command==0x40046204){if(*p>4){errno=EINVAL;return -1;}return 0;}
 if(command==0x40046201){if(*p>100){errno=EINVAL;return -1;}silent_beep_volume=*p;return 0;}
 if(command==0x80046202){*p=silent_beep_volume;return 0;}
 if(command==0x40046206){silent_beep_interval=*p;return 0;}
 if(command==0x80046207){*p=silent_beep_interval;return 0;}
 if(command==0x40146203){
  if(!p[0]||p[1]>4||!p[3]||p[3]>80||(p[3]&3)||!p[4]){errno=EINVAL;return -1;}
  memcpy(silent_beep_pattern,(const void *)(unsigned long)p[4],p[3]);return 0;
 }
 errno=EOPNOTSUPP;return -1;
}
static int silent_mixer_ioctl(unsigned long command,void *value){
 char line[120];int n=snprintf(line,sizeof line,"MANAGER_DEVICE SILENT_MIXER_IOCTL %08lx\n",command);write(2,line,n);
 /* The pinned GPL mixer accepts PLAY/STOP/SYNC as no-ops when its sound-
  * effect controller is absent. In this silent PC profile effects finish
  * immediately. SYNC/STOP are _IO requests and have no argument to read. */
 if(command==0x40046115||command==0x6116||command==0x6117)return 0;
 if(!value){errno=EFAULT;return -1;}unsigned *p=value;
 if(command==0x80046118){*p=2;return 0;} /* AUDIO_SE_STATUS_STOPPED */
 if(command==0x40046101){if(*p&~0x1f1fu){errno=EINVAL;return -1;}silent_mute=*p;return 0;}
 if(command==0x80046102){*p=silent_mute;return 0;}
 if(command==0x40046103){if(*p>6){errno=EINVAL;return -1;}silent_source=*p;return 0;}
 if(command==0x80046104){*p=silent_source;return 0;}
 if(command==0x40046105){if(*p>3){errno=EINVAL;return -1;}silent_output=*p;return 0;}
 if(command==0x80046106){*p=silent_output;return 0;}
 if(command==0x400c6107||command==0x800c6108){
  if(p[0]>100||!p[1]||p[1]>101-p[0]||!p[2]){errno=EINVAL;return -1;}
  void *buffer=(void *)(unsigned long)p[2];
  if(command==0x400c6107)memcpy(silent_volume_table+p[0],buffer,p[1]);
  else memcpy(buffer,silent_volume_table+p[0],p[1]);
  return 0;
 }
 if(command==0x80044dfe||command==0x80044dfb){*p=0x11;return 0;}
 if(command==0x80044dfc||command==0x80044dfd||command==0x80044dff){*p=0;return 0;}
 unsigned *channel=(command&0xff)==0?&silent_volume:(command&0xff)==4?&silent_pcm:0;
 if(channel&&(command==0x80044d00||command==0x80044d04)){*p=*channel;return 0;}
 if(channel&&(command==0xc0044d00||command==0xc0044d04)){
  if((*p&0xffff0000)||(*p&255)>100||((*p>>8)&255)>100){errno=EINVAL;return -1;}
  *channel=*p;return 0;
 }
 errno=EOPNOTSUPP;return -1;
}
