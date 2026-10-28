#define _DEFAULT_SOURCE
#define main device_fixture_main
#include "qqmusic_preview_device.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_preview_service.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_owners.h"
#include <sys/wait.h>
#include <fcntl.h>
#include <signal.h>
#include <unistd.h>
#include <stdio.h>
extern int service_test_fprintf(FILE *,const char *,...) __asm__("fprintf");
extern ssize_t fixture_read(int,void *,size_t) __asm__("read");
extern int fixture_fcntl(int,int,...) __asm__("fcntl");
static struct qq_preview_service service;
static uint64_t wire_generation=1;static unsigned reply_sequence=1,command_sequence=1;
static int producer_callback(void *p,uint64_t generation){(void)p;return qq_preview_service_producer_exited(&service,generation);}
static void send_record(int fd,unsigned type,unsigned seq,unsigned arg,uint64_t value,unsigned corrupt){
 struct qq_preview_record r={wire_generation,value,seq,arg,type};unsigned char bytes[32];assert(!qq_preview_record_encode(&r,bytes,32));if(corrupt)bytes[20]^=1;
 assert(write(fd,bytes,5)==5);usleep(1000);assert(write(fd,bytes+5,27)==27);
}
static void receive(int fd,unsigned *seq,struct qq_preview_record *r){unsigned used=0;unsigned char b[32];while(used<32){ssize_t n=fixture_read(fd,b+used,32-used);assert(n>0);used+=(unsigned)n;}assert(!qq_preview_record_decode(b,32,wire_generation,(*seq)++,r));}
static void ui_process(int command,int pcm,int status_fd,unsigned kind){
 int gate[2],status;pid_t worker;unsigned parent;uint64_t birth;struct qq_preview_record r;char c;
 assert(!pipe(gate));worker=fork();assert(worker>=0);
 if(!worker){unsigned char bytes[32];unsigned i;close(gate[1]);close(command);close(status_fd);assert(fixture_read(gate[0],&c,1)==1);if(c=='x')_exit(0);
  send_record(pcm,QQ_PREVIEW_FORMAT,1,44100,2,kind==3);
  if(kind==2){assert(fixture_read(gate[0],&c,1)==1);_exit(0);}
  for(i=0;i<32;i++)bytes[i]=(unsigned char)i;
  send_record(pcm,QQ_PREVIEW_PCM,2,32,0,0);assert(write(pcm,bytes,3)==3);usleep(1000);assert(write(pcm,bytes+3,29)==29);
  if(kind!=1)send_record(pcm,QQ_PREVIEW_END,3,0,kind==4?9:8,0);
  _exit(0);
 }
 close(gate[0]);assert(qq_preview_process_identity((unsigned)worker,&parent,&birth)==1);
 send_record(command,QQ_PREVIEW_BEGIN,command_sequence++,30000,0,0);send_record(command,QQ_PREVIEW_BIND,command_sequence++,(unsigned)worker,birth+(kind==5),0);
 do{receive(status_fd,&reply_sequence,&r);}while(!(r.argument&0x100u)&&(r.argument&255u)<QQ_PREVIEW_STOPPING);
 assert(write(gate[1],kind==5?"x":"g",1)==1);
 if(kind==2){do{receive(status_fd,&reply_sequence,&r);}while((r.argument&255u)!=QQ_PREVIEW_READY);send_record(command,QQ_PREVIEW_STOP,command_sequence++,0,0,0);assert(write(gate[1],"x",1)==1);}
 do{receive(status_fd,&reply_sequence,&r);}while((r.argument&255u)!=QQ_PREVIEW_DONE);
 assert(waitpid(worker,&status,0)==worker&&WIFEXITED(status)&&!WEXITSTATUS(status));close(gate[1]);return;
}
int main(void){unsigned kind;assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);
 for(kind=0;kind<7;kind++){
  int command[2],pcm[2],statuses[2],child_status=0;pid_t ui;unsigned tick,reaped=0;struct qq_preview_server_channels c;struct qq_preview_device_io io;
  setup();io=d.io;io.producer_exited=producer_callback;assert(!qq_preview_service_init(&service,&io));
  assert(!pipe(command)&&!pipe(pcm)&&!pipe(statuses));ui=fork();assert(ui>=0);
  if(!ui){close(command[0]);close(pcm[0]);close(statuses[1]);ui_process(command[1],pcm[1],statuses[0],kind==6?3:kind);if(kind==6){wire_generation=2;ui_process(command[1],pcm[1],statuses[0],0);}_exit(0);}
  close(command[1]);close(pcm[1]);close(statuses[0]);assert(!fixture_fcntl(command[0],F_SETFL,O_NONBLOCK)&&!fixture_fcntl(pcm[0],F_SETFL,O_NONBLOCK)&&!fixture_fcntl(statuses[1],F_SETFL,O_NONBLOCK));
  c.command=command[0];c.pcm=pcm[0];c.status=statuses[1];c.ui_pid=ui;
  for(tick=0;tick<3000;tick++){
   int rc;if(!reaped){pid_t got=waitpid(ui,&child_status,WNOHANG);assert(got==0||got==ui);if(got==ui)reaped=1;}
   rc=qq_preview_service_pump(&service,&c,reaped,0,100+tick);if(rc<0)service_test_fprintf(stderr,"kind=%u tick=%u phase=%u failed=%u bound=%u ended=%u accepted=%llu dgen=%llu uncertain=%u\n",kind,tick,service.session.phase,service.failed,service.bound,service.ended,(unsigned long long)service.accepted_frames,(unsigned long long)service.device.generation,service.device.uncertain);assert(rc>=0);
   if(reaped&&rc==1)break;
   usleep(1000);
  }
  assert(tick<3000&&reaped&&WIFEXITED(child_status)&&!WEXITSTATUS(child_status));assert(service.session.phase==QQ_PREVIEW_DONE&&!m.guard&&!m.pcm&&!m.mixer);
  assert(!memcmp(&m.state,&m.original,sizeof(m.state)));
  if(kind==0||kind==6){assert(!service.failed&&!service.session.failed&&m.accepted==32&&m.padding_bytes==992&&service.accepted_frames==8);}
  else if(kind!=2)assert(service.failed||service.session.failed);
  close(command[0]);close(pcm[0]);close(statuses[1]);
 }
 return 0;
}



