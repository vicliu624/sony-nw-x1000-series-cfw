#ifndef WR_NATIVE_PAGE_BRIDGE_H
#define WR_NATIVE_PAGE_BRIDGE_H
#include "native_page.h"
#include "settings_backend.h"
/* Owned by the GUI/factory until unbound. No FDs, storage or RF ownership.
 * The backend must outlive this object; bind/unbind run on its owner thread. */
struct wr_native_page_bridge {
 struct wr_settings_backend *backend;
 unsigned long owner;uint64_t generation;
 unsigned open,preview;
 void *view_context;int (*view_begin)(void *);int (*view_end)(void *);
};
int wr_native_page_bridge_bind(struct wr_native_page_bridge *,struct wr_settings_backend *);
int wr_native_page_bridge_unbind(struct wr_native_page_bridge *);
/* Mandatory before OPEN. Ports borrow/end the existing view; end requests
 * deferred restoration. Context must outlive the bridge and its pending close. */
int wr_native_page_bridge_attach_view(struct wr_native_page_bridge *,void *,int (*)(void *),int (*)(void *));
uint32_t wr_native_page_bridge_request(struct wr_native_page_bridge *,uint32_t,uint32_t);
#endif
