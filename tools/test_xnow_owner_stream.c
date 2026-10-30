#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#define XNOW_OWNER_COMMAND_TEST_MAIN command_checks
#include "test_xnow_owner_commands.c"
#include "../runtime/platform/espnow/xnow_owner_stream.h"
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
extern int fixture_fcntl(int,int,...) __asm__("fcntl");
#define fcntl fixture_fcntl
static size_t read_limit=3,write_limit=5;
extern ssize_t __real_read(int,void *,size_t);
extern ssize_t __real_write(int,const void *,size_t);
ssize_t __wrap_read(int fd,void *p,size_t n){return __real_read(fd,p,n>read_limit?read_limit:n);}
ssize_t __wrap_write(int fd,const void *p,size_t n){return __real_write(fd,p,n>write_limit?write_limit:n);}
static void nonblock(int fd){assert(fcntl(fd,F_SETFL,fcntl(fd,F_GETFL)|O_NONBLOCK)>=0);}
static void pipes(int in[2],int out[2]){assert(!pipe(in)&&!pipe(out));for(unsigned i=0;i<2;i++){nonblock(in[i]);nonblock(out[i]);}}
static void write_all(int fd,const void *p,size_t n){while(n){ssize_t k=write(fd,p,n);assert(k>0);p=(const uint8_t *)p+k;n-=(size_t)k;}}
static size_t drain(int fd,uint8_t *p,size_t n){size_t used=0;while(used<n){ssize_t k=read(fd,p+used,n-used);if(k<0&&(errno==EAGAIN||errno==EINTR))break;assert(k>0);used+=(size_t)k;}return used;}
static void exchange(struct xnow_owner_stream *s,int output,uint8_t *reply,size_t n){size_t used=0;for(unsigned i=0;used<n;i++){assert(i<3000&&xnow_owner_stream_step(s)>=0);used+=drain(output,reply+used,n-used);}assert(!s->output_bytes);}
static void setup_stream(struct xnow_owner_stream *s,struct xnow_owner_commands *c,int in[2],int out[2]){pipes(in,out);assert(!xnow_owner_commands_init(c,0,ready,stop));assert(!xnow_owner_stream_open(s,c,in[0],out[1]));assert(fcntl(s->input,F_GETFD)&FD_CLOEXEC);assert(fcntl(s->output,F_GETFD)&FD_CLOEXEC);}
static void cleanup(struct xnow_owner_stream *s,int in[2],int out[2]){assert(!xnow_owner_stream_close(s));for(unsigned i=0;i<2;i++){if(in[i]>=0)close(in[i]);if(out[i]>=0)close(out[i]);}}
int main(void){
 assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);assert(!command_checks());reset();available=1;stops=0;
 struct xnow_full full;assert(!xnow_full_open(&full,&io,&layout));assert(!xnow_endpoint_init(&endpoint,&full,6,17,0,random4));
 struct xnow_owner_stream stream;struct xnow_owner_commands c;int in[2],out[2];setup_stream(&stream,&c,in,out);
 uint8_t cmd[XNOW_OWNER_COMMAND_MAX],reply[32+1470],address[6]={2,1,2,3,4,5};size_t n=request(cmd,XNOW_OWNER_ADD,71,26);memcpy(cmd+16,address,6);cmd[22]=6;cmd[23]=2;
 /* Every real pipe read <=3 and write <=5 bytes, exercising partial framing. */
 uint8_t junk[1024]={0};size_t filled=0;
 for(;;){ssize_t k=__real_write(out[1],junk,sizeof junk);if(k<0){assert(errno==EAGAIN);break;}assert(k>0);filled+=(size_t)k;}
 write_all(in[1],cmd,n);for(unsigned i=0;!stream.output_bytes;i++){assert(i<50&&xnow_owner_stream_step(&stream)>=0);}
 write_all(in[1],cmd,n);for(unsigned i=0;i<20;i++)assert(xnow_owner_stream_step(&stream)==XNOW_PENDING&&stream.output_bytes==16&&stream.written==0);
 unsigned pending_count,pending_encrypted;xnow_peer_count(&endpoint.peers,&pending_count,&pending_encrypted);assert(pending_count==1);
 while(filled){size_t k=drain(out[0],junk,filled<sizeof junk?filled:sizeof junk);assert(k);filled-=k;}
 exchange(&stream,out[0],reply,16);assert(!memcmp(reply,"XNA1",4)&&!result(reply));
 exchange(&stream,out[0],reply,16);assert(result(reply)==XNOW_PEER_EXISTS);
 for(unsigned i=0;i<sizeof stream.request;i++)assert(!stream.request[i]);
 n=request(cmd,XNOW_OWNER_SEND,72,1476);memcpy(cmd+16,address,6);for(unsigned i=0;i<1470;i++)cmd[22+i]=(uint8_t)i;
 write_all(in[1],cmd,n);exchange(&stream,out[0],reply,16);assert(!result(reply));
 struct xnow_owner_completion completed;assert(xnow_owner_commands_poll(&c,&completed)==XNOW_PENDING);done(0);assert(!xnow_owner_commands_poll(&c,&completed));assert(!xnow_owner_stream_completion(&stream,&completed));
 assert(xnow_owner_stream_completion(&stream,&completed)==XNOW_PENDING);exchange(&stream,out[0],reply,32);assert(!memcmp(reply,"XNT1",4)&&reply[8]==72);assert(xnow_owner_commands_poll(&c,&completed)==XNOW_AGAIN);
 uint8_t data[1470],received_data[1470];for(unsigned i=0;i<1470;i++)data[i]=(uint8_t)(i*3);receive(data,1470);struct xnow_full_received metadata;assert(!xnow_owner_commands_receive(&c,received_data,sizeof received_data,&metadata));assert(!xnow_owner_stream_receive(&stream,received_data,1470,&metadata));
 assert(xnow_owner_stream_receive(&stream,data,1470,&metadata)==XNOW_PENDING);exchange(&stream,out[0],reply,1502);assert(!memcmp(reply,"XNR1",4)&&!memcmp(reply+32,data,1470));
 metadata.flags=XNOW_RX_BROADCAST;assert(!xnow_owner_stream_receive(&stream,data,1470,&metadata));exchange(&stream,out[0],reply,1502);assert(reply[24]==1&&!reply[25]&&!reply[26]&&!reply[27]);
 metadata.flags=XNOW_RX_AUTHENTICATED;assert(!xnow_owner_stream_receive(&stream,data,1470,&metadata));exchange(&stream,out[0],reply,1502);assert(reply[24]==2);
 metadata.flags=3;assert(xnow_owner_stream_receive(&stream,data,1470,&metadata)==XNOW_ARGUMENT&&xnow_owner_stream_writable(&stream));
 metadata.flags=4;assert(xnow_owner_stream_receive(&stream,data,1470,&metadata)==XNOW_ARGUMENT&&xnow_owner_stream_writable(&stream));metadata.flags=0;
 for(unsigned i=0;i<sizeof stream.response;i++)assert(!stream.response[i]);
 /* HUP with a complete queued mutation must stop, not execute that mutation. */
 n=request(cmd,XNOW_OWNER_DELETE,73,6);memcpy(cmd+16,address,6);write_all(in[1],cmd,n);close(in[1]);in[1]=-1;assert(xnow_owner_stream_step(&stream)==XNOW_IO&&stops==1&&c.stopped);unsigned count,encrypted;xnow_peer_count(&endpoint.peers,&count,&encrypted);assert(count==1);assert(xnow_owner_stream_step(&stream)==XNOW_IO&&stops==1);cleanup(&stream,in,out);
 /* Oversize header fails before any body allocation/read or mutation. */
 assert(!xnow_endpoint_stop_step(&endpoint));assert(xnow_endpoint_init(&endpoint,&full,6,17,0,random4)==XNOW_ARGUMENT);
 setup_stream(&stream,&c,in,out);request(cmd,XNOW_OWNER_SEND,74,0xffffffffu);write_all(in[1],cmd,16);for(unsigned i=0;i<10&&!stream.fault;i++)xnow_owner_stream_step(&stream);assert(stream.fault&&stops==2);cleanup(&stream,in,out);
 /* Partial key-bearing request is wiped when the input writer disappears. */
 setup_stream(&stream,&c,in,out);request(cmd,XNOW_OWNER_ADD,75,26);memset(cmd+16,0x55,26);write_all(in[1],cmd,35);for(unsigned i=0;stream.used<35;i++){assert(i<50&&xnow_owner_stream_step(&stream)>=0);}close(in[1]);in[1]=-1;assert(xnow_owner_stream_step(&stream)==XNOW_IO&&stops==3);for(unsigned i=0;i<sizeof stream.request;i++)assert(!stream.request[i]);cleanup(&stream,in,out);
 /* Reader disappearance: owner sees output error before risking SIGPIPE. */
 setup_stream(&stream,&c,in,out);close(out[0]);out[0]=-1;assert(xnow_owner_stream_step(&stream)==XNOW_IO&&stops==4);cleanup(&stream,in,out);
 /* Replaced duplicate FD is detected and is not closed as an owned handle. */
 setup_stream(&stream,&c,in,out);int replacement=open("/dev/null",O_RDONLY),reused=stream.input;assert(replacement>=0);assert(dup2(replacement,reused)==reused);close(replacement);assert(xnow_owner_stream_step(&stream)==XNOW_IO&&stops==5);assert(xnow_owner_stream_close(&stream)==XNOW_IDENTITY);assert(fcntl(reused,F_GETFD)>=0);close(reused);
 for(unsigned i=0;i<2;i++){close(in[i]);close(out[i]);}
 puts("Owner stream: real partial pipes,1470 TX/RX, backpressure, HUP-with-data, oversized header, lost reader and descriptor identity passed; radio synthetic.");return 0;
}
