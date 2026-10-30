/* Freestanding ARM consumer of the private provider and real client core. */
#include "stock_host_image.c"
#include "../../runtime/platform/player/stock_provider.h"
#include <stddef.h>
void *memset(void *p,int c,size_t n){unsigned char *q=p;while(n--)*q++=(unsigned char)c;return p;}
void *memcpy(void *p,const void *s,size_t n){unsigned char *q=p;const unsigned char *r=s;while(n--)*q++=*r++;return p;}
int strcmp(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return (unsigned char)*a-(unsigned char)*b;}
struct xw_player test_player;
struct xw_stock_provider test_provider;
struct xw_player_snapshot test_snapshot;
uint32_t test_changes;
int test_bind(void){return xw_stock_player_bind(&test_player,&test_provider);}
int test_poll(void){return xw_player_poll(&test_player,&test_snapshot,&test_changes);}
int test_command(int op,int value){struct xw_player_command command={0};command.operation=op;command.value=value;return xw_player_command(&test_player,&command);}
int test_close(void){return xw_player_close(&test_player);}
int test_volume(void){return test_snapshot.volume;}
int test_state(void){return test_snapshot.state;}
int test_valid(void){return test_snapshot.valid;}
int test_bound(void){return test_provider.bound!=0;}
int test_bindings_remaining(void){return test_provider.gui.bound||test_provider.volume.bound||test_provider.info.bound;}
const char *test_track_id(void){return test_snapshot.track.id.value;}
