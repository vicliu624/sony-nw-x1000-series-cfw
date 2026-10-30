/* Only the radio/manager are modeled. Production owner/gate/pipe loop is real. */
#include "../../runtime/apps/glass-marble/platform.h"
#include "../../runtime/apps/glass-marble/marble.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static unsigned ticks;
int gm_storage_guard(void *p){(void)p;return 0;}
void gm_control_options(struct xnow_full_control_options *o,struct xnow_owner_gate *gate){memset(o,0,sizeof *o);o->context=gate;}
int xnow_full_control_init(struct xnow_full_control *c,const struct xnow_full_control_options *o){memset(c,0,sizeof *c);c->options=*o;c->initialized=1;c->manager.owner=(int)getpid();c->session.phase=XNOW_SESSION_STARTING;return 0;}
void xnow_full_control_stop(struct xnow_full_control *c){c->stop_requested=1;}
int xnow_full_control_step(struct xnow_full_control *c){
 ticks++;if(c->stop_requested){c->session.phase=ticks<8?XNOW_SESSION_STOPPING:XNOW_SESSION_DONE;c->manager.held=c->session.phase!=XNOW_SESSION_DONE;}
 else if(ticks>1){c->session.phase=XNOW_SESSION_READY;c->manager.held=1;}
 return c->session.phase;
}
int xnow_full_control_finished(const struct xnow_full_control *c){return c->session.phase==XNOW_SESSION_DONE;}
struct xnow_endpoint *xnow_full_control_endpoint(struct xnow_full_control *c){return &c->endpoint;}
int xnow_endpoint_receive(struct xnow_endpoint *e,void *p,size_t size,struct xnow_full_received *info){
 (void)e;if(ticks>3&&getenv("GM_TEST_IO_FAILURE"))return XNOW_IO;
 if(ticks>3)return XNOW_AGAIN;
 struct gm_layout l={40,40,37,66.6f,8,-13.3f};struct gm_world w;gm_init(&w,&l,123);w.sequence=ticks;
 int n=gm_encode(&w,p,size);memset(info,0,sizeof *info);info->source[0]=2;info->source[5]=1;info->info.payload_bytes=(size_t)n;return 0;
}
