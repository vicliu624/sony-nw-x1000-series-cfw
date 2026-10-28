#include "qqmusic_preview_runtime.h"
#include "qqmusic_preview_service.h"
#include "qqmusic_preview_device_posix.h"
#include "qqmusic_preview_owners.h"
#include "../../store/deadline.h"
#include <string.h>
struct owner {
 struct qq_preview_service service;struct qq_preview_device_posix adapter;
 struct qq_workspace *workspace;volatile int *stop;uint64_t now;
 unsigned reaped,stopped;
 int (*ui)(void *,const struct qq_preview_client_channels *,volatile int *);void *ui_context;
};
static int ui_entry(void *context,const struct qq_preview_client_channels *c,volatile int *stop){struct owner *o=context;return o->ui(o->ui_context,c,stop);}
static int clock_read(void *context,uint64_t *now){struct owner *o=context;unsigned long long value;if(hb_monotonic_millis(&value))return -1;o->now=value;*now=value;return 0;}
static int pump(void *context,const struct qq_preview_server_channels *c,unsigned reaped,unsigned stop){struct owner *o=context;o->reaped=reaped;o->stopped=stop;return qq_preview_service_pump(&o->service,c,reaped,stop,o->now);}
static int quiet(void *context){
 struct owner *o=context;struct qq_preview_service *s=&o->service;
 if(!o->reaped&&!o->stopped)return 0;
 if(s->session.phase!=QQ_PREVIEW_IDLE&&s->session.phase!=QQ_PREVIEW_DONE)return 0;
 return qq_preview_guard_quiet(o->workspace->lock,!o->reaped?s->ui_pid:0,!o->reaped?s->ui_birth:0);
}
int qq_preview_runtime_run(const struct qq_preview_handoff_policy *policy,struct qq_workspace *workspace,volatile int *stop,
 int (*ui)(void *,const struct qq_preview_client_channels *,volatile int *),void *context){
 struct owner o;struct qq_preview_device_io io;struct qq_preview_supervisor_config supervisor;
 if(!policy||!workspace||workspace->lock<0||!stop||*stop||!ui)return -1;
 memset(&o,0,sizeof(o));o.workspace=workspace;o.stop=stop;o.ui=ui;o.ui_context=context;
 o.adapter.policy=policy;o.adapter.workspace=workspace;o.adapter.stop=stop;o.adapter.role=0;
 o.adapter.producer_context=&o.service;o.adapter.producer_exited=qq_preview_service_producer_exited;
 if(qq_preview_device_posix_io(&o.adapter,&io)||qq_preview_service_init(&o.service,&io))return -1;
 memset(&supervisor,0,sizeof(supervisor));supervisor.context=&o;supervisor.stop=stop;supervisor.verified_guard_fd=workspace->lock;
 supervisor.ui=ui_entry;supervisor.pump=pump;supervisor.descendants_quiet=quiet;supervisor.clock=clock_read;supervisor.ui_grace_ms=3000;
 return qq_preview_supervisor_run(&supervisor);
}
