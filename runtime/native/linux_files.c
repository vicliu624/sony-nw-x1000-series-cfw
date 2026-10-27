#ifndef HB_USE_POSIX_FILES
#include "linux_files.h"
extern long x1000_oabi_call(long,long,long,long,long,long,long);
enum file_syscall {SYS_READ=3,SYS_WRITE=4,SYS_OPEN=5,SYS_CLOSE=6,
                   SYS_LSEEK=19,SYS_READLINK=85,SYS_GETDENTS=141};
static long call3(long n,long a,long b,long c) {return x1000_oabi_call(n,a,b,c,0,0,0);}
long hb_file_open_read(const char *path) {return call3(SYS_OPEN,(long)path,0,0);}
long hb_file_read(int fd,void *buffer,unsigned bytes) {return call3(SYS_READ,fd,(long)buffer,bytes);}
long hb_file_write(int fd,const void *buffer,unsigned bytes) {return call3(SYS_WRITE,fd,(long)buffer,bytes);}
long hb_file_close(int fd) {return call3(SYS_CLOSE,fd,0,0);}

int hb_path_is_not_link(const char *path) {
    char buffer[2];
    return call3(SYS_READLINK,(long)path,(long)buffer,sizeof buffer)==-22;
}
long hb_file_seek_end(int fd) {return call3(SYS_LSEEK,fd,0,2);}
int hb_directory_open(struct hb_directory *directory,const char *path,volatile int *stop) {
    directory->used=directory->offset=0;directory->stop=stop;
    directory->fd=(int)hb_file_open_read(path);
    return directory->fd<0?-1:0;
}
int hb_directory_next(struct hb_directory *directory,char name[33]) {
    for (;;) {
        if(*directory->stop)return -1;
        if(directory->offset==directory->used) {
            long bytes=call3(SYS_GETDENTS,directory->fd,(long)directory->buffer,sizeof directory->buffer);
            if(bytes<0||bytes>(long)sizeof directory->buffer)return -1;
            if(!bytes)return 0;
            directory->used=(unsigned)bytes;directory->offset=0;
        }
        unsigned offset=directory->offset;
        if(offset+11>directory->used)return -1;
        unsigned size=directory->buffer[offset+8]|((unsigned)directory->buffer[offset+9]<<8);
        if(size<12||offset+size>directory->used)return -1;
        directory->offset+=size;
        unsigned length=0;
        while(length<32&&offset+10+length<offset+size&&directory->buffer[offset+10+length]) {
            name[length]=(char)directory->buffer[offset+10+length];length++;
        }
        name[length]=0;
        if(offset+10+length<offset+size&&!directory->buffer[offset+10+length])return 1;
        /* Oversized names are ignored, matching the previous catalog scan. */
    }
}
void hb_directory_close(struct hb_directory *directory) {
    if(directory->fd>=0)hb_file_close(directory->fd);
    directory->fd=-1;
}



#endif
