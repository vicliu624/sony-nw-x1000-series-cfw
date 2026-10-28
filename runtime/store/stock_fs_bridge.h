#ifndef HB_STORE_STOCK_FS_BRIDGE_H
#define HB_STORE_STOCK_FS_BRIDGE_H
/* Private application view, not either libc's struct stat. Only fields used
 * by the store are exposed; stock functions receive a separate96-byte buffer. */
struct hb_target_stat {
 unsigned long long st_dev;
 long long st_size;
 unsigned long long st_ino;
 unsigned st_mode,st_nlink;
};
int hb_target_fstat(int,struct hb_target_stat *);
int hb_target_lstat(const char *,struct hb_target_stat *);
int hb_target_stat(const char *,struct hb_target_stat *);
#endif
