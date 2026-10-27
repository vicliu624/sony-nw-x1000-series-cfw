#include "qqmusic_storage.h"
#include <string.h>
static int canonical(const char *p) {
 size_t i=0,start;if(!p||p[0]!='/') return 0;
 if(!p[1]) return 1;
 while(p[i]) {
  if(i>=2048||p[i++]!='/') return 0;
  start=i;
  while(p[i]&&p[i]!='/') {
   unsigned char c=(unsigned char)p[i++];if(i>2048||c<32||c==127||c=='\\') return 0;
  }
  if(i==start||(i-start==1&&p[start]=='.')||(i-start==2&&p[start]=='.'&&p[start+1]=='.')) return 0;
  if(p[i]=='/'&&!p[i+1]) return 0;
 }return 1;
}
static int mount_row(const char *s,size_t n,char fields[6][513]) {
 size_t i=0,k;unsigned field;
 for(field=0;field<6;field++) {
  while(i<n&&(s[i]==' '||s[i]=='\t')) i++;
  k=0;while(i<n&&s[i]!=' '&&s[i]!='\t') {
   unsigned char c=(unsigned char)s[i++];if(c<33||c>126||k==512) return -1;
   fields[field][k++]=(char)c;
  }
  if(!k) return -1;
  fields[field][k]=0;
 }
 while(i<n&&(s[i]==' '||s[i]=='\t')) i++;
 return i==n?0:-1;
}
static int writable(const char *options) {
 const char *p=options;int rw=0,ro=0;
 while(*p) {const char *e=strchr(p,',');size_t n=e?(size_t)(e-p):strlen(p);
  if(n==2&&!memcmp(p,"rw",2)) rw++;
  if(n==2&&!memcmp(p,"ro",2)) ro++;
  if(!e) break;
  p=e+1;
 }return rw==1&&!ro;
}
static int mounts_check(const struct qq_storage_policy *policy,const char *s,size_t n,unsigned *reason) {
 size_t pos=0;unsigned root=0,underlay=0,user=0;char f[6][513];
#define BAD_MOUNT(why) do {if(reason)*reason=(why);return QQ_STORAGE_MOUNT;}while(0)
 if(reason)*reason=QQ_MOUNT_OK;
 if(!s||!n||n>65536||memchr(s,0,n)) BAD_MOUNT(QQ_MOUNT_INPUT);
 while(pos<n) {
  size_t start=pos;while(pos<n&&s[pos]!='\n') pos++;
  if(pos==n||mount_row(s+start,pos-start,f)) BAD_MOUNT(QQ_MOUNT_ROW);
  pos++;
  if(!strcmp(f[1],"/")) {
   if(!strcmp(f[0],policy->source))BAD_MOUNT(QQ_MOUNT_ROOT);
   /* Old kernels retain rootfs beneath the mounted real root. This exact
    * single underlay must precede the actual root; arbitrary duplicate roots
    * and duplicate user mounts are still rejected. Actual st_dev checks below
    * continue to bind destinations to a device different from visible /. */
   if(!strcmp(f[0],"rootfs")&&!strcmp(f[2],"rootfs")){
    if(root||underlay++)BAD_MOUNT(QQ_MOUNT_ROOT);
   }else if(++root!=1)BAD_MOUNT(QQ_MOUNT_ROOT);
  }
  if(!strcmp(f[1],"/contents")) {
   if(++user!=1)BAD_MOUNT(QQ_MOUNT_USER_DUPLICATE);
   if(strcmp(f[0],policy->source))BAD_MOUNT(QQ_MOUNT_SOURCE);
   if(strcmp(f[2],policy->filesystem))BAD_MOUNT(QQ_MOUNT_FILESYSTEM);
   if(!writable(f[3]))BAD_MOUNT(QQ_MOUNT_READONLY);
  } else if(!strncmp(f[1],"/contents/",10)) BAD_MOUNT(QQ_MOUNT_NESTED);
 }
 if((!root&&!underlay)||user!=1)BAD_MOUNT(QQ_MOUNT_MISSING);
#undef BAD_MOUNT
 return 0;
}
int qq_storage_mount_reason(const struct qq_storage_policy *policy,const char *s,size_t n){
 unsigned reason=QQ_MOUNT_INPUT;
 if(!policy||!policy->source||!policy->filesystem)return QQ_MOUNT_INPUT;
 (void)mounts_check(policy,s,n,&reason);return (int)reason;
}
int qq_storage_preflight(const struct qq_storage_policy *policy,const char *mounts,size_t n,
 const struct qq_storage_directory *dirs,size_t count,const struct qq_storage_plan *plan,uint64_t *required) {
 size_t i;uint64_t peak=0,available,unit,items[7];int rc;
 if(required) *required=0;
 if(!policy||!policy->source||!policy->filesystem||!dirs||count<2||count>64||!plan||!required) return QQ_STORAGE_INPUT;
 if(strcmp(policy->filesystem,"vfat")||strncmp(policy->source,"/dev/",5)) return QQ_STORAGE_INPUT;
 rc=mounts_check(policy,mounts,n,0);if(rc) return rc;
 if(!dirs[0].path||!dirs[1].path||strcmp(dirs[0].path,"/")||strcmp(dirs[1].path,"/contents")||dirs[0].device==dirs[1].device) return QQ_STORAGE_BOUNDARY;
 for(i=0;i<count;i++) {
  size_t parent;
  if(!canonical(dirs[i].path)||(dirs[i].mode&0170000u)!=0040000u) return QQ_STORAGE_BOUNDARY;
  if(i&&dirs[i].device!=dirs[1].device) return QQ_STORAGE_BOUNDARY;
  if(i<2) continue;
  parent=strlen(dirs[i-1].path);
  if(strncmp(dirs[i].path,dirs[i-1].path,parent)||dirs[i].path[parent]!='/'||!dirs[i].path[parent+1]||strchr(dirs[i].path+parent+1,'/')) return QQ_STORAGE_BOUNDARY;
 }
 unit=plan->allocation_unit;
 if(unit<512||unit>1048576||(unit&(unit-1))) return QQ_STORAGE_INPUT;
 if(plan->available_units>UINT64_MAX/unit) return QQ_STORAGE_OVERFLOW;
 available=plan->available_units*unit;
 items[0]=plan->source;items[1]=plan->decoded;items[2]=plan->mp3;items[3]=plan->temporary;items[4]=plan->artwork;items[5]=plan->metadata;items[6]=plan->reserve;
 for(i=0;i<7;i++) {
  uint64_t value=items[i],rounded;
  if(i<6) {
   uint64_t padding;
   if(value&&!plan->files[i]) return QQ_STORAGE_INPUT;
   if(plan->files[i]>4096) return QQ_STORAGE_INPUT;
   /* Upper bound for rounding each file separately, given aggregate bytes. */
   padding=plan->files[i]?(plan->files[i]-1)*(unit-1):0;
   if(value>UINT64_MAX-padding) return QQ_STORAGE_OVERFLOW;
   value+=padding;
  }
  if(value>UINT64_MAX-(unit-1)) return QQ_STORAGE_OVERFLOW;
  rounded=(value+unit-1)&~(unit-1);
  if(peak>UINT64_MAX-rounded) return QQ_STORAGE_OVERFLOW;
  peak+=rounded;
 }
 if(plan->directory_units>UINT64_MAX/unit||peak>UINT64_MAX-plan->directory_units*unit) return QQ_STORAGE_OVERFLOW;
 peak+=plan->directory_units*unit;
 if(peak>available) return QQ_STORAGE_SPACE;
 *required=peak;return 0;
}
