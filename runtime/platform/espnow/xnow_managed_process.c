#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_managed_process.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int managed_fcntl(int,int,...) __asm__("fcntl");
struct launch {struct xnow_managed_process *process;const struct hb_process_observer *original;int armed;};
static void observe(void *context,volatile int *stop){
 struct launch *l=context;
 if(!l->armed){if(xnow_handoff_parent_arm(&l->process->handoff)){l->process->fault=1;*stop=1;}l->armed=1;}
 if(l->original&&l->original->poll_stop)l->original->poll_stop(l->original->context,stop);
}
static int child(void *context){struct launch *l=context;if(l->original&&l->original->child_detach&&l->original->child_detach(l->original->context)<0)return -1;return xnow_handoff_child_inherit(&l->process->handoff)<0?-1:0;}
int xnow_managed_process_begin(struct xnow_managed_process *m,const char *directory,const char *executable,char *const environment[],volatile int *stop,const struct hb_process_observer *original,const uint8_t cookie[16]){
 if(!m||!directory||!executable||!stop||!cookie||*stop)return XNOW_ARGUMENT;
 char *env[131];unsigned count=0,bytes=0;
 if(environment)for(;environment[count];count++){
  if(count>=128||!strncmp(environment[count],"XNOW_HANDOFF_FD=",16)||!strncmp(environment[count],"XNOW_HANDOFF_COOKIE=",20))return XNOW_ARGUMENT;
  size_t n=strnlen(environment[count],4097);if(n>4096||n+1>16384-bytes)return XNOW_ARGUMENT;bytes+=(unsigned)n+1;env[count]=environment[count];
 }
 memset(m,0,sizeof(*m));m->app_status=-1;int r=xnow_handoff_create(&m->handoff,cookie);if(r)return r;
 char fd[64],token[64];int n=snprintf(fd,sizeof(fd),"XNOW_HANDOFF_FD=%d",m->handoff.writer);if(n<0||(unsigned)n>=sizeof(fd)){xnow_handoff_close(&m->handoff);return XNOW_ARGUMENT;}
 memcpy(token,"XNOW_HANDOFF_COOKIE=",20);for(unsigned i=0;i<16;i++){token[20+i*2]="0123456789abcdef"[cookie[i]>>4];token[21+i*2]="0123456789abcdef"[cookie[i]&15];}token[52]=0;
 env[count++]=fd;env[count++]=token;env[count]=0;
 struct launch l={m,original,0};struct hb_process_observer observer={&l,observe,child};m->started=1;
 m->app_status=hb_process_run_observed(directory,executable,env,stop,&observer);
 if(m->app_status<0){
  if(!l.armed){int closed=xnow_handoff_close(&m->handoff);m->started=0;return closed?XNOW_UNCERTAIN:XNOW_IO;}
  m->fault=1;return XNOW_UNCERTAIN;
 }
 if(!l.armed||m->fault){m->fault=1;return XNOW_UNCERTAIN;}
 return XNOW_PENDING;
}
int xnow_managed_process_poll(struct xnow_managed_process *m,struct xnow_handoff_result *out){
 if(!m||!out||!m->started)return XNOW_ARGUMENT;
 if(m->fault)return XNOW_UNCERTAIN;
 int r=xnow_handoff_poll(&m->handoff,out);if(!r)m->complete=1;else if(r!=XNOW_PENDING)m->fault=1;return r;
}
int xnow_managed_process_close(struct xnow_managed_process *m){
 if(!m||!m->started)return XNOW_ARGUMENT;
 if(!m->complete||m->fault)return XNOW_UNCERTAIN;
 int r=xnow_handoff_close(&m->handoff);if(!r)memset(m,0,sizeof(*m));return r;
}
int xnow_managed_process_inherited(int *writer,uint8_t cookie[16]){
 if(!writer||!cookie)return XNOW_ARGUMENT;
 const char *fd=getenv("XNOW_HANDOFF_FD"),*token=getenv("XNOW_HANDOFF_COOKIE");if(!fd||!token||!*fd||strlen(token)!=32)return XNOW_IDENTITY;
 unsigned value=0;for(unsigned i=0;fd[i];i++){if(fd[i]<'0'||fd[i]>'9'||value>104857)return XNOW_IDENTITY;value=value*10+(unsigned)(fd[i]-'0');}if(value<3||value>1048576)return XNOW_IDENTITY;
 uint8_t parsed[16];unsigned any=0;for(unsigned i=0;i<32;i++){unsigned char c=(unsigned char)token[i];unsigned v=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:16;if(v>15)return XNOW_IDENTITY;if(!(i&1))parsed[i/2]=(uint8_t)(v<<4);else parsed[i/2]|=(uint8_t)v;any|=v;}
 int flags=managed_fcntl((int)value,F_GETFL);struct stat st;if(!any||flags<0||(flags&O_ACCMODE)!=O_WRONLY||fstat((int)value,&st)||!S_ISFIFO(st.st_mode)||managed_fcntl((int)value,F_SETFD,FD_CLOEXEC)<0)return XNOW_IDENTITY;
 *writer=(int)value;memcpy(cookie,parsed,16);return 0;
}
