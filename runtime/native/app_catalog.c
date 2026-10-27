#include "app_catalog.h"
#include "linux_files.h"
#include "sha256.h"
static int eq(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static unsigned length(const char*s){unsigned n=0;while(s[n])n++;return n;}
static int copy(char*d,const char*s,unsigned max){unsigned n=length(s);if(n>=max)return -1;for(unsigned i=0;i<=n;i++)d[i]=s[i];return 0;}
static int join(char*out,const char*a,const char*b){unsigned n=length(a),m=length(b);if(n+m+2>256)return -1;copy(out,a,256);out[n++]='/';for(unsigned i=0;i<=m;i++)out[n+i]=b[i];return 0;}
static unsigned number(const char*s,int*ok){unsigned n=0;if(!*s){*ok=0;return 0;}while(*s){if(*s<'0'||*s>'9'||n>13421772){*ok=0;return 0;}n=n*10+(unsigned)(*s++-'0');}return n;}
static int hexchar(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
static int valid_id(const char*s){unsigned n=length(s);if(!n||n>32)return 0;for(unsigned i=0;i<n;i++)if(!((s[i]>='a'&&s[i]<='z')||(s[i]>='0'&&s[i]<='9')||(s[i]=='-'&&i)))return 0;return 1;}
static long read_limit(int fd,char*buf,unsigned max,volatile int *stop){unsigned used=0;while(used<max){if(*stop)return -1;long n=hb_file_read(fd,buf+used,max-used);if(n==-4)continue;if(n<0)return -1;if(!n)break;used+=(unsigned)n;}return used;}
static int manifest(const char*root,const char*id,struct hb_app*a,volatile int *stop){
 char path[256],buf[1025];unsigned seen=0;int ok=1;long n,fd;
 if(!valid_id(id)||join(a->folder,root,id)||!hb_path_is_not_link(a->folder)||join(path,a->folder,"app.ini")||!hb_path_is_not_link(path))return -1;
 fd=hb_file_open_read(path);if(fd<0)return -1;n=read_limit((int)fd,buf,1025,stop);hb_file_close(fd);if(n<=0||n>1024)return -1;buf[n]=0;
 for(int start=0;start<n;){int end=start;while(end<n&&buf[end]!='\n')end++;buf[end]=0;if(end>start&&buf[end-1]=='\r')buf[end-1]=0;char *v=buf+start;while(*v&&*v!='=')v++;if(!*v)return -1;*v++=0;unsigned bit=0;char*k=buf+start;
  if(eq(k,"api")){bit=1;if(!eq(v,"1"))return -1;}
  else if(eq(k,"id")){bit=2;if(!eq(v,id)||copy(a->id,v,33))return -1;}
  else if(eq(k,"name")){bit=4;if(!*v||copy(a->name,v,49))return -1;for(unsigned q=0;v[q];q++)if((unsigned char)v[q]<32)return -1;}
  else if(eq(k,"version")){bit=8;if(!*v||copy(a->version,v,33))return -1;}
  else if(eq(k,"target")){bit=16;if(!eq(v,"sony-nw-x1000-jp"))return -1;}
  else if(eq(k,"exec")){bit=32;if(!eq(v,"app"))return -1;}
  else if(eq(k,"bytes")){bit=64;a->bytes=number(v,&ok);if(!ok||a->bytes<84||a->bytes>134217728)return -1;}
  else if(eq(k,"sha256")){bit=128;if(length(v)!=64)return -1;for(int j=0;j<64;j++)if(hexchar(v[j])<0)return -1;copy(a->sha,v,65);}
  else return -1;
  if(seen&bit)return -1;
  seen|=bit;start=end+1;
 }
 if(seen!=255||join(path,a->folder,"app")||!hb_path_is_not_link(path))return -1;
 fd=hb_file_open_read(path);if(fd<0)return -1;unsigned char h[52];n=read_limit((int)fd,(char*)h,52,stop);long size=hb_file_seek_end(fd);hb_file_close(fd);
 if(n!=52||size!=(long)a->bytes||h[0]!=127||h[1]!='E'||h[2]!='L'||h[3]!='F'||h[4]!=1||h[5]!=1||h[6]!=1||h[16]!=2||h[17]||h[18]!=40||h[19])return -1;
 return 0;
}
int hb_catalog_scan(struct hb_catalog *catalog,const char *root,volatile int *stop) {
    if(!catalog||!root||!stop)return -1;
    catalog->count=catalog->rejected=0;
    if(*stop)return -1;
    struct hb_directory directory;
    if(hb_directory_open(&directory,root,stop))return -1;
    unsigned count=0,rejected=0,candidates=0;
    int result=0,failed=0;
    char id[33];
    while((result=hb_directory_next(&directory,id))>0) {
        if(id[0]=='.')continue;
        if(++candidates>64){failed=1;break;}
        if(count<HB_MAX_APPS) {
            if(!manifest(root,id,&catalog->apps[count],stop))count++;
            else rejected++;
        } else {
            if(eq(id,"store")) {
                struct hb_app store;
                if(!manifest(root,id,&store,stop))catalog->apps[count-1]=store;
            }
            rejected++;
        }
    }
    if(result<0)failed=1;
    hb_directory_close(&directory);
    catalog->count=count;catalog->rejected=rejected;
    if(*stop)return -1;
    if(failed)catalog->rejected++;
    for(unsigned i=0;i<count;i++) {
        if(eq(catalog->apps[i].id,"store")&&i) {
            struct hb_app temp=catalog->apps[0];
            catalog->apps[0]=catalog->apps[i];catalog->apps[i]=temp;
        }
    }
    return failed?-1:0;
}
int hb_app_executable(const struct hb_app *app,char path[256]) {
    return !app||!path?-1:join(path,app->folder,"app");
}
int hb_catalog_verify(const struct hb_app*a,volatile int *stop){if(!a||!stop)return 0;char path[256];unsigned char buf[4096],hash[32];struct hb_sha256 s;unsigned total=0;if(join(path,a->folder,"app")||!hb_path_is_not_link(path))return 0;long fd=hb_file_open_read(path);if(fd<0)return 0;long n;hb_sha256_init(&s);while((n=hb_file_read(fd,buf,sizeof buf))>0){if(*stop||total+(unsigned)n>a->bytes){hb_file_close(fd);return 0;}total+=(unsigned)n;hb_sha256_update(&s,buf,(unsigned)n);}hb_file_close(fd);if(n<0||total!=a->bytes)return 0;hb_sha256_final(&s,hash);for(unsigned i=0;i<32;i++)if(hash[i]!=(unsigned char)((hexchar(a->sha[i*2])<<4)|hexchar(a->sha[i*2+1])))return 0;return 1;}
