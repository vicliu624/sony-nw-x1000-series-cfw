#include "../../runtime/platform/player/query_snapshot.h"
#include "../../runtime/platform/player/local_identity.h"
#include <assert.h>
#include <string.h>
static struct xw_query_snapshot a,b;
int main(void){
 b=a;b.nodes[31].operation=123;b.sort[15].key=456;
 unsigned char *pad=(unsigned char *)&b.parent+sizeof b.parent;
 if(pad<(unsigned char *)b.nodes)*pad=0x5a;
 assert(xw_query_snapshot_equal(&a,&b));
 a.node_count=1;a.root=1;a.nodes[0].operation=1;a.nodes[0].kind=9;b=a;assert(xw_query_snapshot_equal(&a,&b));b.nodes[0].low=1;assert(!xw_query_snapshot_equal(&a,&b));
 b=a;a.sort_count=b.sort_count=1;a.sort[0].key=9;b.sort[0].key=10;assert(!xw_query_snapshot_equal(&a,&b));b=a;assert(xw_query_snapshot_equal(&a,&b));
 a.kind=1;a.domain=1;assert(!xw_local_media_id_format(1,42,&a.parent));b=a;b.parent.value[64]=0x5a;assert(xw_query_snapshot_equal(&a,&b));
 assert(!xw_local_media_id_format(1,43,&b.parent));assert(!xw_query_snapshot_equal(&a,&b));b=a;b.nodes[0].left=1;assert(!xw_query_snapshot_equal(&b,&b));assert(!xw_query_snapshot_equal(0,&a));return 0;
}
