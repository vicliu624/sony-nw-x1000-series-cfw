#include "radio_retirement.h"
#include "worker.h"
#include <unistd.h>
#include <string.h>
int wr_radio_retirement_init(struct wr_radio_retirement *r,struct xnow_handoff *h){
 if(!r||r->used||!h||h->pid!=(int)getpid()||!h->armed||h->done||h->fault||h->reader<3||h->writer!=-1)return XW_PLAYER_INVALID;
 memset(r,0,sizeof *r);r->handoff=h;r->used=1;return 0;
}
int wr_radio_retirement_poll(void *context){
 struct wr_radio_retirement *r=context;
 if(!r||!r->used)return XW_PLAYER_INVALID;
 if(r->fault)return XW_PLAYER_UNCERTAIN;if(r->done)return 0;
 struct xnow_handoff_result result;int rc=xnow_handoff_poll(r->handoff,&result);
 if(rc==XNOW_PENDING)return XW_PLAYER_BUSY;
 if(rc){r->fault=1;return XW_PLAYER_UNCERTAIN;}
 r->startup_failure=result.startup_failure;
 if(xnow_handoff_close(r->handoff)){r->fault=1;return XW_PLAYER_UNCERTAIN;}
 r->done=1;return 0;
}
