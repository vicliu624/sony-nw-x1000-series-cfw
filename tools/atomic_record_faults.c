/* Test-only publication fault/exit points; never linked into app candidates. */
#define __wrap_write hb_atomic_regular_write
#define __wrap_fsync hb_atomic_regular_fsync
#include "download_file_faults.c"
#undef __wrap_write
#undef __wrap_fsync
extern int __real_rename(const char *,const char *);
static int atomic_mode;
void hb_atomic_record_fault(int mode){atomic_mode=mode;}
ssize_t __wrap_write(int fd,const void *data,size_t bytes){if(atomic_mode==3){if(__real_write(fd,data,bytes?1:0)!=1)_exit(78);_exit(77);}return hb_atomic_regular_write(fd,data,bytes);}
int __wrap_fsync(int fd){int result=hb_atomic_regular_fsync(fd);if(!result&&atomic_mode==4)_exit(77);return result;}
int __wrap_rename(const char *old,const char *next){
 if(atomic_mode==1){errno=EIO;return -1;}
 int result=__real_rename(old,next);if(result)return result;
 if(atomic_mode==2){errno=EIO;return -1;}
 if(atomic_mode==5)_exit(77);
 return 0;
}
