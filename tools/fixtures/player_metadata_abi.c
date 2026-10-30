/* Original LinuxThreads opaque primitive layout smoke test; no new thread. */
#include "../../runtime/platform/player/metadata_async.h"
#include <assert.h>
#include <stdio.h>
int main(void){static struct xw_metadata_async state;struct xw_media_item item;assert(!xw_metadata_async_init(&state));assert(xw_metadata_async_observe(&state,0,0,1000,&item)==XW_PLAYER_UNAVAILABLE);assert(!xw_metadata_async_stop(&state));assert(xw_metadata_async_drained(&state));assert(!xw_metadata_async_destroy(&state));assert(!xw_stock_media_source_ready());struct xw_stock_media media={0};assert(xw_stock_media_open(&media)==XW_PLAYER_UNSUPPORTED);puts("Original opaque pthread initialization/destruction and independent-process media refusal passed; no thread created");return 0;}
