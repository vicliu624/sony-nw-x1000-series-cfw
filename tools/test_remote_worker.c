/* Business lifetime ordering only; SDK/RF behavior is modeled here. */
#include "../runtime/apps/wireless-remote/worker.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned sends,samples,closes,retire_polls,detached;static int close_result,retire_result,service_result;
int wr_sender_step(struct wr_sender *s){assert(s->active&&!closes);sends++;return service_result;}
int wr_sender_library_tick(struct wr_sender *s,uint64_t now){(void)now;assert(s->active&&!closes);return 0;}
int wr_sender_sample(struct wr_sender *s){assert(s->active&&!closes);samples++;return 0;}
void wr_sender_clear(struct wr_sender *s){assert(detached);memset(s,0,sizeof *s);}
int xnow_client_close(struct xnow_client *c){assert(c&&closes&&!detached);detached++;return 0;}
static int close_player(void *p){struct wr_worker *w=p;assert(w->busy);closes++;return close_result;}
static int retired(void *p){struct wr_worker *w=p;assert(w->busy&&detached&&!w->sender->active);retire_polls++;return retire_result;}
static void reset(void){sends=samples=closes=retire_polls=detached=0;close_result=retire_result=service_result=0;}
int main(void){
 struct wr_worker w={0};struct wr_sender s={0};struct xnow_client radio={0};s.active=1;s.radio=&radio;reset();
 assert(!wr_worker_init(&w,&s,&w,close_player,retired));
 assert(wr_worker_step(&w,100)==XW_PLAYER_BUSY&&samples==1);
 assert(wr_worker_step(&w,200)==XW_PLAYER_BUSY&&samples==1);
 assert(wr_worker_step(&w,600)==XW_PLAYER_BUSY&&samples==2);
 wr_worker_stop(&w);close_result=XW_PLAYER_BUSY;
 assert(wr_worker_step(&w,700)==XW_PLAYER_BUSY&&closes==1&&!detached);
 assert(wr_worker_step(&w,800)==XW_PLAYER_BUSY&&closes==2&&sends==3);
 close_result=0;retire_result=XW_PLAYER_BUSY;
 assert(wr_worker_step(&w,900)==XW_PLAYER_BUSY&&closes==3&&detached==1&&retire_polls==1);
 assert(wr_worker_step(&w,1000)==XW_PLAYER_BUSY&&closes==3&&detached==1&&retire_polls==2);
 retire_result=0;assert(!wr_worker_step(&w,1100)&&w.phase==WR_WORKER_DONE);
 assert(!wr_worker_step(&w,1200)&&retire_polls==3&&detached==1);
 memset(&w,0,sizeof w);memset(&s,0,sizeof s);s.active=1;s.radio=&radio;reset();
 assert(!wr_worker_init(&w,&s,&w,close_player,retired));service_result=-1;retire_result=-1;
 assert(wr_worker_step(&w,1)==XW_PLAYER_UNCERTAIN&&w.phase==WR_WORKER_FAULT&&detached==1&&!samples);
 assert(wr_worker_step(&w,2)==XW_PLAYER_UNCERTAIN&&retire_polls==1);
 memset(&w,0,sizeof w);memset(&s,0,sizeof s);s.active=1;s.radio=&radio;reset();
 assert(!wr_worker_init(&w,&s,&w,close_player,retired));
 wr_worker_stop(&w);close_result=XW_PLAYER_IO;retire_result=XW_PLAYER_BUSY;
 assert(wr_worker_step(&w,1)==XW_PLAYER_BUSY&&w.player_failure==XW_PLAYER_IO&&detached==1&&retire_polls==1);
 retire_result=0;assert(wr_worker_step(&w,2)==XW_PLAYER_UNCERTAIN&&w.phase==WR_WORKER_FAULT&&detached==1&&retire_polls==2);
 puts("REMOTE_WORKER_PASS: heartbeat, no control after stop, pending close, real-receipt boundary and retained failure (modeled SDK)");return 0;
}
