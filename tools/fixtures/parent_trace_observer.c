/* Generic ARM guest only. Exact capsules/shim/backend; GUI continuations,
 * image qualification and USB ownership inputs are fixture-controlled. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../../runtime/platform/player/parent_trace_observer.h"
#include "../../runtime/native/sha256.h"
#include "parent_observer_profile.h"
extern FILE *__real_fopen(const char *,const char *);
extern FILE *__real_fopen64(const char *,const char *);
FILE *__wrap_fopen(const char *p,const char *m){return __real_fopen(!strcmp(p,"/proc/mounts")?"/fixture-mounts":p,m);}
FILE *__wrap_fopen64(const char *p,const char *m){return __real_fopen64(!strcmp(p,"/proc/mounts")?"/fixture-mounts":p,m);}
extern long xw_host_getpid_oabi(void);
static struct xw_parent_trace_observer observer;
static unsigned owned_value=1,match_value=1,native_calls;
static int stage_status[6];
static struct xw_parent_trace_profile profile={.start=XW_TEST_TRACE_START,.bytes=XW_TEST_TRACE_BYTES,.digest=XW_TEST_TRACE_DIGEST,.callers=XW_TEST_TRACE_CALLERS};
static int owned(void *context){assert(context==&owned_value);return owned_value;}
static int matches(void *context,uintptr_t start,unsigned bytes,const unsigned char digest[32]){
 assert(context==&owned_value&&start==profile.start&&bytes==profile.bytes);
 if(!match_value)return -1;
 struct hb_sha256 hash;unsigned char actual[32];hb_sha256_init(&hash);hb_sha256_update(&hash,(const void *)start,bytes);hb_sha256_final(&hash,actual);
 return memcmp(actual,digest,32)?-1:0;
}
static int snapshot(void *context,uint32_t out[7]){assert(context==&owned_value);for(unsigned i=0;i<7;i++)out[i]=0xfeed0000u+i;return 0;}
int xw_host_pid_dispatch(uint32_t tag,uint32_t frame,uintptr_t caller,uint32_t list,uint32_t captured_r2,uintptr_t entry_sp){
 (void)list;
 for(unsigned i=0;i<5;i++)if(caller==profile.callers[i]&&tag==0x48425001u+i){
  assert((captured_r2&31u)==16u); /* Original user-mode CPSR captured by capsule. */
  int saved=errno;int rc=xw_parent_trace_observer_call(&observer,tag,frame,caller,entry_sp);assert(errno==saved);stage_status[i+1]=rc;return rc;
 }
 return (int)xw_host_getpid_oabi();
}
uint32_t parent_test_native_switch(uint32_t a,uint32_t b,uint32_t c,uint32_t d){assert(a==0x820f68&&b==0x30001&&!c&&d==1);native_calls++;return 0xa5a5;}
static const char path[]="/contents/HOMEBREW/data/diagnostics/parent-boundary.bin";
static void seed(void){
 unsigned char data[2048];FILE *a=fopen("/seed","rb"),*b=fopen(path,"wb");assert(a&&b);
 assert(fread(data,1,2048,a)==2048&&fwrite(data,1,2048,b)==2048&&!fclose(a)&&!fclose(b));
 memcpy(profile.header,data,32);
}
static void initialize(void){memset(&observer,0,sizeof observer);assert(!xw_parent_trace_observer_init(&observer,&profile,&owned_value,matches,owned,snapshot));}
static void exercise(void){
 typedef uint32_t (*function)(uint32_t,uint32_t,uint32_t,uint32_t);
 assert(((function)XW_TEST_TRACE_LAUNCH)(123,456,789,1011)==4);
 (void)((function)XW_TEST_TRACE_LOOKUP)(123,456,789,1011);
 assert(((function)XW_TEST_TRACE_RETURN)(0,456,789,1011)==0);
 assert(((function)XW_TEST_TRACE_SWITCH)(0x820f68,0x30001,0,1)==0xa5a5);
}
int main(void){
 assert(!mount("none","/contents","ramfs",0,0));
 const char *dirs[]={"/contents/HOMEBREW","/contents/HOMEBREW/data","/contents/HOMEBREW/data/diagnostics"};for(unsigned i=0;i<3;i++)assert(!mkdir(dirs[i],0700));
 seed();initialize();
 errno=123;
 assert(xw_parent_trace_observer_call(&observer,0x48425001u,1,0,0)==XW_TRACE_INVALID&&errno==123);
 match_value=0;assert(xw_parent_trace_observer_call(&observer,0x48425001u,0xdeadc008u,profile.callers[0],0xdeadc000u)==XW_TRACE_SKIPPED);match_value=1;
 exercise();assert(native_calls==1);for(unsigned i=1;i<=5;i++)assert(stage_status[i]==0);
 unsigned char raw[2048];FILE *f=fopen(path,"rb");assert(f&&fread(raw,1,2048,f)==2048&&fgetc(f)==EOF&&!fclose(f));
 printf("PARENT_OBSERVER_FILE_HEX ");for(unsigned i=0;i<2048;i++)printf("%02x",raw[i]);puts("");puts("PARENT_OBSERVER_FILE_END");
 assert(!xw_parent_trace_observer_destroy(&observer));
 seed();initialize();owned_value=0;exercise();assert(native_calls==2);
 for(unsigned i=1;i<=5;i++)assert(stage_status[i]==XW_TRACE_STORAGE);
 f=fopen(path,"rb");assert(f&&fread(raw,1,2048,f)==2048&&!fclose(f));for(unsigned i=32;i<2048;i++)assert(!raw[i]);
 assert(!xw_parent_trace_observer_destroy(&observer));assert(!unlink(path)&&!umount("/contents"));
 puts("PARENT_OBSERVER_PAIRED_PASS");fflush(stdout);return 0;
}
