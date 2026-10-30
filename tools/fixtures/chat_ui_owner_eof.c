/* Execute the production UI event reducer and client pipe parser; no devices. */
#define main chat_ui_unused_main
#include "../../runtime/apps/espnow-chat/chat_app.c"
#undef main
#include <assert.h>
extern int fixture_fcntl(int,int,...) __asm__("fcntl");
static int writer;
static void begin_case(void){
 int p[2];assert(!pipe(p));client.events=p[0];client.used=0;writer=p[1];
 assert(fixture_fcntl(p[0],F_SETFL,O_NONBLOCK)==0);
 owner_finished=0;owner_phase=CHAT_READY;linked=1;strcpy(notice,"READY");
}
static void finish_case(void){close(client.events);client.events=-1;if(writer>=0)close(writer);}
static void put_event(unsigned kind,unsigned state){struct chat_event e={0};e.kind=kind;e.state=state;assert(write(writer,&e,sizeof e)==sizeof e);}
int main(void){
 begin_case();close(writer);writer=-1;read_owner();
 assert(!owner_finished&&!linked&&owner_phase==CHAT_REPAIR_REQUIRED);finish_case();
 begin_case();struct chat_event partial={0};assert(write(writer,&partial,7)==7);close(writer);writer=-1;read_owner();read_owner();
 assert(!owner_finished&&owner_phase==CHAT_REPAIR_REQUIRED);finish_case();
 begin_case();put_event(CHAT_STATE,CHAT_RESTORING);read_owner();assert(!owner_finished&&owner_phase==CHAT_RESTORING);
 put_event(CHAT_FINISHED,0);close(writer);writer=-1;read_owner();
 assert(owner_finished&&!linked&&!owner_phase&&!strcmp(notice,"NORMAL WIFI RESTORED"));finish_case();
 begin_case();put_event(CHAT_ERROR,CHAT_REPAIR_REQUIRED);close(writer);writer=-1;read_owner();
 assert(!owner_finished&&owner_phase==CHAT_REPAIR_REQUIRED);finish_case();
 puts("UI owner EOF: only explicit completion releases normal quit; partial/error EOF retains repair state. No hardware or launcher-kill qualification.");return 0;
}
