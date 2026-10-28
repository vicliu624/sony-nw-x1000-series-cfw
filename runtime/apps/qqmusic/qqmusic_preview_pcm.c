#include "qqmusic_preview_pcm.h"
#include <string.h>
#define RATE 44100u
static int stopped(struct qq_preview_pcm *p){return p->stop&&*p->stop;}
static int fail(struct qq_preview_pcm *p){p->failed=1;return -1;}
static int flush(struct qq_preview_pcm *p){
 if(stopped(p))return fail(p);
 if(p->used&&p->output.pcm(p->output.context,p->bytes,p->used))return fail(p);
 if(stopped(p))return fail(p);
 p->used=0;return 0;
}
static int emit(struct qq_preview_pcm *p,int left,int right){
 unsigned channel;int values[2]={left,right};
 if(p->produced>=RATE*30u||stopped(p))return fail(p);
 for(channel=0;channel<2;channel++){
  unsigned value=(unsigned)(uint16_t)values[channel];p->bytes[p->used++]=(unsigned char)value;p->bytes[p->used++]=(unsigned char)(value>>8);
 }
 p->produced++;p->position+=p->rate;
 return p->used==sizeof(p->bytes)?flush(p):0;
}
static int format(void *context,unsigned rate,unsigned channels){
 struct qq_preview_pcm *p=context;
 if(!p||p->configured||p->failed||p->finished||(rate!=32000&&rate!=44100&&rate!=48000)||!channels||channels>2||stopped(p))return -1;
 if(p->output.format(p->output.context,RATE,2))return fail(p);
 p->rate=rate;p->channels=channels;p->configured=1;return 0;
}
static int sample(const unsigned char *p){unsigned n=(unsigned)p[0]|(unsigned)p[1]<<8;return n&0x8000?(int)n-65536:(int)n;}
static int push(void *context,const unsigned char *bytes,unsigned n){
 struct qq_preview_pcm *p=context;unsigned at;
 if(!p||!p->configured||p->failed||p->finished||!bytes||!n||n>4096||n%(p->channels*2))return -1;
 for(at=0;at<n;at+=p->channels*2){
  uint64_t index=p->received,limit=index*RATE;
  if(stopped(p)||index>=(uint64_t)p->rate*30)return fail(p);
  p->older[0]=p->previous[0];p->older[1]=p->previous[1];
  p->previous[0]=p->current[0];p->previous[1]=p->current[1];
  p->current[0]=sample(bytes+at);p->current[1]=p->channels==2?sample(bytes+at+2):p->current[0];p->received++;
  while(p->position<=limit&&p->position+p->rate<=p->received*RATE){
   unsigned fraction=(unsigned)(p->position%RATE);int values[2];unsigned channel;
   for(channel=0;channel<2;channel++){
    if(p->position/RATE==index)values[channel]=p->current[channel];
    else{
     uint64_t source_index=p->position/RATE;int left,right;int64_t value;
     if(source_index+1==index){left=p->previous[channel];right=p->current[channel];}
     else if(source_index+2==index){left=p->older[channel];right=p->previous[channel];}
     else return fail(p);
     value=(int64_t)left*(RATE-fraction)+(int64_t)right*fraction;
     values[channel]=(int)(value/RATE);
    }
   }
   if(emit(p,values[0],values[1]))return -1;
  }
 }
 return 0;
}
int qq_preview_pcm_init(struct qq_preview_pcm *p,const struct qq_preview_sink *output,volatile int *stop){
 if(!p||!output||!output->format||!output->pcm||!stop||*stop)return -1;
 memset(p,0,sizeof(*p));p->output=*output;p->stop=stop;return 0;
}
struct qq_preview_sink qq_preview_pcm_sink(struct qq_preview_pcm *p){struct qq_preview_sink sink={p,format,push};return sink;}
int qq_preview_pcm_finish(struct qq_preview_pcm *p){
 uint64_t total;
 if(!p||!p->configured||p->failed||p->finished||!p->received||stopped(p))return -1;
 total=p->received*RATE/p->rate;
 while(p->produced<total)if(emit(p,p->current[0],p->current[1]))return -1;
 if(flush(p))return -1;
 p->finished=1;return 0;
}
void qq_preview_pcm_clear(struct qq_preview_pcm *p){if(p)memset(p,0,sizeof(*p));}
