/* Portable, bounded, little-endian state; CRC detects damage, not authorship. */
#include "fm_state.h"
#include <string.h>
static void put(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(n>>(i*8));}
static uint32_t get(const unsigned char *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static uint32_t crc(const unsigned char *p,size_t n){uint32_t c=~0u;while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);}return ~c;}
static int band_ok(struct fm_band b){return b.low>=65000&&b.high<=108000&&b.low<=b.high&&b.step>=50&&b.step<=200&&(b.high-b.low)%b.step==0;}
static int freq_ok(struct fm_band b,int khz){return khz>=b.low&&khz<=b.high&&(khz-b.low)%b.step==0;}
static int names_ok(const char *p){
 size_t i=0;
 while(i<FM_NAME_BYTES&&p[i]){
  unsigned c=(unsigned char)p[i++];if(c<32||c==127)return 0;
  if(c<128)continue;
  unsigned count,min,code;
  if(c>=0xc2&&c<=0xdf){count=1;min=128;code=c&31;}
  else if(c>=0xe0&&c<=0xef){count=2;min=2048;code=c&15;}
  else if(c>=0xf0&&c<=0xf4){count=3;min=65536;code=c&7;}else return 0;
  while(count--){if(i>=FM_NAME_BYTES)return 0;c=(unsigned char)p[i++];if((c&0xc0)!=0x80)return 0;code=(code<<6)|(c&63);}
  if(code<min||code>0x10ffff||(code>=0xd800&&code<=0xdfff))return 0;
 }
 return i<FM_NAME_BYTES;
}
static int list_ok(const struct fm_station *items,unsigned count,struct fm_band band){
 for(unsigned i=0;i<count;i++){
  if(!freq_ok(band,items[i].khz)||items[i].strength<0||items[i].strength>255||!names_ok(items[i].name))return 0;
  for(unsigned j=0;j<i;j++)if(items[j].khz==items[i].khz)return 0;
 }return 1;
}
static int valid(const struct fm_state *s){return s&&band_ok(s->band)&&freq_ok(s->band,s->frequency)&&s->threshold>=0&&s->threshold<=255&&s->favorite_count<=FM_MAX_STATIONS&&s->station_count<=FM_MAX_STATIONS&&list_ok(s->favorites,s->favorite_count,s->band)&&list_ok(s->stations,s->station_count,s->band);}
int fm_state_capture(const struct fm_radio *r,struct fm_state *s){
 if(!r||!s)return -1;
 struct fm_state next;memset(&next,0,sizeof(next));next.band=r->band;next.frequency=r->scanning?r->restore:r->frequency;next.threshold=r->threshold;
 next.favorite_count=r->favorite_count;next.station_count=r->station_count;
 if(next.favorite_count>FM_MAX_STATIONS||next.station_count>FM_MAX_STATIONS)return -1;
 memcpy(next.favorites,r->favorites,next.favorite_count*sizeof(next.favorites[0]));memcpy(next.stations,r->stations,next.station_count*sizeof(next.stations[0]));
 if(!valid(&next))return -1;
 *s=next;return 0;
}
int fm_state_apply(struct fm_radio *r,const struct fm_state *s){
 if(!r||!valid(s)||r->scanning||r->band.low!=s->band.low||r->band.high!=s->band.high||r->band.step!=s->band.step)return -1;
 if(r->frequency!=s->frequency&&fm_tune(r,s->frequency))return -1;
 memcpy(r->favorites,s->favorites,s->favorite_count*sizeof(r->favorites[0]));memcpy(r->stations,s->stations,s->station_count*sizeof(r->stations[0]));
 r->favorite_count=s->favorite_count;r->station_count=s->station_count;r->threshold=s->threshold;return 0;
}
int fm_state_encode(const struct fm_state *s,unsigned char *out,size_t cap,size_t *length){
 if(length)*length=0;
 if(!out||!length||!valid(s))return -1;
 size_t bytes=48u+56u*(s->favorite_count+s->station_count);if(bytes>cap)return -1;
 memset(out,0,bytes);memcpy(out,"HBFM",4);put(out+4,1);put(out+8,(uint32_t)bytes);
 put(out+12,(uint32_t)s->band.low);put(out+16,(uint32_t)s->band.high);put(out+20,(uint32_t)s->band.step);
 put(out+24,(uint32_t)s->frequency);put(out+28,(uint32_t)s->threshold);put(out+32,s->favorite_count);put(out+36,s->station_count);put(out+40,s->generation);
 unsigned char *p=out+44;
 for(unsigned group=0;group<2;group++){
  const struct fm_station *items=group?s->stations:s->favorites;unsigned count=group?s->station_count:s->favorite_count;
  for(unsigned i=0;i<count;i++,p+=56){put(p,(uint32_t)items[i].khz);put(p+4,(uint32_t)items[i].strength);memcpy(p+8,items[i].name,strlen(items[i].name));}
 }
 put(out+bytes-4,crc(out,bytes-4));*length=bytes;return 0;
}
int fm_state_decode(const unsigned char *data,size_t length,struct fm_band expected,struct fm_state *out){
 if(!data||!out||length<48||length>FM_STATE_MAX_BYTES||memcmp(data,"HBFM",4)||get(data+4)!=1||get(data+8)!=length||get(data+length-4)!=crc(data,length-4))return -1;
 struct fm_state s;memset(&s,0,sizeof(s));
 s.band=(struct fm_band){(int)get(data+12),(int)get(data+16),(int)get(data+20)};
 int migrate=s.band.low==76000&&s.band.high==90000&&s.band.step==100&&expected.low==76000&&expected.high==108000&&expected.step==100;
 if(!migrate&&(s.band.low!=expected.low||s.band.high!=expected.high||s.band.step!=expected.step))return -1;
 s.frequency=(int)get(data+24);s.threshold=(int)get(data+28);s.favorite_count=get(data+32);s.station_count=get(data+36);s.generation=get(data+40);
 if(s.favorite_count>FM_MAX_STATIONS||s.station_count>FM_MAX_STATIONS||length!=48u+56u*(s.favorite_count+s.station_count))return -1;
 const unsigned char *p=data+44;
 for(unsigned group=0;group<2;group++){
  struct fm_station *items=group?s.stations:s.favorites;unsigned count=group?s.station_count:s.favorite_count;
  for(unsigned i=0;i<count;i++,p+=56){items[i].khz=(int)get(p);items[i].strength=(int)get(p+4);memcpy(items[i].name,p+8,FM_NAME_BYTES);}
 }
 if(!valid(&s))return -1;
 if(migrate)s.band=expected;
 *out=s;return 0;
}
