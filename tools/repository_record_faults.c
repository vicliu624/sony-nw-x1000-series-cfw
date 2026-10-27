/* Test-only write interruption for the real repository/store UI fixture. */
#define __wrap_write hb_repository_regular_write
#include "download_file_faults.c"
#undef __wrap_write
static int cut_record_write;
void hb_repository_record_exit(int enabled){cut_record_write=enabled;}
ssize_t __wrap_write(int fd,const void *data,size_t bytes){if(cut_record_write){if(__real_write(fd,data,bytes?1:0)!=1)_exit(78);_exit(77);}return hb_repository_regular_write(fd,data,bytes);}
