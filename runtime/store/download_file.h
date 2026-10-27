#ifndef HB_STORE_DOWNLOAD_FILE_H
#define HB_STORE_DOWNLOAD_FILE_H
#include "download_stream.h"
enum hb_download_file_state {HB_FETCH_EMPTY,HB_FETCH_OPEN,HB_FETCH_READY,HB_FETCH_REVIEW};
enum hb_download_file_error {HB_FETCH_IO=-30,HB_FETCH_SPACE=-31,HB_FETCH_EXISTS=-32,HB_FETCH_RETAINED=-33};
struct hb_download_file {
 struct hb_download_stream body;
 char folder[512],path[512];
 unsigned long long device,inode;
 int fd,owns,identity_known;
 enum hb_download_file_state state;
};
/* Initialize once at stable address; never reinitialize a live owner. Caller
 * provides a canonical quiescent user-storage cache, not system/state paths. */
void hb_download_file_init(struct hb_download_file *);
int hb_download_file_begin(struct hb_download_file *,const char *folder,const char *key,
 unsigned bytes,const unsigned char *digest,unsigned long long reserve,volatile int *stop);
/* Feed decoded bytes through body, optionally via http_response. Finish accepts
 * only full size/hash and syncs file+directory, leaving an INACTIVE cache file.
 * READY does not publish a package or app. Owner must later discard/move it. */
int hb_download_file_finish(struct hb_download_file *);
/* Deletes only its owned matching inode. Unknown/replaced files are retained. */
int hb_download_file_discard(struct hb_download_file *);
/* Explicit same-process review of a closed owned file, not startup recovery.
 * Rehashes and retries synchronization; identity/size/hash must all match. */
int hb_download_file_recheck(struct hb_download_file *);
#endif
