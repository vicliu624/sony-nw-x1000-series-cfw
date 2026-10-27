#include "inventory.h"
#include "../native/sha256.h"
static unsigned length(const char *s){unsigned n=0;while(s[n])n++;return n;}
static int compare(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return (unsigned char)*a-(unsigned char)*b;}
static char lower(char c){return c>='A'&&c<='Z'?(char)(c+'a'-'A'):c;}
static int hex(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
static int equal_hash(const unsigned char *a,const unsigned char *b) {
 for(unsigned i=0;i<32;i++)if(a[i]!=b[i])return 0;
 return 1;
}
static int conflict(const char *,const char *);
static int path_ok(const char *path) {
 unsigned start=0,n=length(path);
 if(!n||n>160||conflict(path,"files.sha256"))return 0;
 for(unsigned i=0;i<=n;i++) {
  char c=path[i];
  if(c&&c!='/') {
   if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'))return 0;
  } else {
   unsigned count=i-start;char base[5]={0};unsigned used=0;
   if(!count||count>64||path[i-1]=='.')return 0;
   if((count==1&&path[start]=='.')||(count==2&&path[start]=='.'&&path[start+1]=='.'))return 0;
   for(unsigned j=start;j<i&&path[j]!='.';j++) {
    if(used<4)base[used]=lower(path[j]);
    used++;
   }
   if(!compare(base,"con")||!compare(base,"nul")||!compare(base,"aux")||!compare(base,"prn")||
      (used==4&&base[3]>='1'&&base[3]<='9'&&
       ((base[0]=='c'&&base[1]=='o'&&base[2]=='m')||(base[0]=='l'&&base[1]=='p'&&base[2]=='t'))))return 0;
   start=i+1;
  }
 }
 return 1;
}
static int conflict(const char *a,const char *b) {
 unsigned i=0;int case_difference=0;
 while(a[i]&&b[i]&&lower(a[i])==lower(b[i])) {
  if(a[i]!=b[i])case_difference=1;
  if(a[i]=='/'&&case_difference)return 1; /* Same directory, inconsistent spelling. */
  i++;
 }
 return (!a[i]&&(!b[i]||b[i]=='/'))||(!b[i]&&a[i]=='/');
}
int hb_inventory_validate(const struct hb_inventory *inventory) {
 unsigned required=0,total=0;
 if(!inventory||inventory->count<2||inventory->count>HB_INVENTORY_FILES)return HB_PACKAGE_MANIFEST;
 for(unsigned i=0;i<inventory->count;i++) {
  const struct hb_inventory_file *file=inventory->files+i;unsigned n=0,depth=0;
  while(n<sizeof file->path&&file->path[n]){if(file->path[n]=='/')depth++;n++;}
  if(n==sizeof file->path||depth>16||!path_ok(file->path)||file->bytes>134217728u||
     file->bytes>HB_INVENTORY_TOTAL_BYTES-total)return HB_PACKAGE_MANIFEST;
  for(unsigned j=0;j<i;j++)if(conflict(inventory->files[j].path,file->path))return HB_PACKAGE_MANIFEST;
  if(i&&compare(inventory->files[i-1].path,file->path)>=0)return HB_PACKAGE_MANIFEST;
  if(!compare(file->path,"app")){if(file->bytes<84)return HB_PACKAGE_MANIFEST;required|=1;}
  if(!compare(file->path,"app.ini")){if(!file->bytes||file->bytes>1024)return HB_PACKAGE_MANIFEST;required|=2;}
  total+=file->bytes;
 }
 return required==3&&inventory->total_bytes==total?HB_PACKAGE_OK:HB_PACKAGE_MANIFEST;
}
int hb_inventory_parse(const unsigned char *data,unsigned bytes,struct hb_inventory *out) {
 char line[256];unsigned start=0,number=0,required=0;
 if(!out)return HB_PACKAGE_MANIFEST;
 out->count=out->total_bytes=0;
 if(!data||!bytes||bytes>HB_INVENTORY_TEXT_BYTES||data[bytes-1]!='\n')return HB_PACKAGE_MANIFEST;
 while(start<bytes) {
  unsigned end=start,n;
  while(end<bytes&&data[end]!='\n')end++;
  n=end-start;if(n&&data[end-1]=='\r')n--;
  if(n>=sizeof line)goto invalid;
  for(unsigned i=0;i<n;i++){if(!data[start+i])goto invalid;line[i]=(char)data[start+i];}
  line[n]=0;start=end+1;
  if(!number++){if(compare(line,"HBFILES1"))goto invalid;continue;}
  if(out->count>=HB_INVENTORY_FILES||n<68||line[64]!=' ')goto invalid;
  struct hb_inventory_file *file=out->files+out->count;
  for(unsigned i=0;i<32;i++) {
   int a=hex(line[i*2]),b=hex(line[i*2+1]);if(a<0||b<0)goto invalid;
   file->sha256[i]=(unsigned char)((a<<4)|b);
  }
  unsigned i=65,value=0,digits=0;
  while(line[i]&&line[i]!=' ') {
   if(line[i]<'0'||line[i]>'9'||(digits&&line[65]=='0'))goto invalid;
   unsigned digit=(unsigned)(line[i]-'0');
   if(value>(134217728u-digit)/10u)goto invalid;
   value=value*10u+digit;i++;digits++;
  }
  if(!digits||line[i]!=' '||!path_ok(line+i+1))goto invalid;
  const char *path=line+i+1;
  for(unsigned j=0;j<out->count;j++)if(conflict(out->files[j].path,path))goto invalid;
  if(out->count&&compare(out->files[out->count-1].path,path)>=0)goto invalid;
  unsigned len=length(path);for(unsigned j=0;j<=len;j++)file->path[j]=path[j];
  if(!compare(path,"app"))required|=1;
  if(!compare(path,"app.ini"))required|=2;
  if(value>HB_INVENTORY_TOTAL_BYTES-out->total_bytes)goto invalid;
  file->bytes=value;out->total_bytes+=value;out->count++;
 }
 if(required==3)return HB_PACKAGE_OK;
invalid:
 out->count=out->total_bytes=0;return HB_PACKAGE_MANIFEST;
}
int hb_inventory_bind_manifest(const struct hb_inventory *inventory,const unsigned char *data,
                               unsigned bytes,const char *id,struct hb_package *package) {
 if(!inventory||inventory->count>HB_INVENTORY_FILES)return HB_PACKAGE_MANIFEST;
 int result=hb_package_parse(data,bytes,id,package);if(result)return result;
 struct hb_sha256 hash;unsigned char digest[32];unsigned found=0;
 hb_sha256_init(&hash);hb_sha256_update(&hash,data,bytes);hb_sha256_final(&hash,digest);
 for(unsigned i=0;i<inventory->count;i++) {
  const struct hb_inventory_file *file=inventory->files+i;
  if(!compare(file->path,"app.ini")) {
   if(file->bytes!=bytes||!equal_hash(file->sha256,digest))return HB_PACKAGE_HASH;
   found|=1;
  } else if(!compare(file->path,"app")) {
   if(file->bytes!=package->bytes||!equal_hash(file->sha256,package->sha256))return HB_PACKAGE_HASH;
   found|=2;
  }
 }
 return found==3?HB_PACKAGE_OK:HB_PACKAGE_MANIFEST;
}
int hb_inventory_verify_file(const struct hb_inventory_file *file,void *context,
                             int (*read_chunk)(void *,unsigned char *,unsigned)) {
 struct hb_sha256 hash;unsigned char buffer[4096],digest[32];unsigned total=0;
 if(!file||!read_chunk||file->bytes>134217728u)return HB_PACKAGE_MANIFEST;
 hb_sha256_init(&hash);
 for(;;) {
  int n=read_chunk(context,buffer,sizeof buffer);
  if(n<0||(unsigned)n>sizeof buffer)return HB_PACKAGE_IO;
  if(!n)break;
  if((unsigned)n>file->bytes-total)return HB_PACKAGE_SIZE;
  total+=(unsigned)n;hb_sha256_update(&hash,buffer,(unsigned)n);
 }
 if(total!=file->bytes)return HB_PACKAGE_SIZE;
 hb_sha256_final(&hash,digest);return equal_hash(file->sha256,digest)?HB_PACKAGE_OK:HB_PACKAGE_HASH;
}
