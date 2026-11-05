#ifndef XW_PARENT_TRACE_STORE_H
#define XW_PARENT_TRACE_STORE_H
#include <stdint.h>
#define XW_PARENT_TRACE_FILE_BYTES 2048u
#define XW_PARENT_TRACE_SLOTS 16u
#define XW_PARENT_TRACE_RECORD_BYTES 64u
/* Internal diagnostic backend, never a public SDK grant. Caller supplies a
 * trusted ownership check: exactly1 means user storage is still Linux-owned,
 * not exported over USB. Mount/identity checks here do not replace that proof.
 * Ownership callback/context must outlive the store and perform a bounded,
 * read-only check without waiting for USB. Payload values are copied during
 * the call; no caller frame pointer is retained.
 */
struct xw_parent_trace_store {
 union {uint64_t align;unsigned char bytes[64];} lock;
 unsigned char header[32];
 uint32_t attempted,sequence;
 unsigned initialized,armed;
 void *context;int (*owned)(void *);
};
enum {XW_TRACE_OK=0,XW_TRACE_SKIPPED=1,XW_TRACE_INVALID=-1,XW_TRACE_STORAGE=-2,XW_TRACE_LOCK=-3};
/* Zero-initialized context required. No file is opened or created by init. */
int xw_parent_trace_store_init(struct xw_parent_trace_store *,const unsigned char[32],void *,int (*)(void *));
int xw_parent_trace_store_record(struct xw_parent_trace_store *,unsigned stage,const uint32_t payload[12]);
int xw_parent_trace_store_destroy(struct xw_parent_trace_store *);
#endif
