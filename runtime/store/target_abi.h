#ifndef HB_STORE_TARGET_ABI_H
#define HB_STORE_TARGET_ABI_H
/* Include last, after system headers. Never enable against the host libc for
 * filesystem operations. This profile binds the observed Sony interfaces. */
#ifdef HB_STORE_SONY_LIBC
#include <stddef.h>
#include <dirent.h>
#include <sys/statvfs.h>
#include "stock_fs_bridge.h"
/* These fields are consumed directly, unlike the explicitly decoded stat.
 * Refuse a header layout change; this is not target syscall qualification. */
typedef char hb_stock_statvfs_size[(sizeof(struct statvfs)==96)?1:-1];
typedef char hb_stock_statvfs_unit[(offsetof(struct statvfs,f_frsize)==4)?1:-1];
typedef char hb_stock_statvfs_available[(offsetof(struct statvfs,f_bavail)==24 && sizeof(((struct statvfs*)0)->f_bavail)==8)?1:-1];
typedef char hb_stock_dirent_length[(offsetof(struct dirent,d_reclen)==16)?1:-1];
typedef char hb_stock_dirent_name[(offsetof(struct dirent,d_name)==19)?1:-1];
#define stat hb_target_stat
#define fstat hb_target_fstat
#define lstat hb_target_lstat
#endif
#endif
