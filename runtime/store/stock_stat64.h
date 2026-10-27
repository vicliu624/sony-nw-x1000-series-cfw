#ifndef HB_STORE_STOCK_STAT64_H
#define HB_STORE_STOCK_STAT64_H
/* Normalized values, NOT a libc or kernel ABI structure. Input is the observed
 * stock __xstat64/__lxstat64/__fxstat64 version3 output. No syscall is performed. */
struct hb_stock_stat {
 unsigned long long device,size,inode;
 unsigned mode,links;
};
int hb_stock_stat64_decode(const unsigned char *,unsigned bytes,unsigned version,struct hb_stock_stat *);
#endif
