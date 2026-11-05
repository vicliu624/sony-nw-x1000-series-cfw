#include "../../runtime/platform/player/startup_delivery.h"
#include "../../runtime/platform/services/descriptor.h"
#include <assert.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
int main(void){
 const char *nonce="0123456789abcdef0123456789abcdef";
 assert(xw_player_startup_listen("/contents/not-an-ipc-directory")<0);
 for(unsigned mode=0;mode<3;mode++){
  char directory[80],path[108];snprintf(directory,sizeof directory,"/tmp/x1000-player-test-%u-%u",(unsigned)getpid(),mode);
  assert(!mkdir(directory,0700));int listener=xw_player_startup_listen(directory);assert(listener>=0);
  assert(xw_player_startup_listen(directory)<0); /* Existing socket is retained. */
  pid_t child=fork();assert(child>=0);
  if(!child){
   close(listener);int channel=xw_player_startup_connect(directory,mode==1?"1123456789abcdef0123456789abcdef":nonce,23,7,200);
   if(mode){assert(channel<0);_exit(0);}
   assert(channel>=0);int pair[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,pair));
   struct xw_descriptor_offer offer={23,5,7};assert(!xw_service_descriptor_send(channel,pair[1],&offer));close(pair[1]);
   char data[4];assert(read(pair[0],data,sizeof data)==4&&!memcmp(data,"ping",4));
   close(pair[0]);close(channel);_exit(0);
  }
  if(mode!=2){
   int accepted=1;for(unsigned i=0;i<1000&&accepted==1;i++){accepted=xw_player_startup_accept(listener,directory,nonce,23,7);if(accepted==1)poll(0,0,1);}
   assert(accepted==(mode==1?-1:0));
   if(!mode){
    int stream=-1,rc=1;struct xw_descriptor_offer offer;
    for(unsigned i=0;i<1000&&rc;i++){rc=xw_service_descriptor_receive(listener,&stream,&offer);if(rc)poll(0,0,1);}
    assert(!rc&&offer.generation==23&&offer.session==5&&offer.grants==7);
    assert(write(stream,"ping",4)==4);close(stream);
   }
  }
  int status;assert(waitpid(child,&status,0)==child&&status==0);close(listener);
  snprintf(path,sizeof path,"%s/controller.sock",directory);assert(!unlink(path));assert(!rmdir(directory));
 }
 puts("PLAYER_STARTUP_DELIVERY_PASS");return 0;
}
