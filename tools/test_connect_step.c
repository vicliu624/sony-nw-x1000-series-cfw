#define _POSIX_C_SOURCE 200809L
#include "../runtime/store/connect_step.h"
#include <sys/un.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
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
extern int __real_connect(int,const struct sockaddr *,socklen_t);
static int force_pending=1;
extern int sony_fcntl(int,int,...) __asm__("fcntl");
int __wrap_connect(int fd,const struct sockaddr *address,socklen_t size){
 if(force_pending==2){errno=EAGAIN;return -1;}
 int result=__real_connect(fd,address,size);if(!result&&force_pending){errno=EINPROGRESS;return -1;}return result;
}
static void drain(int listener){int fd=accept(listener,0,0);assert(fd>=0);assert(!close(fd));}
int main(void){
 const char *path=getenv("HB_LOCAL_SOCKET");assert(path&&strlen(path)<sizeof(((struct sockaddr_un *)0)->sun_path)-1);
 /* Linux abstract namespace avoids filesystem socket support on /mnt/c. */
 struct sockaddr_un address;memset(&address,0,sizeof address);address.sun_family=AF_UNIX;memcpy(address.sun_path+1,path,strlen(path));
 int listener=socket(AF_UNIX,SOCK_STREAM,0);assert(listener>=0&&!bind(listener,(const struct sockaddr *)&address,sizeof address)&&!listen(listener,4));
 struct hb_transfer_deadline deadline;volatile int stop=0;struct hb_connect c;
 assert(!hb_transfer_deadline_init(&deadline,1000));hb_connect_init(&c);
 assert(hb_connect_begin(&c,AF_UNIX,(const struct sockaddr *)&address,sizeof address,&deadline,&stop)==0);
 assert(hb_connect_step(&c,100)==1);
 int client=hb_connect_take(&c);assert(client>=0&&(sony_fcntl(client,F_GETFL,0)&O_NONBLOCK)&&hb_connect_take(&c)==-1);
 int peer=accept(listener,0,0);assert(peer>=0);assert(write(client,"abc",3)==3);char data[3];assert(read(peer,data,3)==3&&!memcmp(data,"abc",3));
 assert(!close(client)&&!close(peer)&&!hb_connect_release(&c));
 hb_connect_init(&c);stop=1;assert(hb_connect_begin(&c,AF_UNIX,(const struct sockaddr *)&address,sizeof address,&deadline,&stop)==HB_CONNECT_CANCELLED&&c.fd==-1);
 stop=0;hb_connect_init(&c);assert(!hb_transfer_deadline_init(&deadline,0));assert(hb_connect_begin(&c,AF_UNIX,(const struct sockaddr *)&address,sizeof address,&deadline,&stop)==HB_CONNECT_DEADLINE&&c.fd==-1);
 force_pending=2;hb_connect_init(&c);assert(!hb_transfer_deadline_init(&deadline,1000));assert(hb_connect_begin(&c,AF_UNIX,(const struct sockaddr *)&address,sizeof address,&deadline,&stop)==HB_CONNECT_IO&&c.system_error==EAGAIN&&c.fd==-1);force_pending=1;
 hb_connect_init(&c);assert(!hb_transfer_deadline_init(&deadline,1000));assert(!hb_connect_begin(&c,AF_UNIX,(const struct sockaddr *)&address,sizeof address,&deadline,&stop));
 stop=1;assert(hb_connect_step(&c,0)==HB_CONNECT_CANCELLED&&c.fd==-1);stop=0;drain(listener);
 assert(!close(listener));hb_connect_init(&c);assert(!hb_transfer_deadline_init(&deadline,1000));
 assert(hb_connect_begin(&c,AF_UNIX,(const struct sockaddr *)&address,sizeof address,&deadline,&stop)==HB_CONNECT_IO&&c.fd==-1);
 return 0;
}
