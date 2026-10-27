#include "qqmusic_mp3.h"
#include <string.h>
static int read_bytes(const struct qq_codec_io *io,uint64_t offset,unsigned char *p,unsigned n){unsigned used=0;
 if(offset>io->source_bytes||n>io->source_bytes-offset)return -1;
 while(used<n){int got;if(io->stop&&*io->stop)return -1;got=io->read_at(io->source,offset+used,p+used,n-used);if(got<=0||(unsigned)got>n-used)return -1;used+=(unsigned)got;}return 0;
}
static uint32_t be32(const unsigned char *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
int qq_mp3_verify(const struct qq_codec_io *io,const struct qq_import_report *expected,struct qq_mp3_report *out){
 static const unsigned rates[]={44100,48000,32000,0},bitrates[]={0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0};
 unsigned char h[10];uint64_t pos,tag,frames=0;unsigned bitrate=0,i;
 if(out)memset(out,0,sizeof(*out));
 if(!io||!expected||!out||!io->read_at||!io->source_bytes||io->source_bytes>268435456||expected->output_bytes!=io->source_bytes||expected->tag_bytes<10||expected->tag_bytes>1048576||expected->tag_bytes>=io->source_bytes||!expected->audio.samples||expected->audio.samples>48000ULL*21600||expected->audio.padded_samples>=1152||expected->audio.mp3_bytes!=io->source_bytes-expected->tag_bytes||read_bytes(io,0,h,10)||memcmp(h,"ID3\3\0\0",6))return -1;
 tag=0;for(i=6;i<10;i++){if(h[i]&128)return -1;tag=(tag<<7)|h[i];}tag+=10;if(tag!=expected->tag_bytes||tag>=io->source_bytes)return -1;
 pos=10;
 while(pos<tag){uint32_t n;if(tag-pos<10||read_bytes(io,pos,h,10)||h[8]||h[9])return -1;for(i=0;i<4;i++)if(!((h[i]>='A'&&h[i]<='Z')||(h[i]>='0'&&h[i]<='9')))return -1;n=be32(h+4);if(!n||n>tag-pos-10)return -1;pos+=10+n;}
 while(pos<io->source_bytes){uint32_t header;unsigned rate,bits,channels,length;
  if(read_bytes(io,pos,h,4))return -1;
  header=be32(h);
  if((header>>21)!=2047||((header>>19)&3)!=3||((header>>17)&3)!=1)return -1;
  rate=rates[(header>>10)&3];bits=bitrates[(header>>12)&15];channels=((header>>6)&3)==3?1:2;
  if(!rate||!bits||rate!=expected->audio.rate||channels!=expected->audio.channels||(bitrate&&bitrate!=bits))return -1;
  bitrate=bits;length=144000*bits/rate+((header>>9)&1);if(length<4||length>io->source_bytes-pos)return -1;pos+=length;frames++;
 }
 if(!frames||frames*1152!=expected->audio.samples+expected->audio.padded_samples)return -1;
 out->frames=frames;out->bitrate_kbps=bitrate;return 0;
}
