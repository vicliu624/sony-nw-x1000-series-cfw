/* Stock-libc files and directory streams, no raw syscall ABI here. */
#include "linux_files.h"
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <limits.h>
#include <stddef.h>
/* Stock exports llseek (not lseek64). Its observed ARM ABI takes the 64-bit
 * offset in aligned r2/r3 and whence on the stack; no 64-to-32 alias. */
extern long long hb_stock_llseek(int,long long,int) __asm__("llseek");
typedef char stock_dirent_name[(offsetof(struct dirent,d_name)==19)?1:-1];
typedef char stock_dirent_record_length[(offsetof(struct dirent,d_reclen)==16)?1:-1];
typedef char stock_dirent_inode[(sizeof(((struct dirent*)0)->d_ino)==8)?1:-1];
static long result(long value) {return value<0?-errno:value;}
long hb_file_open_read(const char *path){return result(open(path,O_RDONLY));}
long hb_file_read(int fd,void *buffer,unsigned bytes){return result(read(fd,buffer,bytes));}
long hb_file_write(int fd,const void *buffer,unsigned bytes){return result(write(fd,buffer,bytes));}
long hb_file_close(int fd){return result(close(fd));}
int hb_path_is_not_link(const char *path){
 char buffer[2];return readlink(path,buffer,sizeof buffer)<0&&errno==EINVAL;
}


long hb_file_seek_end(int fd){
 long long end=hb_stock_llseek(fd,0,SEEK_END);
 if(end<0)return -errno;
 if(end>LONG_MAX)return -EOVERFLOW;
 return (long)end;
}
int hb_directory_open(struct hb_directory *d,const char *path,volatile int *stop){
 d->stream=0;d->stop=stop;
 if(!stop||*stop)return -1;
 d->stream=opendir(path);return d->stream?0:-1;
}
int hb_directory_next(struct hb_directory *d,char name[33]){
 for(;;){
  if(!d->stream||*d->stop)return -1;
  errno=0;struct dirent *entry=readdir(d->stream);
  if(!entry)return errno?-1:0;
  unsigned header=offsetof(struct dirent,d_name);
  if(entry->d_reclen<=header)return -1;
  unsigned available=entry->d_reclen-header,n=0;
  while(n<available&&n<=32&&entry->d_name[n]){if(n<32)name[n]=entry->d_name[n];n++;}
  if(n==available)return -1;
  if(n>32)continue;
  name[n]=0;return 1;
 }
}
void hb_directory_close(struct hb_directory *d){
 if(d->stream){(void)closedir(d->stream);d->stream=0;}
}

