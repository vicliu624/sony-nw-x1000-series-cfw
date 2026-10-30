/* Host-only foreground/client/owner integration; radio effects are substituted. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <sys/stat.h>
#include "../../runtime/apps/espnow-chat/chat_ipc.h"
#include "../../runtime/platform/espnow/xnow_launcher_bridge.h"
#ifdef CHAT_UI_FIXTURE
static void mark(const char *path,long value){FILE *f=fopen(path,"w");assert(f);assert(fprintf(f,"%ld\n",value)>0);assert(!fclose(f));}
int __real_lstat(const char *,struct stat *);
int __wrap_lstat(const char *path,struct stat *s){
 if(!strcmp(path,"/contents"))return __real_lstat(getenv("CHAT_FIXTURE_VOLUME"),s);
 int result=__real_lstat(path,s);if(!result&&!strcmp(path,"/"))s->st_dev^=1;return result;
}
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--no-cap")){struct chat_client c;assert(chat_client_start(&c)==-2&&!c.pid&&c.command==-1&&c.events==-1);puts("unmanaged RF startup refused before owner fork");return 0;}
 assert(argc==1);
 struct chat_client c;assert(!chat_client_start(&c));mark("ui-pid",getpid());mark("worker-pid",c.pid);
 for(unsigned i=0;i<3000;i++){struct chat_event e;int r=chat_client_event(&c,&e);assert(r>=0);if(r==1&&e.kind==CHAT_STATE&&e.state==CHAT_READY){assert(signal(SIGTERM,SIG_IGN)!=SIG_ERR);mark("ready",1);for(;;)pause();}usleep(1000);}
 return 75;
}
#else
struct observer {char ready[1024];};
static void observe(void *context,volatile int *stop){struct observer *o=context;if(!access(o->ready,F_OK))*stop=1;}
int main(int argc,char **argv){
 if(argc!=3)return 64;
 char image[1024],mode[128],volume[1200];struct observer o;
 assert(snprintf(image,sizeof image,"%s/app",argv[1])<(int)sizeof image);
 assert(snprintf(o.ready,sizeof o.ready,"%s/ready",argv[1])<(int)sizeof o.ready);
 assert(snprintf(mode,sizeof mode,"CHAT_TEST_RESTORE_MODE=%s",argv[2])<(int)sizeof mode);
 assert(snprintf(volume,sizeof volume,"CHAT_FIXTURE_VOLUME=%s",argv[1])<(int)sizeof volume);
 char *env[]={mode,volume,0};volatile int stop=0;struct hb_process_observer callback={&o,observe,0};
 int status=xnow_launcher_run_managed(argv[1],image,env,&stop,&callback);
 assert(!access("/proc/self",F_OK));
 printf("managed_chat_status=%d\n",status);return 0;
}
#endif
