#include "remote_page_guard.h"
#include "stock_image.h"
#include "remote_native_page_profile.h"
struct guard {uint32_t address,bytes;unsigned char digest[32];};
static const uintptr_t callers[]=XW_REMOTE_PAGE_CALLERS;
static const struct guard page[]=XW_REMOTE_PAGE_GUARDS;
static const struct guard view[]=XW_REMOTE_VIEW_GUARDS;
static int valid(const struct guard *g,unsigned count){
 for(unsigned i=0;i<count;i++)if(xw_stock_image_match(g[i].address,g[i].bytes,g[i].digest))return 0;
 return 1;
}
int xw_player_remote_page_caller(uintptr_t caller){
 for(unsigned i=0;i<sizeof callers/sizeof *callers;i++)if(caller==callers[i])return 1;
 return 0;
}
int xw_player_remote_page_image_valid(void){return valid(page,sizeof page/sizeof *page);}
int xw_player_remote_view_image_valid(void){return valid(view,sizeof view/sizeof *view);}
