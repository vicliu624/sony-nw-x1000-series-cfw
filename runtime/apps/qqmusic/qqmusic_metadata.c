#include "qqmusic_metadata.h"
#include "qqmusic_image.h"
#include "../../native/sha256.h"
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
void qq_metadata_init(struct qq_metadata *m) {memset(m,0,sizeof(*m));}
static int copy(char *out,size_t cap,const char *s,size_t n) {
 if(!s||n>=cap||memchr(s,0,n)) return -1;
 memcpy(out,s,n);out[n]=0;return 0;
}
static int field(const char *name) {
 static const char *keys[]={"TITLE","ARTIST","ALBUM","ALBUMARTIST","TRACKNUMBER","DISCNUMBER","DATE","GENRE","COMPOSER"};unsigned i;
 for(i=0;i<QQ_META_FIELDS;i++) if(!strcmp(name,keys[i])) return (int)i;
 if(!strcmp(name,"ALBUM_ARTIST")||!strcmp(name,"ALBUM ARTIST")) return QQ_META_ALBUM_ARTIST;
 if(!strcmp(name,"TRACK")) return QQ_META_TRACK;
 if(!strcmp(name,"DISC")) return QQ_META_DISC;
 if(!strcmp(name,"YEAR")) return QQ_META_DATE;
 return -1;
}
static int comment_impl(struct qq_metadata *m,const char *name,size_t name_n,const char *value,size_t n) {
 char key[65];size_t i;int id;
 if(!m||!name||!name_n||name_n>=sizeof(key)||!value) return -1;
 for(i=0;i<name_n;i++) {unsigned char c=(unsigned char)name[i];if(c<32||c>125||c=='=') return -1;key[i]=c>='a'&&c<='z'?(char)(c-32):(char)c;}key[name_n]=0;
 if(!strcmp(key,"METADATA_BLOCK_PICTURE")) {
  unsigned w,h;size_t bytes=0;int rc,had_source=m->source_cover&&m->jpeg_bytes;unsigned char before[32],after[32];struct hb_sha256 hash;
  if(!m->jpeg||!m->jpeg_capacity) return -2;
  if(had_source) {hb_sha256_init(&hash);hb_sha256_update(&hash,m->jpeg,(unsigned)m->jpeg_bytes);hb_sha256_final(&hash,before);}
  rc=qq_picture_jpeg(value,n,m->jpeg,m->jpeg_capacity,&bytes,&w,&h);
  if(rc<0) return -1;
  if(rc==1) {m->nonfront_pictures++;return 0;}
  if(had_source) {hb_sha256_init(&hash);hb_sha256_update(&hash,m->jpeg,(unsigned)bytes);hb_sha256_final(&hash,after);if(memcmp(before,after,32)) return -1;}
  m->jpeg_bytes=bytes;m->source_cover=1;return 0;
 }
 if(!strcmp(key,"COVERART")) return -2;
 if(n>1024||memchr(value,0,n)) return -1;
 if(!n) return 0;
 id=field(key);
 if(id>=0) {
  char *dest=m->fields[id];size_t used=strlen(dest);
  if(used) {
   if(used==n&&!memcmp(dest,value,n)) return 0;
   if(id==QQ_META_DATE&&used>=4&&n>=4&&!memcmp(dest,value,4)) {
    if(n==4&&used>4&&dest[4]=='-') return 0;
    if(used==4&&n>4&&value[4]=='-') return copy(dest,1025,value,n);
   }
   if(id!=QQ_META_ARTIST&&id!=QQ_META_ALBUM_ARTIST) return -1;
   if(used+3+n>=1025) return -1;
   memcpy(dest+used," / ",3);return copy(dest+used+3,1025-used-3,value,n);
  }
  if(copy(dest,1025,value,n)) return -1;
  m->source_mask|=1u<<(unsigned)id;return 0;
 }
 for(i=0;i<m->extras;i++) if(!strcmp(key,m->extra_names[i])) return strlen(m->extra_values[i])==n&&!memcmp(m->extra_values[i],value,n)?0:-1;
 if(m->extras==16) return -1;
 memcpy(m->extra_names[m->extras],key,name_n+1);
 if(copy(m->extra_values[m->extras],1025,value,n)) return -1;
 m->extras++;return 0;
}
int qq_metadata_comment(struct qq_metadata *m,const char *name,size_t name_n,const char *value,size_t n) {
 int rc;if(!m||m->error) return -1;rc=comment_impl(m,name,name_n,value,n);if(rc) m->error=rc;return rc;
}
static int fill(struct qq_metadata *m,unsigned id,const char *s) {
 if(m->fields[id][0]||!s||!*s) return 0;
 if(copy(m->fields[id],1025,s,strlen(s))) return -1;
 m->filled_mask|=1u<<id;return 0;
}
static int fill_impl(struct qq_metadata *m,const struct qq_song *song,const struct qq_resource_intent *intent,const char *album_artist) {
 char number[32];int n;
 if(!m||!song||!intent||!song->mid[0]||!song->media_mid[0]||strcmp(song->mid,intent->song_mid)||strcmp(song->media_mid,intent->media_mid)) return -1;
 if(album_artist&&*album_artist&&!song->album_id&&!song->album_mid[0]) return -1;
 memcpy(m->bound_album_mid,song->album_mid,strlen(song->album_mid)+1);
 if(fill(m,QQ_META_TITLE,song->title)||fill(m,QQ_META_ARTIST,song->artist)||fill(m,QQ_META_ALBUM,song->album)||fill(m,QQ_META_ALBUM_ARTIST,album_artist)||fill(m,QQ_META_DATE,song->date)) return -1;
 if(song->track) {n=sony_snprintf(number,sizeof(number),"%llu",(unsigned long long)song->track);if(n<0||(size_t)n>=sizeof(number)||fill(m,QQ_META_TRACK,number)) return -1;}
 if(song->disc) {n=sony_snprintf(number,sizeof(number),"%llu",(unsigned long long)song->disc);if(n<0||(size_t)n>=sizeof(number)||fill(m,QQ_META_DISC,number)) return -1;}
 return 0;
}
int qq_metadata_fill(struct qq_metadata *m,const struct qq_song *song,const struct qq_resource_intent *intent,const char *album_artist) {
 int rc;if(!m||m->error) return -1;rc=fill_impl(m,song,intent,album_artist);if(rc) m->error=rc;return rc;
}
static int combine_total(char *position,const char *total) {
 char *slash;unsigned first=0,last=0;const char *p;size_t n;
 if(!position[0]||!total||!*total) return 0;
 for(p=total;*p;p++) {if(*p<'0'||*p>'9'||last>9999) return -1;last=last*10+(unsigned)(*p-'0');}
 if(!last) return -1;
 for(p=position;*p&&*p!='/';p++) {if(*p<'0'||*p>'9'||first>9999) return -1;first=first*10+(unsigned)(*p-'0');}
 if(first>last) return -1;
 slash=strchr(position,'/');
 if(slash) {unsigned current=0;for(p=slash+1;*p;p++) {if(*p<'0'||*p>'9'||current>9999) return -1;current=current*10+(unsigned)(*p-'0');}return current==last?0:-1;}
 n=strlen(position);if(n+1+strlen(total)>=1025) return -1;position[n++]='/';memcpy(position+n,total,strlen(total)+1);return 0;
}
int qq_metadata_tags(struct qq_metadata *m,struct qq_track_tags *out) {
 unsigned i;const char *date;
 if(!out) return -1;
 memset(out,0,sizeof(*out));if(!m||m->error) return -1;memset(m->year,0,sizeof(m->year));
 for(i=0;i<m->extras;i++) {
  int track=!strcmp(m->extra_names[i],"TRACKTOTAL")||!strcmp(m->extra_names[i],"TOTALTRACKS");
  int disc=!strcmp(m->extra_names[i],"DISCTOTAL")||!strcmp(m->extra_names[i],"TOTALDISCS");
  if((track&&combine_total(m->fields[QQ_META_TRACK],m->extra_values[i]))||(disc&&combine_total(m->fields[QQ_META_DISC],m->extra_values[i]))) {m->error=-1;return -1;}
 }
 date=m->fields[QQ_META_DATE];
 if(strlen(date)>=4&&(!date[4]||date[4]=='-')) {
  for(i=0;i<4;i++) if(date[i]<'0'||date[i]>'9') break;
  if(i==4) memcpy(m->year,date,4);
 }
 out->title=m->fields[QQ_META_TITLE];out->artist=m->fields[QQ_META_ARTIST];out->album=m->fields[QQ_META_ALBUM];out->album_artist=m->fields[QQ_META_ALBUM_ARTIST];
 out->track=m->fields[QQ_META_TRACK];out->disc=m->fields[QQ_META_DISC];out->year=m->year;out->date=date;out->genre=m->fields[QQ_META_GENRE];out->composer=m->fields[QQ_META_COMPOSER];
 for(i=0;i<m->extras;i++) {m->extra_view[i].name=m->extra_names[i];m->extra_view[i].value=m->extra_values[i];}
 out->extras=m->extra_view;out->extra_count=m->extras;
 if(m->jpeg_bytes) {out->jpeg=m->jpeg;out->jpeg_bytes=m->jpeg_bytes;}
 return 0;
}
int qq_metadata_artwork_buffer(struct qq_metadata *m,unsigned char *out,size_t cap) {
 if(!m||m->error||!out||!cap||cap>524288||m->jpeg_bytes) return -1;
 m->jpeg=out;m->jpeg_capacity=cap;memset(out,0,cap);return 0;
}
int qq_metadata_album_cover(struct qq_metadata *m,const char *album_mid,const unsigned char *data,size_t n) {
 unsigned w,h;size_t bytes;
 if(!m||m->error||!album_mid||!*album_mid||!m->bound_album_mid[0]||strcmp(album_mid,m->bound_album_mid)||!m->jpeg) {if(m) m->error=-1;return -1;}
 if(m->jpeg_bytes) return 0;
 if(qq_image_jpeg(data,n,m->jpeg,m->jpeg_capacity,&bytes,&w,&h)) {m->error=-1;return -1;}
 m->jpeg_bytes=bytes;return 0;
}
