#include "native_rf_worker.h"
#include "native_permission.h"
#include <pthread.h>
#include <stdlib.h>
#include <unistd.h>
typedef char stock_key_word[(sizeof(pthread_key_t)==4&&sizeof(pthread_once_t)==4)?1:-1];
static pthread_once_t once=PTHREAD_ONCE_INIT;
static pthread_key_t key;
static int initialized=-1;
static void destroy(void *context){
 struct xw_native_wireless_permission *permission=context;
 if(permission){(void)xw_native_permission_close(permission);free(permission);}
}
static void initialize(void){initialized=pthread_key_create(&key,destroy);}
static int ready(void){return !pthread_once(&once,initialize)&&!initialized;}
__attribute__((weak)) int xw_native_rf_refresh_offer(void){return XW_MODE_PENDING;}
__attribute__((weak)) int xw_native_rf_wait_offer(unsigned timeout){(void)timeout;return XW_MODE_PENDING;}
__attribute__((weak)) int xw_native_rf_gui_cleanup_permission(void){return XW_MODE_DENIED;}
int xw_native_rf_worker_bind(int fd,int gui_pid,unsigned long gui_thread,const struct xw_wireless_lease *lease){
 if(!ready())return XW_MODE_FAULT;
 if(pthread_getspecific(key))return XW_MODE_BUSY;
 struct xw_native_wireless_permission *p=calloc(1,sizeof *p);if(!p)return XW_MODE_FAULT;
 int rc=xw_native_permission_open(p,fd,gui_pid,gui_thread,lease);
 if(rc){free(p);return rc;}
 if(pthread_setspecific(key,p)){destroy(p);return XW_MODE_FAULT;}
 return 0;
}
static int check(void){
 if(!ready())return XW_MODE_FAULT;
 struct xw_native_wireless_permission *p=pthread_getspecific(key);
 return p?xw_native_permission_check(p,200):XW_MODE_DENIED;
}
static int validate_view(struct xw_native_wireless_permission *p){
 struct xw_mode_reply view;int rc=xw_native_permission_snapshot(p,200,&view);if(rc)return rc;
 if(view.phase==XW_MODE_DRAINING||view.phase==XW_MODE_FAILED)return XW_NATIVE_RF_CLEANUP_VIEW;
 return xw_mode_reply_data_allowed(&view);
}
int xw_native_rf_worker_observe(struct xw_mode_reply *out){
 if(!ready())return XW_MODE_FAULT;
 struct xw_native_wireless_permission *p=pthread_getspecific(key);
 return p?xw_native_permission_snapshot(p,200,out):XW_MODE_DENIED;
}
int xw_native_rf_worker_retirement(struct xw_native_retirement *out){
 if(!out||!ready())return XW_MODE_INVALID;
 struct xw_native_wireless_permission *p=pthread_getspecific(key);
 if(!p||!p->sealed)return XW_MODE_DENIED;
 if(p->client.pid!=(int)getpid()||p->client.thread!=(unsigned long)pthread_self())return XW_MODE_WRONG_OWNER;
 *out=p->retirement;return 0;
}
int xw_native_rf_worker_seal(const struct xw_native_retirement *r){
 if(!r||!ready())return XW_MODE_INVALID;struct xw_native_wireless_permission *p=pthread_getspecific(key);
 if(!p||p->client.pid!=(int)getpid()||p->client.thread!=(unsigned long)pthread_self())return XW_MODE_WRONG_OWNER;
 if(r->lease.generation!=p->lease.generation||r->lease.serial!=p->lease.serial||r->lease.consumer!=p->lease.consumer||r->lease.mode!=p->lease.mode||
    r->native_result||r->public_state!=2||r->modules_clear!=1||r->sealed!=1||(r->phase!=XW_MODE_DRAINING&&r->phase!=XW_MODE_FAILED))return XW_MODE_DENIED;
 p->sealed=1;p->retirement_sent=0;p->retirement=*r;
 if(p->client.bound)(void)xw_mode_client_close(&p->client);return 0;
}
int xw_native_rf_worker_notice_pending(void){
 if(!ready())return 0;struct xw_native_wireless_permission *p=pthread_getspecific(key);
 return p&&p->sealed&&!p->retirement_sent&&p->client.pid==(int)getpid()&&p->client.thread==(unsigned long)pthread_self();
}
void xw_native_rf_worker_notice_sent(const struct xw_wireless_lease *lease){
 if(!lease||!ready())return;struct xw_native_wireless_permission *p=pthread_getspecific(key);
 if(p&&p->sealed&&p->client.pid==(int)getpid()&&p->client.thread==(unsigned long)pthread_self()&&
    lease->generation==p->lease.generation&&lease->serial==p->lease.serial&&lease->consumer==p->lease.consumer&&lease->mode==p->lease.mode)p->retirement_sent=1;
}
int xw_native_rf_cleanup_permission(void){
 int offered=xw_native_rf_refresh_offer();
 if(offered!=0&&offered!=XW_MODE_PENDING&&offered!=XW_NATIVE_RF_CLEANUP_VIEW)return offered;
 if(!ready())return XW_MODE_FAULT;struct xw_native_wireless_permission *p=pthread_getspecific(key);
 if(!p)return xw_native_rf_gui_cleanup_permission();
 if(p->sealed)return 2;
 struct xw_mode_reply view;return xw_native_permission_snapshot(p,200,&view);
}
int xw_native_rf_permission(void){
 int offered=xw_native_rf_refresh_offer();
 if(!offered)return 0; /* Receipt already validated a fresh exact-lease query. */
 if(offered!=XW_MODE_PENDING)return offered;
 if(!ready())return XW_MODE_FAULT;
 if(!pthread_getspecific(key)){
  offered=xw_native_rf_wait_offer(200);
  return offered==XW_MODE_PENDING?XW_MODE_DENIED:offered;
 }
 return check();
}
int xw_native_rf_worker_replace(int fd,int gui_pid,unsigned long gui_thread,const struct xw_wireless_lease *lease){
 if(!ready())return XW_MODE_FAULT;
 struct xw_native_wireless_permission *old=pthread_getspecific(key);
 if(!old||!lease)return XW_MODE_INVALID;
 if(lease->generation!=old->lease.generation||lease->consumer!=old->lease.consumer||
    lease->mode!=old->lease.mode||lease->serial<=old->lease.serial||
    gui_pid!=old->gui_pid||gui_thread!=old->gui_thread)return XW_MODE_STALE;
 struct xw_native_wireless_permission *next=calloc(1,sizeof *next);if(!next)return XW_MODE_FAULT;
 int rc=xw_native_permission_open(next,fd,gui_pid,gui_thread,lease);
 if(rc){free(next);return rc;}
 rc=validate_view(next);
 if(rc!=0&&rc!=XW_NATIVE_RF_CLEANUP_VIEW){destroy(next);return rc;}
 if(pthread_setspecific(key,next)){destroy(next);return XW_MODE_FAULT;}
 destroy(old);return rc;
}
int xw_native_rf_worker_close(void){
 if(!ready())return XW_MODE_FAULT;
 struct xw_native_wireless_permission *p=pthread_getspecific(key);if(!p)return 0;
 if(pthread_setspecific(key,0))return XW_MODE_FAULT;
 int rc=xw_native_permission_close(p);free(p);return rc;
}
int xw_native_rf_worker_offer(int fd,int gui_pid,unsigned long gui_thread,const struct xw_wireless_lease *lease){
 if(!ready())return XW_MODE_FAULT;
 if(pthread_getspecific(key))return xw_native_rf_worker_replace(fd,gui_pid,gui_thread,lease);
 int rc=xw_native_rf_worker_bind(fd,gui_pid,gui_thread,lease);if(rc)return rc;
 struct xw_native_wireless_permission *p=pthread_getspecific(key);rc=validate_view(p);
 if(rc!=0&&rc!=XW_NATIVE_RF_CLEANUP_VIEW)(void)xw_native_rf_worker_close();return rc;
}
