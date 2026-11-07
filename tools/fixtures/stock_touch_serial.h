/* PC-only touch transport. Fixed local UART packet: XWT1, x:u16le,
 * y:u16le, down:u8. Coordinates are logical Sony screen pixels.
 * No native event queues, state pointers or readiness events are injected.
 */
#include <sys/socket.h>
struct gui_touch_session {int writer;unsigned running;int status;};
static struct gui_touch_session *gui_touch_session;
static unsigned char gui_touch_value[11];
extern int pthread_create(unsigned long *,const void *,void *(*)(void *),void *);
extern int pthread_detach(unsigned long);
static void *gui_touch_serial_thread(void *argument){
 struct gui_touch_session *session=argument;
 int (*real_open)(const char *,int,...)=dlsym(RTLD_NEXT,"open");
 int (*real_ioctl)(int,unsigned long,void *)=dlsym(RTLD_NEXT,"ioctl");
 int (*real_close)(int)=dlsym(RTLD_NEXT,"close");
 int fd=real_open("/dev/ttyAMA1",O_RDWR|O_NOCTTY|O_NONBLOCK,0);
 struct {unsigned iflag,oflag,cflag,lflag;unsigned char line,cc[19];} term;
 if(fd>=0){
  if(real_ioctl(fd,0x5401,&term)){real_close(fd);fd=-1;}
  else{
   term.iflag=term.oflag=term.lflag=0;term.cc[5]=0;term.cc[6]=0;
   if(real_ioctl(fd,0x5402,&term)){real_close(fd);fd=-1;}
  }
 }
 __atomic_store_n(&session->status,fd>=0?1:-(errno?errno:EIO),__ATOMIC_RELEASE);
 if(fd>=0){
  const char note[]="GUEST_TOUCH_INPUT_READY\n";write(2,note,sizeof note-1);
  unsigned char input[9];unsigned used=0,notes=0;
  while(__atomic_load_n(&session->running,__ATOMIC_ACQUIRE)){
   if(!__atomic_load_n(&gui_touch_normal,__ATOMIC_ACQUIRE)){usleep(10000);continue;}
   ssize_t got=read(fd,input+used,sizeof input-used);
   if(got<=0){usleep(10000);continue;}used+=(unsigned)got;
   if(used!=sizeof input)continue;used=0;
   unsigned x=input[4]|((unsigned)input[5]<<8),y=input[6]|((unsigned)input[7]<<8),down=input[8];
   if(memcmp(input,"XWT1",4)||x>=240||y>=432||down>1)continue;
   unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;
   /* The original decoder stores byte0's low three bits as its contact count
    * at context+0x208. A single contact must not advertise zero contacts. */
   unsigned char packet[11]={0};packet[0]=down;packet[1]=down;packet[2]=rx>>8;packet[3]=rx;packet[4]=ry>>8;packet[5]=ry;
   if(send(session->writer,packet,sizeof packet,MSG_DONTWAIT|MSG_NOSIGNAL)!=(ssize_t)sizeof packet)continue;
   if(notes++<64){char line[100];int n=snprintf(line,sizeof line,"GUEST_TOUCH_PACKET x=%u y=%u down=%u\n",x,y,down);write(2,line,n);}
  }
  real_close(fd);
 }
 while(__atomic_load_n(&session->running,__ATOMIC_ACQUIRE))usleep(10000);
 real_close(session->writer);free(session);return 0;
}
static int gui_touch_serial_start(int descriptors[2]){
 if(socketpair(AF_UNIX,SOCK_DGRAM,0,descriptors))return -1;
 struct gui_touch_session *session=calloc(1,sizeof *session);
 if(!session){close(descriptors[0]);close(descriptors[1]);return -1;}
 session->writer=descriptors[1];session->running=1;
 guest_fcntl(descriptors[0],F_SETFL,O_NONBLOCK);
 unsigned long thread;
 gui_touch_session=session;
 int error=pthread_create(&thread,0,gui_touch_serial_thread,session);
 if(error){gui_touch_session=0;close(descriptors[0]);close(descriptors[1]);free(session);errno=error;return -1;}
 pthread_detach(thread);
 for(unsigned attempt=0;attempt<250&&!__atomic_load_n(&session->status,__ATOMIC_ACQUIRE);attempt++)usleep(2000);
 int status=__atomic_load_n(&session->status,__ATOMIC_ACQUIRE);
 if(status!=1){gui_touch_session=0;__atomic_store_n(&session->running,0,__ATOMIC_RELEASE);close(descriptors[0]);errno=status<0?-status:ETIMEDOUT;return -1;}
 return 0;
}
