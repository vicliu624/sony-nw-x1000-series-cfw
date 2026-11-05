#include "../runtime/apps/wireless-remote/library_player.h"
#include "../runtime/platform/player/provider.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct xw_player player;
static struct wr_library_ledger ledger;
static unsigned calls;static int failure,reenter;
static int snapshot(void *p,struct xw_player_snapshot *out){(void)p;memset(out,0,sizeof *out);return 0;}
static int browse(void *p,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *page){
 (void)p;calls++;
 if(reenter){struct wr_library_request request={0};request.session=7;request.request=99;request.query.limit=1;struct wr_library_reply output={0};assert(wr_library_dispatch(&ledger,&player,7,&request,&output));}
 if(failure)return failure;
 assert(q->limit==1);memset(items,0,sizeof *items);strcpy(items->id.value,"media-1");strcpy(items->title,"Track");items->flags=XW_MEDIA_TITLE_PRESENT;
 *page=(struct xw_media_page){11,q->offset,1,10,q->offset+1};return 0;
}
static int close_player(void *p){(void)p;return 0;}
int main(void){
 struct xw_player_provider provider={XW_PLAYER_API,0,0,snapshot,0,browse,close_player};assert(!xw_player_bind(&player,&provider));
 struct wr_library_request q={0};q.session=7;q.request=1;q.query.limit=1;struct wr_library_reply out={0};
 assert(!wr_library_dispatch(&ledger,&player,7,&q,&out)&&!out.result&&out.page.count==1&&calls==1);
 assert(!wr_library_dispatch(&ledger,&player,7,&q,&out)&&calls==1);
 struct wr_library_reply saved=out;q.query.offset=1;assert(wr_library_dispatch(&ledger,&player,7,&q,&out)&&calls==1&&!memcmp(&saved,&out,sizeof out));
 q.request=2;reenter=1;assert(!wr_library_dispatch(&ledger,&player,7,&q,&out)&&calls==2);reenter=0;
 q.request=1;assert(wr_library_dispatch(&ledger,&player,7,&q,&out)&&calls==2);
 q.request=3;q.session=8;assert(wr_library_dispatch(&ledger,&player,7,&q,&out)&&calls==2);q.session=7;
 failure=XW_PLAYER_UNSUPPORTED;assert(!wr_library_dispatch(&ledger,&player,7,&q,&out)&&out.result==failure&&!out.page.count&&calls==3);
 assert(!wr_library_dispatch(&ledger,&player,7,&q,&out)&&calls==3);
 assert(!xw_player_close(&player));q.request=4;assert(!wr_library_dispatch(&ledger,&player,7,&q,&out)&&out.result==XW_PLAYER_CLOSED&&calls==3);
 puts("REMOTE_LIBRARY_PLAYER_DISPATCH_PASS");return 0;
}
