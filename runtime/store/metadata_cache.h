#ifndef HB_STORE_METADATA_CACHE_H
#define HB_STORE_METADATA_CACHE_H
#define HB_METADATA_CACHE_BYTES 32768u
struct hb_metadata_cache {
 char parent[512],path[512],key[33];
 unsigned expected,actual;
 unsigned char expected_sha256[32],observed_sha256[32];
 unsigned long long parent_device,parent_inode,device,inode;
 volatile int *stop;int valid,complete,removed;
};
enum hb_metadata_cache_result {HB_META_CACHE_ABSENT=2,HB_META_CACHE_PREVIOUS=3};
enum hb_metadata_cache_error {HB_META_CACHE_INPUT=-150,HB_META_CACHE_IO=-151,HB_META_CACHE_CANCELLED=-152};
int hb_metadata_cache_key(const char *url,unsigned bytes,const unsigned char digest[32],char key[33]);
/* Exact configured URL/size/digest target only.0=verified complete data,
 * 2=absent,3=bounded regular previous cache requiring explicit discard choice.
 * Unknown/link/oversize targets reject. Unverified data is cleared. No network.
 * Caller keeps stop alive, serializes writers and keeps the root quiescent. */
int hb_metadata_cache_inspect(const char *parent,const char *url,unsigned bytes,const unsigned char digest[32],volatile int *,unsigned char *data,unsigned capacity,struct hb_metadata_cache *);
/* Explicit choice for PREVIOUS; automatic only after consuming verified data.
 * Rechecks inode/length AND observed bytes hash. Never deletes a replacement.
 * Retains removed state for parent-sync retry. Does not change stop. */
int hb_metadata_cache_discard(struct hb_metadata_cache *);
#endif
