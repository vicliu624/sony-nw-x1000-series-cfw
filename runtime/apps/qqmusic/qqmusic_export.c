#include "qqmusic_export.h"
#include "../../native/sha256.h"
#include <string.h>
#include <stdint.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static void digest_field(struct hb_sha256 *s,const char *value) {
 unsigned char length[4];size_t n=strlen(value);unsigned i;
 for(i=0;i<4;i++) length[3-i]=(unsigned char)(n>>(i*8));
 hb_sha256_update(s,length,4);hb_sha256_update(s,(const unsigned char *)value,(unsigned)n);
}
static void finish(struct hb_sha256 *s,char out[65]) {
 static const char hex[]="0123456789abcdef";unsigned char hash[32];unsigned i;
 hb_sha256_final(s,hash);for(i=0;i<32;i++) {out[i*2]=hex[hash[i]>>4];out[i*2+1]=hex[hash[i]&15];}out[64]=0;
}
/* Validate whole UTF-8 even after display prefix reaches limit. */
static int component(const char *input,const char *fallback,char out[61]) {
 size_t i=0,used=0;unsigned units=0;int truncated=0;
 if(!input) return -1;
 while(input[i]) {
  size_t start=i;uint32_t c=(unsigned char)input[i++],min=0;unsigned more=0,j;
  if(i>4096) return -1;
  if(c>=0xc2&&c<=0xdf) {more=1;min=0x80;c&=31;}
  else if(c>=0xe0&&c<=0xef) {more=2;min=0x800;c&=15;}
  else if(c>=0xf0&&c<=0xf4) {more=3;min=0x10000;c&=7;}
  else if(c>=128) return -1;
  for(j=0;j<more;j++) {unsigned char b;if(i>=4096||!input[i]) return -1;b=(unsigned char)input[i++];if((b&0xc0)!=0x80) return -1;c=c*64+(b&63);}
  if((more&&c<min)||c>0x10ffff||(c>=0xd800&&c<=0xdfff)) return -1;
  if(c<32||c==127||c=='/'||c=='\\'||c==':'||c=='*'||c=='?'||c=='"'||c=='<'||c=='>'||c=='|') {
   if(!truncated&&used<60) out[used++]='_';else truncated=1;
  } else {
   size_t n=i-start;if(truncated||used+n>60) {truncated=1;continue;}
   memcpy(out+used,input+start,n);used+=n;
  }
  if(++units>4096) return -1;
 }
 while(used&&(out[used-1]==' '||out[used-1]=='.')) used--;
 if(!used) {size_t n=strlen(fallback);memcpy(out,fallback,n);used=n;}
 /* Prefix avoids FAT/Windows DOS reserved names, '.' and '..' semantics.
  * It is directory spelling only; ID3 text remains untouched. */
 if(used>58) {while(used>58||((unsigned char)out[used]&0xc0)==0x80) used--;}
 memmove(out+2,out,used);out[0]='q';out[1]='-';out[used+2]=0;return 0;
}
int qq_export_plan(const struct qq_song *song,const struct qq_resource_intent *intent,const char *album_artist,struct qq_export_plan *out) {
 struct hb_sha256 hash;struct qq_resource_intent checked;char artist[61],album[61],title[61],artist_hash[65],album_hash[65],number[32],order[48];
 const char *artist_source;int n,rc=-1;
 if(!out) return -1;
 memset(out,0,sizeof(*out));memset(order,0,sizeof(order));
 if(!song||!intent||strcmp(song->mid,intent->song_mid)||strcmp(song->media_mid,intent->media_mid)||
    qq_resource_intent_init(&checked,intent->song_mid,intent->media_mid,intent->song_type,intent->quality)||strcmp(checked.filename,intent->filename)) return -1;
 artist_source=album_artist&&*album_artist?album_artist:song->artist;
 if(component(artist_source,"Unknown artist",artist)||component(song->album,"Unknown album",album)||component(song->title,"Untitled",title)) return -1;
 n=sony_snprintf(number,sizeof(number),"%u",intent->song_type);if(n<0||(size_t)n>=sizeof(number)) goto done;
 hb_sha256_init(&hash);digest_field(&hash,"qq-export-mp3-v1");digest_field(&hash,intent->song_mid);digest_field(&hash,intent->filename);digest_field(&hash,number);finish(&hash,out->identity);
 hb_sha256_init(&hash);digest_field(&hash,"artist");digest_field(&hash,artist_source);finish(&hash,artist_hash);
 n=sony_snprintf(number,sizeof(number),"%llu",(unsigned long long)song->album_id);if(n<0||(size_t)n>=sizeof(number)) goto done;
 hb_sha256_init(&hash);digest_field(&hash,"album");digest_field(&hash,song->album_mid);digest_field(&hash,number);finish(&hash,album_hash);
 if(song->track) {
  if(song->disc) n=sony_snprintf(order,sizeof(order),"%02llu-%02llu ",(unsigned long long)song->disc,(unsigned long long)song->track);
  else n=sony_snprintf(order,sizeof(order),"%02llu ",(unsigned long long)song->track);
  if(n<0||(size_t)n>=sizeof(order)) goto done;
 }
 n=sony_snprintf(out->relative,sizeof(out->relative),"%s-%s/%s-%s/%s%s [%s].mp3",artist,artist_hash,album,album_hash,order,title,out->identity);
 if(n<0||(size_t)n>=sizeof(out->relative)) goto done;
 out->version=1;rc=0;
done:
 if(rc) memset(out,0,sizeof(*out));
 return rc;
}
int qq_export_existing_check(const struct qq_export_plan *plan,int exists,const char *identity,const unsigned char recorded[32],const unsigned char actual[32]) {
 if(!plan||plan->version!=1||!plan->identity[0]||(exists!=0&&exists!=1)) return QQ_EXPORT_CONFLICT;
 if(!exists) return QQ_EXPORT_NEW;
 if(!identity||!recorded||!actual||strcmp(identity,plan->identity)||memcmp(recorded,actual,32)) return QQ_EXPORT_CONFLICT;
 return QQ_EXPORT_REUSE;
}
