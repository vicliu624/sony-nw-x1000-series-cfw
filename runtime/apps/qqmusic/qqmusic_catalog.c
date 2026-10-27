#include "qqmusic_catalog.h"
#include "qqmusic_protocol.h"
#include <string.h>
static int get_alias(const struct qq_json *d,unsigned object,const char *a,const char *b,const char *c) {
 int result=qq_json_get(d,object,a),other;
 if(b) {other=qq_json_get(d,object,b);if(other>=0) {if(result>=0) return -2;result=other;}}
 if(c) {other=qq_json_get(d,object,c);if(other>=0) {if(result>=0) return -2;result=other;}}
 return result;
}
static int number(const struct qq_json *d,int node,uint64_t *value) {
 char text[32];size_t i;uint64_t n=0;
 if(node<0) return -1;
 if(d->nodes[node].type==QQ_JSON_NUMBER) return qq_json_uint(d,(unsigned)node,value);
 if(qq_json_string(d,(unsigned)node,text,sizeof(text))||!text[0]) return -1;
 for(i=0;text[i];i++) {unsigned digit=(unsigned)(text[i]-'0');if(digit>9||n>(UINT64_MAX-digit)/10) return -1;n=n*10+digit;}
 *value=n;return 0;
}
static int flag(const struct qq_json *d,int node,unsigned *value) {
 uint64_t n;
 if(node<0) return -1;
 if(d->nodes[node].type==QQ_JSON_LITERAL) {
  const struct qq_json_node *t=&d->nodes[node];
  if(t->end-t->start==4&&!memcmp(d->text+t->start,"true",4)) {*value=1;return 0;}
  if(t->end-t->start==5&&!memcmp(d->text+t->start,"false",5)) {*value=0;return 0;}
  return -1;
 }
 if(number(d,node,&n)||n>1) return -1;
 *value=(unsigned)n;return 0;
}
static int string(const struct qq_json *d,int node,char *out,size_t cap,int required) {
 size_t i;
 if(node==-1&&!required) return 0;
 if(node<0||qq_json_string(d,(unsigned)node,out,cap)||(required&&!out[0])) return -1;
 for(i=0;out[i];i++) if((unsigned char)out[i]<32||(unsigned char)out[i]==127) return -1;
 return 0;
}
static int identifier(const char *s) {
 size_t i;if(!*s) return 0;
 for(i=0;s[i];i++) if(!((s[i]>='a'&&s[i]<='z')||(s[i]>='A'&&s[i]<='Z')||(s[i]>='0'&&s[i]<='9')||s[i]=='_'||s[i]=='-')) return 0;
 return 1;
}
static int optional_number(const struct qq_json *d,unsigned object,const char *key,uint64_t *v) {
 int n=qq_json_get(d,object,key);return n<0?0:number(d,n,v);
}
int qq_parse_playlists(struct qq_json *d,const char *s,size_t n,enum qq_playlist_kind kind,struct qq_playlist_page *out,uint64_t *code) {
 int data,array,rc=QQ_AUTH_PROTOCOL;unsigned i,j,finished;
 if(!out) return rc;
 qq_secret_clear(out,sizeof(*out));
 data=qq_cgi_data(d,s,n,code);if(data<0) return data;
 if(kind!=QQ_PLAYLIST_CREATED&&kind!=QQ_PLAYLIST_COLLECTED) goto done;
 if(number(d,qq_json_get(d,(unsigned)data,"total"),&out->total)) goto done;
 if(kind==QQ_PLAYLIST_CREATED) {
  if(flag(d,qq_json_get(d,(unsigned)data,"bFinish"),&finished)) goto done;
  out->more=!finished;
 } else if(flag(d,qq_json_get(d,(unsigned)data,"hasmore"),&out->more)) goto done;
 array=qq_json_get(d,(unsigned)data,kind==QQ_PLAYLIST_CREATED?"v_playlist":"v_list");
 if(array<0||d->nodes[array].type!=QQ_JSON_ARRAY) goto done;
 for(i=(unsigned)array+1;i<d->nodes[array].next;i=d->nodes[i].next) {
  struct qq_playlist *p;int title;
  if(out->count==QQ_PLAYLIST_LIMIT||d->nodes[i].type!=QQ_JSON_OBJECT) goto done;
  p=&out->entries[out->count];
  title=get_alias(d,i,"title","dissname","name");
  if(qq_json_get(d,i,"dirName")>=0) {if(title!=-1) goto done;title=qq_json_get(d,i,"dirName");}
  if(number(d,get_alias(d,i,"id","tid","dissid"),&p->id)||
     number(d,get_alias(d,i,"dirid","dirId",0),&p->dirid)||(!p->id&&p->dirid!=201)||
     number(d,get_alias(d,i,"songnum","songNum","song_cnt"),&p->songs)||
     string(d,title,p->title,sizeof(p->title),1)) goto done;
  for(j=0;j<out->count;j++) if(out->entries[j].id==p->id&&out->entries[j].dirid==p->dirid) goto done;
  out->count++;
 }
 if(out->count>out->total||(!out->count&&out->more)) goto done;
 if(kind==QQ_PLAYLIST_CREATED&&!out->more&&out->count!=out->total) goto done;
 rc=0;
done:
 qq_secret_clear(d,sizeof(*d));if(rc) qq_secret_clear(out,sizeof(*out));return rc;
}
int qq_parse_songs(struct qq_json *d,const char *s,size_t n,struct qq_song_page *out,uint64_t *code) {
 int data,array,rc=QQ_AUTH_PROTOCOL;unsigned i,j;
 if(!out) return rc;
 qq_secret_clear(out,sizeof(*out));
 data=qq_cgi_data(d,s,n,code);if(data<0) return data;
 if(number(d,qq_json_get(d,(unsigned)data,"total_song_num"),&out->total)||flag(d,qq_json_get(d,(unsigned)data,"hasmore"),&out->more)) goto done;
 array=qq_json_get(d,(unsigned)data,"songlist");if(array<0||d->nodes[array].type!=QQ_JSON_ARRAY) goto done;
 for(i=(unsigned)array+1;i<d->nodes[array].next;i=d->nodes[i].next) {
  struct qq_song *p;int album,singers,title,node;size_t used=0;
  if(out->count==QQ_SONG_PAGE_LIMIT||d->nodes[i].type!=QQ_JSON_OBJECT) goto done;
  p=&out->entries[out->count];
  if(number(d,qq_json_get(d,i,"id"),&p->id)||!p->id||string(d,qq_json_get(d,i,"mid"),p->mid,sizeof(p->mid),1)||!identifier(p->mid)) goto done;
  title=qq_json_get(d,i,"title");if(title<0) title=qq_json_get(d,i,"name");
  if(string(d,title,p->title,sizeof(p->title),1)) goto done;
  album=qq_json_get(d,i,"album");
  if(album<0||d->nodes[album].type!=QQ_JSON_OBJECT||number(d,qq_json_get(d,(unsigned)album,"id"),&p->album_id)||
     string(d,qq_json_get(d,(unsigned)album,"mid"),p->album_mid,sizeof(p->album_mid),0)||
     string(d,qq_json_get(d,(unsigned)album,"name"),p->album,sizeof(p->album),0)) goto done;
  if(p->album_mid[0]&&!identifier(p->album_mid)) goto done;
  singers=qq_json_get(d,i,"singer");if(singers<0||d->nodes[singers].type!=QQ_JSON_ARRAY) goto done;
  for(j=(unsigned)singers+1;j<d->nodes[singers].next;j=d->nodes[j].next) {
   char artist[257];size_t length;
   if(string(d,qq_json_get(d,j,"name"),artist,sizeof(artist),1)) goto done;
   length=strlen(artist);if(length+(used?3:0)>=sizeof(p->artist)-used) goto done;
   if(used) {memcpy(p->artist+used," / ",3);used+=3;}
   memcpy(p->artist+used,artist,length);used+=length;p->artist[used]=0;
  }
  if(optional_number(d,i,"index_album",&p->track)||optional_number(d,i,"index_cd",&p->disc)||
     optional_number(d,i,"type",&p->type)||
     optional_number(d,i,"interval",&p->duration)||string(d,qq_json_get(d,i,"time_public"),p->date,sizeof(p->date),0)) goto done;
  /* Preserve the PC import convention: QQ index_cd is zero-based. */
  if(qq_json_get(d,i,"index_cd")>=0) {if(p->disc==UINT64_MAX) goto done;p->disc++;}
  node=qq_json_get(d,i,"file");if(node>=0&&string(d,qq_json_get(d,(unsigned)node,"media_mid"),p->media_mid,sizeof(p->media_mid),0)) goto done;
  if(p->media_mid[0]&&!identifier(p->media_mid)) goto done;
  out->count++;
 }
 if(out->count>out->total||(!out->count&&out->more)) goto done;
 rc=0;
done:
 qq_secret_clear(d,sizeof(*d));if(rc) qq_secret_clear(out,sizeof(*out));return rc;
}
int qq_catalog_advance(struct qq_catalog_cursor *c,unsigned count,unsigned more,uint64_t total) {
 uint64_t next;
 if(!c||c->finished||c->pages>=1000||more>1||(!count&&more)||c->offset>UINT64_MAX-count) return -1;
 next=c->offset+count;
 if(next>total||(c->pages&&c->total!=total)||(more&&next>=total)||(!more&&next!=total)) return -1;
 c->offset=next;c->total=total;c->pages++;c->finished=!more;return 0;
}
