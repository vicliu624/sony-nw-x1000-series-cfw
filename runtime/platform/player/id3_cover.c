#include "id3_cover.h"
#include "player.h"
#include <string.h>
static uint32_t big(const unsigned char *p,unsigned n){uint32_t v=0;while(n--)v=(v<<8)|*p++;return v;}
static int syncsafe(const unsigned char *p,uint32_t *out){uint32_t v=0;for(unsigned i=0;i<4;i++){if(p[i]&128)return -1;v=(v<<7)|p[i];}*out=v;return 0;}
static int picture_header(const unsigned char *p,size_t n,int v2,unsigned *type,size_t *offset){
 if(n<6||p[0]>3)return -1;unsigned encoding=p[0];size_t at=1;
 if(v2){if(memcmp(p+at,"JPG",3)&&memcmp(p+at,"PNG",3))return -1;at+=3;}
 else {
  size_t begin=at;while(at<n&&p[at])at++;if(at==n)return -1;
  if(!((at-begin==10&&!memcmp(p+begin,"image/jpeg",10))||(at-begin==9&&!memcmp(p+begin,"image/png",9))))return -1;at++;
 }
 if(at>=n)return -1;*type=p[at++];
 if(encoding==1||encoding==2){for(;at+1<n;at+=2)if(!p[at]&&!p[at+1]){*offset=at+2;return 0;}}
 else for(;at<n;at++)if(!p[at]){*offset=at+1;return 0;}
 return -1;
}
int xw_id3_cover(void *context,int (*read_at)(void *,uint32_t,void *,size_t),uint64_t file_bytes,
                 unsigned char *out,size_t capacity,size_t *bytes){
 if(!read_at||!out||!capacity||!bytes)return XW_PLAYER_INVALID;
 unsigned char header[10],prefix[1024];if(file_bytes<10||read_at(context,0,header,10))return XW_PLAYER_IO;
 if(memcmp(header,"ID3",3)||header[3]<2||header[3]>4)return XW_PLAYER_UNAVAILABLE;
 unsigned version=header[3];uint32_t tag_bytes;
 if(header[4]!=0||syncsafe(header+6,&tag_bytes)||tag_bytes>16u*1024u*1024u||(uint64_t)tag_bytes+10>file_bytes)return XW_PLAYER_PROTOCOL;
 if(header[5]&0x80u||(version==2&&(header[5]&0x40u)))return XW_PLAYER_UNSUPPORTED;
 uint32_t at=10,end=10+tag_bytes,selected=0,length=0;unsigned preference=0;
 if(version>2&&(header[5]&0x40u)){
  unsigned char extended[4];uint32_t count;if(end-at<4||read_at(context,at,extended,4))return XW_PLAYER_PROTOCOL;
  if(version==4){if(syncsafe(extended,&count)||count<6)return XW_PLAYER_PROTOCOL;}
  else {count=big(extended,4);if(count<6||count>UINT32_MAX-4)return XW_PLAYER_PROTOCOL;count+=4;}
  if(count>end-at)return XW_PLAYER_PROTOCOL;at+=count;
 }
 for(unsigned frames=0;at<end&&frames<4096;frames++){
  unsigned hb=version==2?6:10;if(end-at<hb)break;
  if(read_at(context,at,header,hb))return XW_PLAYER_IO;if(!header[0])break;
  unsigned id_bytes=version==2?3:4;for(unsigned i=0;i<id_bytes;i++)if(!((header[i]>='A'&&header[i]<='Z')||(header[i]>='0'&&header[i]<='9')))return XW_PLAYER_PROTOCOL;
  uint32_t size;
  if(version==4){if(syncsafe(header+4,&size))return XW_PLAYER_PROTOCOL;}
  else size=big(header+(version==2?3:4),version==2?3:4);
  at+=hb;if(size>end-at)return XW_PLAYER_PROTOCOL;
  int picture=version==2?!memcmp(header,"PIC",3):!memcmp(header,"APIC",4);
  unsigned flags=version==2?0:header[9];
  if(picture&&!(flags&(version==4?0x4fu:0xe0u))){
   size_t n=size<sizeof prefix?size:sizeof prefix,skip=0;unsigned type=255;
   if(n&&read_at(context,at,prefix,n))return XW_PLAYER_IO;
   if(!picture_header(prefix,n,version==2,&type,&skip)&&skip<size){
    unsigned rank=type==3?2:type==0?1:0;
    if(rank>preference){preference=rank;selected=at+(uint32_t)skip;length=size-(uint32_t)skip;}
   }
  }
  at+=size;
 }
 if(!preference)return XW_PLAYER_UNAVAILABLE;
 if(length>capacity)return XW_PLAYER_UNSUPPORTED;
 if(read_at(context,selected,out,length))return XW_PLAYER_IO;
 if(!((length>=3&&out[0]==0xff&&out[1]==0xd8&&out[2]==0xff)||(length>=8&&!memcmp(out,"\211PNG\r\n\032\n",8))))return XW_PLAYER_PROTOCOL;
 *bytes=length;return 0;
}
