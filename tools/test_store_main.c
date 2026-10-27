#define HB_BUILD_VERSION "test"
#define main store_entry
#include "../runtime/store/main.c"
#undef main
#include <assert.h>
static int factories,runs;
int hb_store_native_platform(struct hb_store_platform *p){(void)p;factories++;return 0;}
int hb_store_app_run(const char *apps,const char *packages,unsigned long long reserve,const struct hb_store_platform *p){
 (void)p;assert(!strcmp(apps,"/contents/HOMEBREW/apps")&&!strcmp(packages,"/contents/HOMEBREW/packages")&&reserve==1048576);runs++;return 0;
}
int main(void){
 char *outside[]={"/tmp/app",0};char *deployed[]={"/contents/HOMEBREW/apps/store/app",0};
 char *explicit_native[]={"/tmp/app","--native",0};char *wrong[]={"/tmp/app","--native","extra",0};
 assert(store_entry(1,outside,0)==64&&!factories&&!runs);
 assert(store_entry(3,wrong,0)==64&&!factories&&!runs);
 assert(!store_entry(1,deployed,0)&&factories==1&&runs==1);
 assert(!store_entry(2,explicit_native,0)&&factories==2&&runs==2);
 return 0;
}
