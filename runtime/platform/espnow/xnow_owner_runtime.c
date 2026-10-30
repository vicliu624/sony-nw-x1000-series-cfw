#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_owner_runtime.h"
#include "xnow_handoff.h"
#include "xnow_security.h"
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int runtime_fcntl(int,int,...) __asm__("fcntl");
static void erase(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
static int writer_valid(struct xnow_owner_runtime *r){struct stat st;int flags=runtime_fcntl(r->writer,F_GETFL);return flags>=0&&(flags&O_ACCMODE)==O_WRONLY&&!fstat(r->writer,&st)&&S_ISFIFO(st.st_mode)&&(uint64_t)st.st_dev==r->writer_device&&(uint64_t)st.st_ino==r->writer_inode;}
static void stop(struct xnow_owner_runtime *r,int failure){if(failure&&!r->application_failure)r->application_failure=failure;r->commands->stopped=1;xnow_full_control_stop(r->control);}
int xnow_owner_runtime_init(struct xnow_owner_runtime *r,struct xnow_full_control *c,struct xnow_owner_gate *g,struct xnow_owner_stream *s,struct xnow_owner_commands *commands,int writer,const uint8_t cookie[16],void *context,int (*prepare)(void *,struct xnow_endpoint *,const uint8_t[6]),int (*close_data)(void *)){
 if(!r||!c||!g||!s||!commands||!cookie||!close_data||writer<3||writer==s->input||writer==s->output||writer==g->command_fd||writer==g->socket_fd||c->session.phase!=XNOW_SESSION_STARTING||!c->initialized||c->manager.held||c->job.pid||c->endpoint_ready||c->stop_requested||s->commands!=commands||s->fault||s->used||s->output_bytes||s->pid!=(int)getpid()||g->pid!=(int)getpid()||s->device[0]!=g->command_device||s->inode[0]!=g->command_inode||c->options.context!=g||c->options.lease_valid!=xnow_owner_gate_radio_valid||(c->options.encrypted_limit&&!prepare)||!xnow_owner_gate_radio_valid(g))return XNOW_ARGUMENT;
 unsigned any=0;for(unsigned i=0;i<16;i++)any|=cookie[i];if(!any)return XNOW_ARGUMENT;
 memset(r,0,sizeof *r);r->control=c;r->gate=g;r->stream=s;r->commands=commands;r->writer=writer;r->pid=(int)getpid();r->context=context;r->prepare=prepare;r->close_data=close_data;memcpy(r->cookie,cookie,16);
 struct stat st;int flags=runtime_fcntl(writer,F_GETFL);
 if(flags<0||(flags&O_ACCMODE)!=O_WRONLY||fstat(writer,&st)||!S_ISFIFO(st.st_mode)||
    ((uint64_t)st.st_dev==s->device[0]&&(uint64_t)st.st_ino==s->inode[0])||
    ((uint64_t)st.st_dev==s->device[1]&&(uint64_t)st.st_ino==s->inode[1])||
    runtime_fcntl(writer,F_SETFD,FD_CLOEXEC)<0){r->fault=1;return XNOW_IDENTITY;}
 r->writer_device=(uint64_t)st.st_dev;r->writer_inode=(uint64_t)st.st_ino;
 return xnow_owner_commands_control(commands,c);
}
static int finish(struct xnow_owner_runtime *r){
 if(!r->cleaned){
  if(r->close_data(r->context)){r->fault=1;return XNOW_UNCERTAIN;}
  r->cleaned=1;
 }
 if(!r->released){
  if(xnow_owner_stream_close(r->stream)||xnow_owner_gate_release(r->gate,r->control)){r->fault=1;return XNOW_UNCERTAIN;}
  r->released=1;
 }
 if(!writer_valid(r)){r->fault=1;return XNOW_UNCERTAIN;}
 int result=xnow_handoff_notify(r->writer,r->cookie,r->control);
 if(result==XNOW_PENDING)return result;
 if(result||close(r->writer)){r->fault=1;return XNOW_UNCERTAIN;}
 r->writer=-1;erase(r->cookie,sizeof r->cookie);erase(r->receive,sizeof r->receive);r->done=1;return 0;
}
int xnow_owner_runtime_step(struct xnow_owner_runtime *r){
 if(!r||!r->control||r->pid!=(int)getpid())return XNOW_ARGUMENT;
 if(r->done)return 0;
 if(r->fault)return XNOW_UNCERTAIN;
 int phase=xnow_owner_gate_step(r->gate,r->control);
 if(phase<0)return phase;
 if(xnow_full_control_finished(r->control))return finish(r);
 if(phase!=XNOW_SESSION_READY)return XNOW_PENDING;
 if(r->control->stop_requested)return XNOW_PENDING;
 if(xnow_owner_gate_storage_guard(r->gate)){stop(r,XNOW_IDENTITY);return XNOW_PENDING;}
 struct xnow_endpoint *endpoint=xnow_full_control_endpoint(r->control);
 if(!endpoint){stop(r,XNOW_IDENTITY);return XNOW_PENDING;}
 if(!r->prepared){
  if(r->prepare){int result=r->prepare(r->context,endpoint,r->control->local_mac);if(result){stop(r,result);return XNOW_PENDING;}}
  if(r->control->options.encrypted_limit&&(!endpoint->crypto.context||!endpoint->crypto.prepare||!endpoint->crypto.send||!endpoint->crypto.receive||!endpoint->crypto.forget||!endpoint->crypto.clear)){stop(r,XNOW_ENDPOINT_CRYPTO_UNAVAILABLE);return XNOW_PENDING;}
  r->prepared=1;
 }
 if(xnow_owner_stream_step(r->stream)<0){stop(r,XNOW_IO);return XNOW_PENDING;}
 if(!xnow_owner_stream_writable(r->stream))return XNOW_PENDING;
 struct xnow_owner_completion complete;int result=xnow_owner_commands_poll(r->commands,&complete);
 if(!result){if(xnow_owner_stream_completion(r->stream,&complete)){stop(r,XNOW_UNCERTAIN);}return XNOW_PENDING;}
 if(result<0){stop(r,result);return XNOW_PENDING;}
 struct xnow_full_received received;result=xnow_owner_commands_receive(r->commands,r->receive,sizeof r->receive,&received);
 if(!result){if(xnow_owner_stream_receive(r->stream,r->receive,received.info.payload_bytes,&received))stop(r,XNOW_UNCERTAIN);}
 else if(result==XNOW_SECURITY_AUTH||result==XNOW_SECURITY_REPLAY||result==XNOW_SECURITY_FORMAT||result==XNOW_RADIO_REJECTED||result==XNOW_ENDPOINT_CRYPTO_UNAVAILABLE)r->dropped++;
 else if(result<0)stop(r,result);
 erase(r->receive,sizeof r->receive);return XNOW_PENDING;
}
