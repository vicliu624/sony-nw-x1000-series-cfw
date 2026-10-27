#include "qqmusic_json.h"
#include <string.h>
static int hex(char c) {
 if(c>='0'&&c<='9') return c-'0';
 if(c>='a'&&c<='f') return c-'a'+10;
 return c>='A'&&c<='F'?c-'A'+10:-1;
}
static int hex4(const char *s,size_t n,size_t *i,uint32_t *cp) {
 unsigned j;uint32_t v=0;if(n-*i<4) return -1;
 for(j=0;j<4;j++) {int h=hex(s[(*i)++]);if(h<0) return -1;v=v*16+(unsigned)h;}
 *cp=v;return 0;
}
static int scalar(const char *s,size_t n,size_t *i,uint32_t *cp) {
 uint32_t c;unsigned more,j;uint32_t min;
 if(*i>=n) return -1;
 c=(unsigned char)s[(*i)++];
 if(c=='\\') {
  if(*i>=n) return -1;
  c=(unsigned char)s[(*i)++];
  if(c=='u') {
   if(hex4(s,n,i,&c)) return -1;
   if(c>=0xd800&&c<=0xdbff) {
    uint32_t low;if(n-*i<6||s[*i]!='\\'||s[*i+1]!='u') return -1;*i+=2;
    if(hex4(s,n,i,&low)||low<0xdc00||low>0xdfff) return -1;
    c=0x10000+(c-0xd800)*1024+low-0xdc00;
   } else if(c>=0xdc00&&c<=0xdfff) return -1;
   if(!c) return -1;
  } else if(c=='b') c=8;else if(c=='f') c=12;else if(c=='n') c=10;
  else if(c=='r') c=13;else if(c=='t') c=9;
  else if(c!='"'&&c!='\\'&&c!='/') return -1;
 } else if(c<32) return -1;
 else if(c>=128) {
  if(c>=0xc2&&c<=0xdf) {more=1;min=0x80;c&=31;}
  else if(c>=0xe0&&c<=0xef) {more=2;min=0x800;c&=15;}
  else if(c>=0xf0&&c<=0xf4) {more=3;min=0x10000;c&=7;}
  else return -1;
  if(n-*i<more) return -1;
  for(j=0;j<more;j++) {unsigned v=(unsigned char)s[(*i)++];if((v&0xc0)!=0x80) return -1;c=c*64+(v&63);}
  if(c<min||c>0x10ffff||(c>=0xd800&&c<=0xdfff)) return -1;
 }
 *cp=c;return 0;
}
int qq_json_string(const struct qq_json *d,unsigned node,char *out,size_t cap) {
 size_t i,k=0,end;if(!out||!cap) return -1;out[0]=0;
 if(!d||node>=d->used||d->nodes[node].type!=QQ_JSON_STRING) return -1;
 i=d->nodes[node].start;end=d->nodes[node].end;
 while(i<end) {
  uint32_t cp;unsigned char bytes[4];unsigned n,j;
  if(scalar(d->text,end,&i,&cp)) goto bad;
  if(cp<128) {n=1;bytes[0]=(unsigned char)cp;}
  else if(cp<2048) {n=2;bytes[0]=(unsigned char)(0xc0|(cp>>6));bytes[1]=(unsigned char)(0x80|(cp&63));}
  else if(cp<65536) {n=3;bytes[0]=(unsigned char)(0xe0|(cp>>12));bytes[1]=(unsigned char)(0x80|((cp>>6)&63));bytes[2]=(unsigned char)(0x80|(cp&63));}
  else {n=4;bytes[0]=(unsigned char)(0xf0|(cp>>18));bytes[1]=(unsigned char)(0x80|((cp>>12)&63));bytes[2]=(unsigned char)(0x80|((cp>>6)&63));bytes[3]=(unsigned char)(0x80|(cp&63));}
  if(n>=cap-k) goto bad;
  for(j=0;j<n;j++) out[k++]=(char)bytes[j];
 }
 out[k]=0;return 0;
bad: memset(out,0,cap);return -1;
}
static void ws(const struct qq_json *d,size_t *i) {
 while(*i<d->bytes&&(d->text[*i]==' '||d->text[*i]=='\t'||d->text[*i]=='\r'||d->text[*i]=='\n')) ++*i;
}
static int value(struct qq_json *d,size_t *i,unsigned depth) {
 unsigned id;char c;size_t start;
 ws(d,i);if(*i>=d->bytes||depth>16||d->used==QQ_JSON_NODES) return -1;
 id=d->used++;start=*i;c=d->text[*i];d->nodes[id].start=start;
 if(c=='"') {
  d->nodes[id].type=QQ_JSON_STRING;(*i)++;d->nodes[id].start=*i;
  while(*i<d->bytes&&d->text[*i]!='"') {uint32_t cp;if(scalar(d->text,d->bytes,i,&cp)) return -1;}
  if(*i==d->bytes) return -1;
  d->nodes[id].end=(*i)++;
 } else if(c=='{'||c=='[') {
  int object=c=='{';d->nodes[id].type=object?QQ_JSON_OBJECT:QQ_JSON_ARRAY;(*i)++;ws(d,i);
  if(*i<d->bytes&&d->text[*i]==(object?'}':']')) (*i)++;
  else for(;;) {
   if(object) {
    int key;unsigned prior;char current[129],old[129];
    if(*i>=d->bytes||d->text[*i]!='"') return -1;
    key=value(d,i,depth+1);if(key<0||qq_json_string(d,(unsigned)key,current,sizeof(current))) return -1;
    for(prior=id+1;prior<(unsigned)key;) {
     if(qq_json_string(d,prior,old,sizeof(old))||!strcmp(current,old)) return -1;
     prior=d->nodes[prior+1].next;
    }
    ws(d,i);if(*i>=d->bytes||d->text[(*i)++]!=':') return -1;
   }
   if(value(d,i,depth+1)<0) return -1;
   ws(d,i);
   if(*i>=d->bytes) return -1;
   if(d->text[*i]==(object?'}':']')) {(*i)++;break;}
   if(d->text[(*i)++]!=',') return -1;
   ws(d,i);
  }
  d->nodes[id].end=*i;
 } else if(c=='t'||c=='f'||c=='n') {
  const char *s=c=='t'?"true":c=='f'?"false":"null";size_t n=strlen(s);
  if(d->bytes-*i<n||memcmp(d->text+*i,s,n)) return -1;
  *i+=n;d->nodes[id].type=QQ_JSON_LITERAL;d->nodes[id].end=*i;
 } else {
  d->nodes[id].type=QQ_JSON_NUMBER;
  if(c=='-') (*i)++;
  if(*i>=d->bytes) return -1;
  if(d->text[*i]=='0') (*i)++;
  else {size_t digits=*i;while(*i<d->bytes&&d->text[*i]>='0'&&d->text[*i]<='9') (*i)++;if(*i==digits) return -1;}
  if(*i<d->bytes&&d->text[*i]=='.') {size_t digits=++*i;while(*i<d->bytes&&d->text[*i]>='0'&&d->text[*i]<='9') (*i)++;if(*i==digits) return -1;}
  if(*i<d->bytes&&(d->text[*i]=='e'||d->text[*i]=='E')) {
   size_t digits;(*i)++;if(*i<d->bytes&&(d->text[*i]=='+'||d->text[*i]=='-')) (*i)++;
   digits=*i;while(*i<d->bytes&&d->text[*i]>='0'&&d->text[*i]<='9') (*i)++;if(*i==digits) return -1;
  }
  d->nodes[id].end=*i;
 }
 d->nodes[id].next=d->used;return (int)id;
}
int qq_json_parse(struct qq_json *d,const char *s,size_t n) {
 size_t i=0;if(!d) return -1;memset(d,0,sizeof(*d));
 if(!s||!n||n>262144) return -1;
 d->text=s;d->bytes=n;
 if(value(d,&i,0)<0) goto bad;
 ws(d,&i);if(i!=n) goto bad;return 0;
bad: memset(d,0,sizeof(*d));return -1;
}
int qq_json_get(const struct qq_json *d,unsigned object,const char *key) {
 unsigned i;char text[129];
 if(!d||object>=d->used||d->nodes[object].type!=QQ_JSON_OBJECT||!key) return -1;
 for(i=object+1;i<d->nodes[object].next;i=d->nodes[i+1].next) {
  if(qq_json_string(d,i,text,sizeof(text))) return -1;
  if(!strcmp(text,key)) return (int)i+1;
 }return -1;
}
int qq_json_uint(const struct qq_json *d,unsigned node,uint64_t *out) {
 size_t i;uint64_t n=0;if(!d||!out||node>=d->used||d->nodes[node].type!=QQ_JSON_NUMBER) return -1;
 for(i=d->nodes[node].start;i<d->nodes[node].end;i++) {
  unsigned digit=(unsigned)(d->text[i]-'0');if(digit>9||n>(UINT64_MAX-digit)/10) return -1;n=n*10+digit;
 }*out=n;return 0;
}
