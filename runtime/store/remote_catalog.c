#include "remote_catalog.h"
#include "https_url.h"
#include "../native/sha256.h"
#include <string.h>
static int id_ok(const char *s){unsigned n=(unsigned)strlen(s);if(!n||n>32)return 0;for(unsigned i=0;i<n;i++)if(!((s[i]>='a'&&s[i]<='z')||(s[i]>='0'&&s[i]<='9')||(i&&s[i]=='-')))return 0;return 1;}
static int version_ok(const char *s){unsigned n=(unsigned)strlen(s);if(!n||n>32)return 0;for(unsigned i=0;i<n;i++)if(!((s[i]>='a'&&s[i]<='z')||(s[i]>='A'&&s[i]<='Z')||(s[i]>='0'&&s[i]<='9')||s[i]=='.'||s[i]=='-'||s[i]=='+'))return 0;return 1;}
static int number(const char *s,unsigned maximum,unsigned *out){unsigned n=0;if(!*s||(*s=='0'&&s[1]))return -1;for(;*s;s++){if(*s<'0'||*s>'9'||n>(maximum-(unsigned)(*s-'0'))/10)return -1;n=n*10+(unsigned)(*s-'0');}if(!n||n>maximum)return -1;*out=n;return 0;}
static int digest(const char *s,unsigned char *out){if(strlen(s)!=64)return -1;for(unsigned i=0;i<32;i++){unsigned value=0;for(unsigned k=0;k<2;k++){char c=s[i*2+k];unsigned n;if(c>='0'&&c<='9')n=(unsigned)(c-'0');else if(c>='a'&&c<='f')n=(unsigned)(c-'a'+10);else return -1;value=value*16+n;}out[i]=(unsigned char)value;}return 0;}
static int base_ok(const char *s){unsigned n=(unsigned)strlen(s);if(!n||n>512||s[n-1]!='/')return 0;for(unsigned i=0;i<n;i++)if(s[i]=='?'||s[i]=='#')return 0;struct hb_https_url url;return !hb_https_url_parse(s,&url);}
static int reject(struct hb_remote_catalog *c){c->count=0;c->valid=0;return -1;}
int hb_remote_catalog_parse(const unsigned char *data,unsigned bytes,struct hb_remote_catalog *c){
 if(!c)return -1;
 c->count=0;c->valid=0;
 if(!data||bytes<9||bytes>HB_REMOTE_CATALOG_BYTES||data[bytes-1]!='\n')return -1;
 int flat=!memcmp(data,"HBSTORE2\n",9);if(!flat&&memcmp(data,"HBSTORE1\n",9))return -1;
 unsigned pos=9;
 while(pos<bytes){
  if(c->count==HB_REMOTE_CATALOG_ENTRIES)return reject(c);
  char line[1024];unsigned used=0;
  while(pos<bytes&&data[pos]!='\n'){unsigned char ch=data[pos++];if((ch<32&&ch!='\t')||ch>126||used+1>=sizeof line)return reject(c);line[used++]=(char)ch;}
  if(pos==bytes||!used)return reject(c);
  pos++;line[used]=0;
  char *field[8];field[0]=line;unsigned count=1,expected=flat?8u:7u;
  for(unsigned i=0;i<used;i++)if(line[i]=='\t'){if(count==expected)return reject(c);line[i]=0;field[count++]=line+i+1;}
  if(count!=expected)return reject(c);
  struct hb_remote_entry *e=c->entries+c->count;
  e->asset_prefix[0]=0;
  if(!id_ok(field[0])||!version_ok(field[1])||!base_ok(field[2])||number(field[3],1024,&e->manifest_bytes)||digest(field[4],e->manifest_sha256)||number(field[5],HB_INVENTORY_TEXT_BYTES,&e->index_bytes)||digest(field[6],e->index_sha256))return reject(c);
  if(c->count&&strcmp(c->entries[c->count-1].id,field[0])>=0)return reject(c);
  if(flat){unsigned length=(unsigned)strlen(field[7]);if(!length||length>40)return reject(c);for(unsigned i=0;i<length;i++)if(!((field[7][i]>='a'&&field[7][i]<='z')||(field[7][i]>='0'&&field[7][i]<='9')||field[7][i]=='-'))return reject(c);strcpy(e->asset_prefix,field[7]);}
  strcpy(e->id,field[0]);strcpy(e->version,field[1]);strcpy(e->base_url,field[2]);c->count++;
 }
 c->valid=1;return 0;
}
static int matches(const unsigned char *data,unsigned bytes,const unsigned char expected[32]){struct hb_sha256 s;unsigned char out[32];hb_sha256_init(&s);hb_sha256_update(&s,data,bytes);hb_sha256_final(&s,out);return !memcmp(out,expected,32);}
int hb_remote_entry_plan(const struct hb_remote_entry *e,const unsigned char *manifest,unsigned mf_bytes,const unsigned char *index,unsigned ix_bytes,struct hb_package_download_plan *p){
 if(!p)return -1;
 p->valid=0;
 if(!e||!manifest||!index||!memchr(e->id,0,sizeof e->id)||!memchr(e->version,0,sizeof e->version)||!memchr(e->base_url,0,sizeof e->base_url)||!id_ok(e->id)||!version_ok(e->version)||!base_ok(e->base_url)||!mf_bytes||mf_bytes>1024||!ix_bytes||ix_bytes>HB_INVENTORY_TEXT_BYTES||mf_bytes!=e->manifest_bytes||ix_bytes!=e->index_bytes||!matches(manifest,mf_bytes,e->manifest_sha256)||!matches(index,ix_bytes,e->index_sha256))return -1;
 if(hb_package_download_plan_init(p,e->id,e->base_url,manifest,mf_bytes,index,ix_bytes))return -1;
 if(strcmp(p->bundle.package.version,e->version)){p->valid=0;return -1;}
 if(!memchr(e->asset_prefix,0,sizeof e->asset_prefix)){p->valid=0;return -1;}
 strcpy(p->asset_prefix,e->asset_prefix);return 0;
}
