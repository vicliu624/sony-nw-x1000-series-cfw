#define _XOPEN_SOURCE 700
#include "qqmusic_preview_transport.h"
#include "qqmusic_preview_wire.h"
#include "../../../sdk/include/x1000/services/process.h"
#include "../../../sdk/include/x1000/services/clock.h"
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/abi.h"
extern int transport_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t transport_write(int,const void *,size_t) __asm__("write");
static int stopped(struct qq_preview_transport *t){return !t||!t->stop||*t->stop||(unsigned)getppid()!=t->parent;}
static int packet(struct qq_preview_transport *t,unsigned type,unsigned argument,uint64_t value,const unsigned char *pcm){
 unsigned char bytes[4096];struct qq_preview_record r;struct hb_transfer_deadline deadline;unsigned wanted=32;
 if(stopped(t)||t->failed||t->ended||!t->sequence||t->sequence==UINT32_MAX)return -1;
 r.generation=t->generation;r.sequence=t->sequence;r.type=type;r.argument=argument;r.value=value;
 if(qq_preview_record_encode(&r,bytes,32))return -1;
 if(type==QQ_PREVIEW_PCM){if(!pcm)return -1;memcpy(bytes+32,pcm,argument);wanted+=argument;}
 if(hb_transfer_deadline_init(&deadline,15000))return -1;
 for(;;){
  ssize_t n;unsigned wait;
  if(stopped(t)||hb_transfer_deadline_remaining(&deadline,&wait)!=1)break;
  n=transport_write(t->pcm_fd,bytes,wanted);
  /* Linux 2.6 pipes guarantee an atomic write up to PIPE_BUF=4096. A
   * surprising short success is an error, never resend a duplicate prefix. */
  if(n==(ssize_t)wanted){t->sequence++;return 0;}
  if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR)){hb_linux_wait_tick();continue;}
  break;
 }
 t->failed=1;return -1;
}
static int format(void *context,unsigned rate,unsigned channels){struct qq_preview_transport *t=context;if(t->formatted||rate!=44100||channels!=2||packet(t,QQ_PREVIEW_FORMAT,rate,channels,0))return -1;t->formatted=1;return 0;}
static int pcm(void *context,const unsigned char *bytes,unsigned n){
 struct qq_preview_transport *t=context;unsigned used=0;
 if(!t->formatted||!bytes||!n||n>4096||(n&3)||t->frames+n/4u>44100u*30u)return -1;
 while(used<n){unsigned take=n-used;if(take>QQ_PREVIEW_PCM_BYTES)take=QQ_PREVIEW_PCM_BYTES;
  if(packet(t,QQ_PREVIEW_PCM,take,0,bytes+used))return -1;
  used+=take;t->frames+=take/4u;
 }return 0;
}
int qq_preview_transport_init(struct qq_preview_transport *t,int fd,unsigned parent,uint64_t generation,volatile int *stop){
 struct stat s;int flags;
 if(!t||fd<0||parent<=1||!generation||!stop||*stop||(unsigned)getppid()!=parent)return -1;
 flags=transport_fcntl(fd,F_GETFL);
 if(flags<0||!(flags&O_NONBLOCK)||(flags&O_ACCMODE)==O_RDONLY||fstat(fd,&s)||!S_ISFIFO(s.st_mode))return -1;
 memset(t,0,sizeof(*t));t->pcm_fd=fd;t->parent=parent;t->generation=generation;t->stop=stop;t->sequence=1;return 0;
}
struct qq_preview_sink qq_preview_transport_sink(struct qq_preview_transport *t){struct qq_preview_sink s={t,format,pcm};return s;}
int qq_preview_transport_end(struct qq_preview_transport *t,unsigned result){
 if(!t||result>2||(!result&&(!t->formatted||!t->frames)))return -1;
 if(packet(t,QQ_PREVIEW_END,result,t->frames,0))return -1;
 t->ended=1;return 0;
}
