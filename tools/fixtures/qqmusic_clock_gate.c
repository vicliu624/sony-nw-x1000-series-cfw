/* Public production composition: invalid date must precede Wi-Fi acquisition. */
#include "../../runtime/apps/qqmusic/qqmusic_program.h"
#include "qqmusic_profile.h"
#include <assert.h>
#include <string.h>
static volatile int stopped;
static unsigned ensures,cancels,releases,timezone_sets;
static int plausible;
static int clock_source(struct hb_tls_time *out){out->unix_seconds=plausible?1793100000ULL:1199881535ULL;out->days=719528u+(unsigned)(out->unix_seconds/86400);out->seconds=(unsigned)(out->unix_seconds%86400);return 0;}
static int ensure(void *p){(void)p;ensures++;return 1;}
static void cancel_platform(void *p){(void)p;cancels++;}
static void release(void *p){(void)p;releases++;}
static int timezone_choice(int minutes){assert(minutes==480);timezone_sets++;return 0;}
static int inspect(const struct qq_entry_config *entry,void *unused){
 struct qq_runtime_material material;struct qq_connection_diagnostic diagnostic;int rc;(void)unused;
 memset(&material,0,sizeof(material));rc=entry->operations->prepare(entry->operations->context,&material);
 if(!plausible){
  assert(rc<0&&ensures==0&&material.network_stage==0);
  entry->operations->diagnostic(entry->operations->context,&diagnostic);
  assert(diagnostic.step==QQ_STEP_CLOCK&&diagnostic.clock_year==2008&&diagnostic.clock_month==1&&diagnostic.clock_day==9);
  assert(!timezone_sets&&entry->operations->set_utc_offset(entry->operations->context,480)<0);
  entry->operations->cancel(entry->operations->context);
  assert(!entry->operations->set_utc_offset(entry->operations->context,480)&&timezone_sets==1);
 }else{
  assert(rc==1&&ensures==1&&material.network_stage==1);
  entry->operations->cancel(entry->operations->context);assert(cancels==1);
 }
 return 0;
}
int main(void){
 struct qq_program_config c;struct qq_storage_policy volume={"/dev/mock-user","vfat"};br_x509_trust_anchor anchor;
 memset(&c,0,sizeof(c));memset(&anchor,0,sizeof(anchor));c.volume=&volume;c.resources="synthetic";c.comm=QQ_PROFILE_COMM;c.guid=QQ_PROFILE_GUID;c.stop=&stopped;
 c.network.anchors=&anchor;c.network.anchor_count=1;c.network.timeout_ms=1000;c.network.time=clock_source;
 c.ensure_network=ensure;c.cancel_network=cancel_platform;c.release_network=release;c.set_utc_offset=timezone_choice;
 assert(!qq_program_run_bound(&c,inspect,0)&&releases==1&&!ensures&&!cancels);
 plausible=1;assert(!qq_program_run_bound(&c,inspect,0)&&releases==2&&ensures==1&&cancels==1);
 return 0;
}
