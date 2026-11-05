/* Actual generic SDK pipe decoder. Records are fixtures, not RF proof. */
#include "../runtime/apps/wireless-remote/radio_retirement.h"
#include "../runtime/platform/player/player.h"
#include <assert.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <fcntl.h>
extern int fixture_retire_fcntl(int,int,...) __asm__("fcntl");
static const uint8_t cookie[16]={1,2,3};
static int start(struct xnow_handoff *h,struct wr_radio_retirement *r){
 memset(h,0,sizeof *h);memset(r,0,sizeof *r);assert(!xnow_handoff_create(h,cookie));
 int writer=dup(h->writer);assert(writer>=3);assert(!xnow_handoff_parent_arm(h));
 assert(!wr_radio_retirement_init(r,h));return writer;
}
int main(void){
 struct xnow_handoff h;struct wr_radio_retirement r;uint8_t record[32]={0};
 memcpy(record,"XRFDONE1",8);memcpy(record+8,cookie,16);record[24]=1;
 int writer=start(&h,&r);assert(wr_radio_retirement_poll(&r)==XW_PLAYER_BUSY);
 assert(write(writer,record,7)==7&&wr_radio_retirement_poll(&r)==XW_PLAYER_BUSY);
 assert(write(writer,record+7,25)==25&&wr_radio_retirement_poll(&r)==XW_PLAYER_BUSY);
 assert(!close(writer)&&!wr_radio_retirement_poll(&r)&&r.done&&h.reader==-1);
 assert(!wr_radio_retirement_poll(&r));
 writer=start(&h,&r);close(writer);assert(wr_radio_retirement_poll(&r)==XW_PLAYER_UNCERTAIN&&!r.done);
 int retained=h.reader;assert(wr_radio_retirement_poll(&r)==XW_PLAYER_UNCERTAIN&&h.reader==retained);close(h.reader);
 writer=start(&h,&r);record[8]^=1;assert(write(writer,record,32)==32);close(writer);
 assert(wr_radio_retirement_poll(&r)==XW_PLAYER_UNCERTAIN&&!r.done);close(h.reader);record[8]^=1;
 writer=start(&h,&r);record[28]=1;assert(write(writer,record,32)==32);close(writer);
 assert(!wr_radio_retirement_poll(&r)&&r.done&&r.startup_failure==1);
 int pipes[2];assert(!pipe(pipes));memset(&h,0,sizeof h);memset(&r,0,sizeof r);
 assert(xnow_handoff_adopt_reader(&h,pipes[0],cookie)==XNOW_IDENTITY);
 assert(fixture_retire_fcntl(pipes[0],F_GETFD)>=0);
 assert(!fixture_retire_fcntl(pipes[0],F_SETFL,O_NONBLOCK));
 assert(!xnow_handoff_adopt_reader(&h,pipes[0],cookie));
 assert(fixture_retire_fcntl(h.reader,F_GETFD)&FD_CLOEXEC);
 assert(xnow_handoff_adopt_reader(&h,pipes[1],cookie)==XNOW_ARGUMENT);
 assert(!wr_radio_retirement_init(&r,&h));assert(write(pipes[1],record,32)==32);close(pipes[1]);
 assert(!wr_radio_retirement_poll(&r)&&r.done&&r.startup_failure==1);
 puts("REMOTE_RETIREMENT_PASS: actual SDK parser, partial writes, record plus EOF, wrong cookie, empty EOF, retained faults and startup result; RF modeled");return 0;
}
