#include "package.h"
#include "../native/sha256.h"
static unsigned length(const char *s) { unsigned n=0;while(s[n])n++;return n; }
static int eq(const char *a,const char *b) {
 while(*a&&*a==*b){a++;b++;}return *a==*b;
}
static int copy(char *out,const char *s,unsigned capacity) {
 unsigned n=length(s);if(n>=capacity)return -1;
 for(unsigned i=0;i<=n;i++)out[i]=s[i];
 return 0;
}
static int id_ok(const char *s) {
 unsigned n=length(s);if(!n||n>32)return 0;
 for(unsigned i=0;i<n;i++)if(!((s[i]>='a'&&s[i]<='z')||
    (s[i]>='0'&&s[i]<='9')||(s[i]=='-'&&i)))return 0;
 return 1;
}
static int hex(char c) {
 return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
}
int hb_package_parse(const unsigned char *input,unsigned n,const char *expected,
                     struct hb_package *out) {
 char buffer[1025];struct hb_package result={{0},{0},{0},0,{0}};unsigned seen=0;
 if(!input||!expected||!out||!n||n>1024||!id_ok(expected))return HB_PACKAGE_MANIFEST;
 for(unsigned i=0;i<n;i++) {
  if(!input[i])return HB_PACKAGE_MANIFEST;
  buffer[i]=(char)input[i];
 }
 buffer[n]=0;
 for(unsigned start=0;start<n;) {
  unsigned end=start,bit=0;
  while(end<n&&buffer[end]!='\n')end++;
  buffer[end]=0;
  if(end>start&&buffer[end-1]=='\r')buffer[end-1]=0;
  char *key=buffer+start,*value=key;
  while(*value&&*value!='=')value++;
  if(!*value)return HB_PACKAGE_MANIFEST;
  *value++=0;
  if(eq(key,"api")){bit=1;if(!eq(value,"1"))return HB_PACKAGE_MANIFEST;}
  else if(eq(key,"id")) {
   bit=2;if(!eq(value,expected)||copy(result.id,value,sizeof result.id))return HB_PACKAGE_MANIFEST;
  } else if(eq(key,"name")) {
   bit=4;if(!*value||copy(result.name,value,sizeof result.name))return HB_PACKAGE_MANIFEST;
   for(unsigned i=0;value[i];i++)if((unsigned char)value[i]<32)return HB_PACKAGE_MANIFEST;
  } else if(eq(key,"version")) {
   bit=8;if(!*value||copy(result.version,value,sizeof result.version))return HB_PACKAGE_MANIFEST;
  } else if(eq(key,"target")){bit=16;if(!eq(value,"sony-nw-x1000-jp"))return HB_PACKAGE_MANIFEST;}
  else if(eq(key,"exec")){bit=32;if(!eq(value,"app"))return HB_PACKAGE_MANIFEST;}
  else if(eq(key,"bytes")) {
   bit=64;if(!*value)return HB_PACKAGE_MANIFEST;
   for(unsigned i=0;value[i];i++) {
    if(value[i]<'0'||value[i]>'9'||result.bytes>13421772u)return HB_PACKAGE_MANIFEST;
    result.bytes=result.bytes*10u+(unsigned)(value[i]-'0');
   }
   if(result.bytes<84||result.bytes>134217728u)return HB_PACKAGE_MANIFEST;
  } else if(eq(key,"sha256")) {
   bit=128;if(length(value)!=64)return HB_PACKAGE_MANIFEST;
   for(unsigned i=0;i<32;i++) {
    int a=hex(value[2*i]),b=hex(value[2*i+1]);
    if(a<0||b<0)return HB_PACKAGE_MANIFEST;
    result.sha256[i]=(unsigned char)((a<<4)|b);
   }
  } else return HB_PACKAGE_MANIFEST;
  if(seen&bit)return HB_PACKAGE_MANIFEST;
  seen|=bit;start=end+1;
 }
 if(seen!=255)return HB_PACKAGE_MANIFEST;
 *out=result;return HB_PACKAGE_OK;
}
int hb_package_verify_program(const struct hb_package *package,void *context,
                              int (*read_chunk)(void *,unsigned char *,unsigned)) {
 unsigned char buffer[4096],header[52],digest[32];unsigned total=0;
 struct hb_sha256 hash;
 if(!package||!read_chunk||package->bytes<84||package->bytes>134217728u)
  return HB_PACKAGE_MANIFEST;
 hb_sha256_init(&hash);
 for(;;) {
  int n=read_chunk(context,buffer,sizeof buffer);
  if(n<0||(unsigned)n>sizeof buffer)return HB_PACKAGE_IO;
  if(!n)break;
  if((unsigned)n>package->bytes-total)return HB_PACKAGE_SIZE;
  for(unsigned i=0;i<(unsigned)n&&total+i<sizeof header;i++)header[total+i]=buffer[i];
  hb_sha256_update(&hash,buffer,(unsigned)n);total+=(unsigned)n;
 }
 if(total!=package->bytes)return HB_PACKAGE_SIZE;
 if(header[0]!=127||header[1]!='E'||header[2]!='L'||header[3]!='F'||
    header[4]!=1||header[5]!=1||header[6]!=1||header[16]!=2||header[17]||
    header[18]!=40||header[19])return HB_PACKAGE_ELF;
 hb_sha256_final(&hash,digest);
 for(unsigned i=0;i<32;i++)if(digest[i]!=package->sha256[i])return HB_PACKAGE_HASH;
 return HB_PACKAGE_OK;
}
