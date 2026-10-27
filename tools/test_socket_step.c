#include "../runtime/store/socket_step.h"
#include <sys/socket.h>
#include <unistd.h>
#include <string.h>
#include <assert.h>
int main(void){
 int pair[2];unsigned char buffer[8];volatile int stop=0;
 assert(!socketpair(AF_UNIX,SOCK_STREAM,0,pair));
 assert(hb_socket_read_step(pair[1],buffer,8,0,&stop)==HB_SOCKET_TIMEOUT);
 assert(hb_socket_write_step(pair[0],(const unsigned char *)"abc",3,100,&stop)==3);
 assert(hb_socket_read_step(pair[1],buffer,8,100,&stop)==3&&!memcmp(buffer,"abc",3));
 stop=1;assert(hb_socket_write_step(pair[0],(const unsigned char *)"x",1,0,&stop)==HB_SOCKET_CANCELLED);
 assert(hb_socket_read_step(pair[1],buffer,8,0,&stop)==HB_SOCKET_CANCELLED);
 stop=0;assert(hb_socket_read_step(pair[1],buffer,8,0,&stop)==HB_SOCKET_TIMEOUT);
 assert(hb_socket_read_step(-1,buffer,8,0,&stop)==HB_SOCKET_ERROR);
 assert(hb_socket_read_step(pair[1],buffer,8,1001,&stop)==HB_SOCKET_ERROR);
 assert(hb_socket_write_step(pair[0],(const unsigned char *)"x",0,0,&stop)==HB_SOCKET_ERROR);
 assert(!shutdown(pair[0],SHUT_WR));assert(hb_socket_read_step(pair[1],buffer,8,100,&stop)==0);
 assert(!close(pair[1]));
 assert(hb_socket_write_step(pair[0],(const unsigned char *)"x",1,100,&stop)==HB_SOCKET_ERROR);
 assert(!close(pair[0]));return 0;
}
