#define _DEFAULT_SOURCE
#include "../runtime/store/market_detail.h"
#include "../runtime/store/install_posix.h"
#include "../runtime/store/canvas.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static struct hb_package_download_plan plan;
static struct hb_bundle scratch;
static struct hb_market_local local;
static unsigned short pixels[240*432];static volatile int stop;
static unsigned events,presents;static int back,navigate;
static int next(void *ctx,unsigned char p[11]){
 (void)ctx;assert(events<12);unsigned x=back&&events>=2?20:180,y=404;
 if(navigate){unsigned step=events/2;x=step==0?170:step==1?40:step==2?200:20;y=step<2?116:step<4?352:404;}
 memset(p,0,11);p[1]=(events++%2)==0;unsigned rx=x*2929/240+1,ry=(431-y)*5281/432+1;
 p[2]=(unsigned char)(rx>>8);p[3]=(unsigned char)rx;p[4]=(unsigned char)(ry>>8);p[5]=(unsigned char)ry;return 1;
}
static int present(void *ctx){(void)ctx;presents++;return 0;}
static void versions(void){
 const char *order[]={"0.1.0","1.0.0-alpha","1.0.0-alpha.1","1.0.0-alpha.beta","1.0.0-beta","1.0.0-beta.2","1.0.0-beta.11","1.0.0-rc.1","1.0.0","1.0.1","1.9.0","1.10.0","2.0.0"};
 for(unsigned i=0;i<sizeof order/sizeof order[0];i++)for(unsigned j=0;j<sizeof order/sizeof order[0];j++){int value;assert(!hb_semver_compare(order[i],order[j],&value));assert(value==(i==j?0:i<j?-1:1));}
 const char *invalid[]={"1","1.2","01.2.3","1.02.3","1.2.03","1.2.3-01","1.2.3-","1.2.3+","1.2.3-a..b","1.2.3+a..b","v1.2.3","1.2.3/4"};
 for(unsigned i=0;i<sizeof invalid/sizeof invalid[0];i++){int value;assert(hb_semver_compare(invalid[i],"1.0.0",&value));}
 int value;assert(!hb_semver_compare("1.2.3+abc","1.2.3+xyz",&value)&&!value);
 assert(!hb_semver_compare("999999999999999999999999.0.0","999999999999999999999998.0.0",&value)&&value==1);
 struct hb_remote_entry e={0};strcpy(e.id,"hello");strcpy(e.version,"1.0.0");
 struct hb_store_canvas c;struct hb_store_painter p;assert(!hb_store_canvas_init(&c,pixels,240*432,&p));struct hb_store_ui_io io={0,next,present};
 for(int status=0;status<7;status++){
  local.status=(enum hb_market_status)status;events=presents=0;back=status>=HB_MARKET_CONFLICT;
  assert(hb_market_detail_run(&e,&local,&p,&io)==(back?0:1));
  assert(events==(status>=HB_MARKET_DOWNGRADE?4u:2u));
 }
 memset(e.description,'a',600);e.description[600]=0;local.status=HB_MARKET_NEW;
 events=presents=0;navigate=1;assert(!hb_market_detail_run(&e,&local,&p,&io)&&events==10&&presents>=5);navigate=0;
 puts("SemVer precedence and details confirmations passed");
}
int main(int argc,char **argv){
 versions();if(argc==1)return 0;assert(argc==5);
 assert(!hb_bundle_check(argv[1],"hello",&stop,&plan.bundle));assert(!hb_bundle_identity(&plan.bundle,plan.identity));plan.valid=1;
 assert(!hb_market_inspect(argv[2],&plan,&stop,&scratch,&local));int expected=atoi(argv[3]);assert((int)local.status==expected);
 if(strcmp(argv[4],"inspect")){
  int presence=local.present;unsigned char identity[32];memcpy(identity,local.identity,32);
  if(!strcmp(argv[4],"stale")){presence=1;memset(identity,0,32);}
  if(!strcmp(argv[4],"appeared"))presence=0;
  int result=hb_store_install_local_guarded(argv[2],argv[1],"hello",4096,&stop,plan.identity,presence,identity);
  assert(result==(!strcmp(argv[4],"stale")||!strcmp(argv[4],"appeared")?HB_INSTALL_CHANGED:0));
 }
 printf("STATUS %d\n",expected);return 0;
}
