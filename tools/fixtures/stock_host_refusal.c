/* Real loader smoke test: independent executables must refuse host bindings. */
#include "../../runtime/platform/player/stock_volume.h"
#include "../../runtime/platform/player/stock_gui.h"
#include "../../runtime/platform/player/stock_provider.h"
#include "../../runtime/platform/player/stock_info.h"
#include <assert.h>
#include <stdio.h>
int main(void){
 struct xw_stock_volume volume={0};struct xw_stock_gui gui={0};
 struct xw_stock_volume_view view={0};int active=1234;
 struct xw_player player={0};struct xw_stock_provider provider={0};
 struct xw_stock_info info={0};struct xw_stock_info_view information={0};
 struct xw_stock_gui_view gui_view={0};
 assert(xw_stock_info_bind(&info)==XW_PLAYER_UNSUPPORTED);
 assert(xw_stock_info_read(&info,&information)==XW_PLAYER_CLOSED);
 assert(xw_stock_player_bind(&player,&provider)==XW_PLAYER_UNSUPPORTED);
 assert(!player.initialized&&!provider.bound);
 assert(xw_stock_volume_bind(&volume)==XW_PLAYER_UNSUPPORTED);
 assert(xw_stock_gui_bind(&gui)==XW_PLAYER_UNSUPPORTED);
 assert(xw_stock_volume_read(&volume,&view)==XW_PLAYER_CLOSED);
 assert(xw_stock_gui_audio_active(&gui,&active)==XW_PLAYER_CLOSED&&active==1234);
 assert(xw_stock_gui_read(&gui,&gui_view)==XW_PLAYER_CLOSED);
 assert(xw_stock_gui_skip(&gui,1)==XW_PLAYER_CLOSED);
 assert(xw_stock_gui_skip(&gui,-1)==XW_PLAYER_CLOSED);
 assert(xw_stock_gui_skip(&gui,0)==XW_PLAYER_INVALID);
 assert(xw_stock_gui_set_playing(&gui,1)==XW_PLAYER_CLOSED);
 assert(xw_stock_gui_set_playing(&gui,0)==XW_PLAYER_CLOSED);
 assert(xw_stock_gui_set_playing(&gui,2)==XW_PLAYER_INVALID);
 puts("Independent-process native bindings refused without original code calls");return 0;
}
