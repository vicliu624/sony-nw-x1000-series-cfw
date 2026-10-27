#include "tls_socket_step.h"
#include "socket_step.h"
static int error(int result){
 if(result==HB_SOCKET_RETRY)return HB_TLS_SOCKET_WAIT;
 if(result==HB_SOCKET_TIMEOUT)return HB_TLS_SOCKET_TIMEOUT;
 if(result==HB_SOCKET_CANCELLED)return HB_TLS_SOCKET_CANCELLED;
 return HB_TLS_SOCKET_IO;
}
int hb_tls_socket_step(br_ssl_engine_context *engine,int fd,unsigned timeout,volatile int *stop){
 if(!engine||fd<0||timeout>1000)return HB_TLS_SOCKET_INPUT;
 if(stop&&*stop)return HB_TLS_SOCKET_CANCELLED;
 unsigned state=br_ssl_engine_current_state(engine);
 if(state&BR_SSL_CLOSED)return br_ssl_engine_last_error(engine)?HB_TLS_SOCKET_PROTOCOL:HB_TLS_SOCKET_CLOSED;
 if(state&BR_SSL_RECVAPP)return HB_TLS_SOCKET_APPDATA;
 size_t bytes;unsigned char *buffer;int n;
 if(state&BR_SSL_SENDREC){
  buffer=br_ssl_engine_sendrec_buf(engine,&bytes);if(!buffer||!bytes)return HB_TLS_SOCKET_PROTOCOL;
  if(bytes>65536)bytes=65536;
  n=hb_socket_write_step(fd,buffer,(unsigned)bytes,timeout,stop);if(n<0)return error(n);
  if(!n)return HB_TLS_SOCKET_IO;
  br_ssl_engine_sendrec_ack(engine,(size_t)n);return HB_TLS_SOCKET_PROGRESS;
 }
 if(state&BR_SSL_RECVREC){
  buffer=br_ssl_engine_recvrec_buf(engine,&bytes);if(!buffer||!bytes)return HB_TLS_SOCKET_PROTOCOL;
  if(bytes>65536)bytes=65536;
  n=hb_socket_read_step(fd,buffer,(unsigned)bytes,timeout,stop);if(n<0)return error(n);
  if(!n)return HB_TLS_SOCKET_EOF;
  br_ssl_engine_recvrec_ack(engine,(size_t)n);return HB_TLS_SOCKET_PROGRESS;
 }
 return state&BR_SSL_SENDAPP?HB_TLS_SOCKET_APPDATA:HB_TLS_SOCKET_WAIT;
}
int hb_tls_socket_deadline_step(br_ssl_engine_context *engine,int fd,struct hb_transfer_deadline *deadline,unsigned cap,volatile int *stop){
 if(!engine||fd<0||!deadline||cap>1000)return HB_TLS_SOCKET_INPUT;
 if(stop&&*stop)return HB_TLS_SOCKET_CANCELLED;
 unsigned wait;int state=hb_transfer_deadline_remaining(deadline,&wait);
 if(state<0)return HB_TLS_SOCKET_CLOCK;
 if(!state)return HB_TLS_SOCKET_DEADLINE;
 if(wait>cap)wait=cap;
 int result=hb_tls_socket_step(engine,fd,wait,stop);
 if(stop&&*stop)return HB_TLS_SOCKET_CANCELLED;
 if(result<0&&result!=HB_TLS_SOCKET_TIMEOUT)return result;
 state=hb_transfer_deadline_remaining(deadline,&wait);
 if(state<0)return HB_TLS_SOCKET_CLOCK;
 return state?result:HB_TLS_SOCKET_DEADLINE;
}
