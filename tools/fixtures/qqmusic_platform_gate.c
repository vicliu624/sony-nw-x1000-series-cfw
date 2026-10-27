/* Correct seam: a request must survive waiting, and never send after cancel. */
#include "../../runtime/apps/qqmusic/qqmusic_program.c"
#include <assert.h>
static unsigned ensure_calls,sent,polls,cancelled,transport_cancelled;static int ready,deny,stop_in_ensure;static volatile int stopped;
static struct qq_cookie_jar jar;
void qq_secret_clear(void *p,size_t n){memset(p,0,n);}
const struct qq_runtime_ops *qq_network_operations(struct qq_network *n){return &n->operations;}
void qq_network_cancel(struct qq_network *n){(void)n;transport_cancelled++;}
static int ensure(void *p){(void)p;ensure_calls++;if(stop_in_ensure)stopped=1;return deny?-1:ready?0:1;}
static void cancel_platform(void *p){(void)p;cancelled++;}
static int send_request(void *p,const struct qq_request *r,struct qq_cookie_jar *cookies,uint64_t ticket){(void)p;assert(!strcmp(r->body,"synthetic-owned-buffer")&&cookies==&jar&&ticket==123);sent++;return 0;}
static int poll_request(void *p,struct qq_response **out){(void)p;(void)out;polls++;return 0;}
static int empty(const void *p,size_t n){const unsigned char *b=p;size_t i;for(i=0;i<n;i++)if(b[i])return 0;return 1;}
int main(void){
 struct program *p=calloc(1,sizeof(*p));struct qq_program_config config;struct qq_request request;struct qq_response *response=0;
 assert(p);memset(&config,0,sizeof(config));config.stop=&stopped;config.ensure_network=ensure;config.cancel_network=cancel_platform;p->config=&config;p->network.operations.start=send_request;p->network.operations.poll=poll_request;
 memset(&request,0,sizeof(request));strcpy(request.body,"synthetic-owned-buffer");assert(!start(p,&request,&jar,123)&&p->deferred_request&&!sent);memset(&request,0,sizeof(request));
 assert(!poll_network(p,&response)&&!sent&&!polls);ready=1;assert(!poll_network(p,&response)&&sent==1&&polls==1&&!p->deferred_request&&empty(&p->platform_request,sizeof(p->platform_request)));
 cancel(p);cancelled=transport_cancelled=0;
 ready=0;strcpy(request.body,"synthetic-owned-buffer");assert(!start(p,&request,&jar,123));cancel(p);assert(cancelled==1&&transport_cancelled==1&&empty(&p->platform_request,sizeof(p->platform_request))&&!p->platform_cookies);{unsigned before=polls;response=(void *)1;assert(!poll_network(p,&response)&&!response&&polls==before&&sent==1);}
 assert(!start(p,&request,&jar,123));deny=1;assert(poll_network(p,&response)<0&&sent==1&&empty(&p->platform_request,sizeof(p->platform_request))&&!p->deferred_request);
 deny=0;assert(!start(p,&request,&jar,123));ready=1;stop_in_ensure=1;assert(poll_network(p,&response)<0&&sent==1&&!p->request_active&&!p->deferred_request&&empty(&p->platform_request,sizeof(p->platform_request)));
 stopped=0;assert(start(p,&request,&jar,123)<0&&sent==1&&!p->request_active);
 assert(ensure_calls>=5);free(p);return 0;
}
