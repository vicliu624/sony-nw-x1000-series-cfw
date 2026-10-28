#include "../../runtime/apps/qqmusic/qqmusic_preview_pcm.h"
#include <assert.h>
#include <string.h>
static struct qq_preview_pcm adapter;static volatile int stop;
static unsigned char output[200000],input[4096];static unsigned used,formats;
static int reject,stop_on_output;
static int format(void *p,unsigned rate,unsigned channels){(void)p;assert(rate==44100&&channels==2);formats++;return reject?-1:0;}
static int pcm(void *p,const unsigned char *data,unsigned n){(void)p;assert(formats==1&&n&&n<=4096&&!(n%4)&&used+n<=sizeof(output));memcpy(output+used,data,n);used+=n;if(stop_on_output)stop=1;return 0;}
static int value(unsigned frame,unsigned channel,unsigned channels){int n=((int)(frame%2000)-1000)*20;return channels==1||!channel?n:-n;}
static void sample(unsigned char *p,int n){p[0]=(unsigned char)n;p[1]=(unsigned char)((unsigned)(uint16_t)n>>8);}
static int decoded(const unsigned char *p){unsigned n=p[0]|(unsigned)p[1]<<8;return n&32768?(int)n-65536:(int)n;}
static void run(unsigned rate,unsigned channels,unsigned frames,unsigned chunk){
 struct qq_preview_sink sink,downstream={0,format,pcm};unsigned at=0,i;uint64_t count;
 used=formats=0;stop=0;reject=stop_on_output=0;assert(!qq_preview_pcm_init(&adapter,&downstream,&stop));sink=qq_preview_pcm_sink(&adapter);assert(!sink.format(sink.context,rate,channels));
 while(at<frames){unsigned n=frames-at;if(n>chunk)n=chunk;if(n>sizeof(input)/(channels*2))n=sizeof(input)/(channels*2);for(i=0;i<n;i++){sample(input+i*channels*2,value(at+i,0,channels));if(channels==2)sample(input+i*4+2,value(at+i,1,channels));}assert(!sink.pcm(sink.context,input,n*channels*2));at+=n;}
 assert(!qq_preview_pcm_finish(&adapter));count=(uint64_t)frames*44100/rate;assert(used==count*4&&adapter.produced==count);
 /* Independent whole-signal rational reference, no streaming history. */
 for(i=0;i<count;i++){
  uint64_t numerator=(uint64_t)i*rate;unsigned index=(unsigned)(numerator/44100),fraction=(unsigned)(numerator%44100),ch;
  for(ch=0;ch<2;ch++){int left=value(index,channels==1?0:ch,channels),right=value(index+1<frames?index+1:index,channels==1?0:ch,channels);int expected=(int)(((int64_t)left*(44100-fraction)+(int64_t)right*fraction)/44100);assert(decoded(output+i*4+ch*2)==expected);}
 }
 assert(qq_preview_pcm_finish(&adapter)<0);qq_preview_pcm_clear(&adapter);assert(!adapter.configured&&!adapter.used);
}
int main(void){
 unsigned r,c,k;const unsigned rates[]={32000,44100,48000};struct qq_preview_sink sink,downstream={0,format,pcm};
 for(r=0;r<3;r++)for(c=1;c<=2;c++)for(k=0;k<2;k++){run(rates[r],c,rates[r],k?1024:7);run(rates[r],c,13,k?13:1);run(rates[r],c,1,1);}
 used=formats=0;stop=0;reject=0;assert(!qq_preview_pcm_init(&adapter,&downstream,&stop));sink=qq_preview_pcm_sink(&adapter);assert(sink.format(sink.context,96000,2)<0&&!formats);assert(sink.format(sink.context,44100,3)<0&&!formats);
 assert(!sink.format(sink.context,44100,2));stop=1;assert(sink.pcm(sink.context,input,4)<0&&qq_preview_pcm_finish(&adapter)<0&&!used);
 stop=0;formats=0;reject=1;assert(!qq_preview_pcm_init(&adapter,&downstream,&stop));sink=qq_preview_pcm_sink(&adapter);assert(sink.format(sink.context,44100,2)<0&&!used);
 stop=0;formats=0;reject=0;stop_on_output=1;assert(!qq_preview_pcm_init(&adapter,&downstream,&stop));sink=qq_preview_pcm_sink(&adapter);assert(!sink.format(sink.context,44100,2));assert(sink.pcm(sink.context,input,4096)<0);assert(qq_preview_pcm_finish(&adapter)<0);qq_preview_pcm_clear(&adapter);
 return 0;
}
