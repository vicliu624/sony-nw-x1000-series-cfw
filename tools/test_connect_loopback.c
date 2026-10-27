#define _POSIX_C_SOURCE 200809L
#include "../runtime/store/connect_step.h"
#include "../runtime/store/socket_step.h"
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#ifdef HB_CONNECT_HOST_CLOCK
#include <time.h>
long x1000_oabi_call(long n,long id,long pointer,long c,long d,long e,long f){
 assert(n==263&&id==1&&!c&&!d&&!e&&!f);struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return -1;
 int *out=(int *)pointer;out[0]=(int)t.tv_sec;out[1]=(int)t.tv_nsec;return 0;
}
#endif
static int wait_connect(struct hb_connect *c,int result){for(unsigned i=0;!result&&i<100;i++)result=hb_connect_step(c,100);return result;}
int main(void){
 int listener=socket(AF_INET,SOCK_STREAM,0);assert(listener>=0);
 struct sockaddr_in address;memset(&address,0,sizeof address);address.sin_family=AF_INET;address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
 assert(!bind(listener,(const struct sockaddr *)&address,sizeof address)&&!listen(listener,4));
 socklen_t size=sizeof address;assert(!getsockname(listener,(struct sockaddr *)&address,&size)&&size==sizeof address&&address.sin_addr.s_addr==htonl(INADDR_LOOPBACK)&&address.sin_port);
 struct hb_transfer_deadline deadline;assert(!hb_transfer_deadline_init(&deadline,2000));
 volatile int stop=0;struct hb_connect connection;hb_connect_init(&connection);
 int initial=hb_connect_begin(&connection,AF_INET,(const struct sockaddr *)&address,sizeof address,&deadline,&stop);
 assert(initial>=0&&wait_connect(&connection,initial)==1);
 int client=hb_connect_take(&connection);assert(client>=0&&hb_connect_take(&connection)==-1);
 struct sockaddr_in remote;size=sizeof remote;int peer=accept(listener,(struct sockaddr *)&remote,&size);
 assert(peer>=0&&remote.sin_addr.s_addr==htonl(INADDR_LOOPBACK));
 size=sizeof remote;assert(!getpeername(client,(struct sockaddr *)&remote,&size)&&remote.sin_addr.s_addr==htonl(INADDR_LOOPBACK));
 assert(hb_socket_write_step(client,(const unsigned char *)"probe",5,100,&stop)==5);
 unsigned char data[5];assert(hb_socket_read_step(peer,data,5,100,&stop)==5&&!memcmp(data,"probe",5));
 assert(!close(client)&&!close(peer)&&!hb_connect_release(&connection));
 hb_connect_init(&connection);assert(!hb_transfer_deadline_init(&deadline,2000));
 int pending=hb_connect_begin(&connection,AF_INET,(const struct sockaddr *)&address,sizeof address,&deadline,&stop);
 if(!pending){stop=1;assert(hb_connect_step(&connection,0)==HB_CONNECT_CANCELLED&&connection.fd==-1);stop=0;}
 else {assert(pending==1);assert(!hb_connect_release(&connection));}
 peer=accept(listener,0,0);assert(peer>=0&&!close(peer));assert(!close(listener));
 hb_connect_init(&connection);assert(!hb_transfer_deadline_init(&deadline,2000));
 int refused=hb_connect_begin(&connection,AF_INET,(const struct sockaddr *)&address,sizeof address,&deadline,&stop);
 assert(wait_connect(&connection,refused)==HB_CONNECT_IO&&connection.system_error==ECONNREFUSED&&connection.fd==-1);
 const char *message=initial==0?"loopback-native-in-progress; bytes/cancel/refusal passed\n":"loopback-immediate-connect; bytes/cancel/refusal passed\n";
 return write(1,message,strlen(message))==(long)strlen(message)?0:1;
}
