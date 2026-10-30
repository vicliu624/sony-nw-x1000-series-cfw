#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_file_check.h"
#include "../../native/sha256.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include "../../store/target_abi.h"
extern ssize_t xnow_file_readlink(const char *,char *,size_t) __asm__("readlink");
static int same_path(int fd,const char *path) {
    char link[64],actual[513];ssize_t n;
    int length=snprintf(link,sizeof(link),"/proc/self/fd/%d",fd);
    if(length<0||(unsigned)length>=sizeof(link))return -1;
    n=xnow_file_readlink(link,actual,sizeof(actual));
    if(n<0||(unsigned)n>=sizeof(actual))return -1;
    actual[n]=0;return strcmp(actual,path)?-1:0;
}
int xnow_file_check(const char *path,uint64_t expected_device,unsigned bytes,const unsigned char expected[32]) {
    struct stat before,after;struct hb_sha256 hash;unsigned char buffer[1024],digest[32];
    char component[256],relative[320],prefix[513];size_t length,start,end;
    int directory=-1,fd=-1,result=-1;unsigned used=0;
    if(!path||!expected||!bytes||bytes>1048576||path[0]!='/')return -1;
    length=strlen(path);if(length<2||length>512||path[length-1]=='/')return -1;
    directory=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(directory<0)return -1;
    start=1;
    while(start<length) {
        int next,n;end=start;while(end<length&&path[end]!='/')end++;
        if(end==start||end-start>=sizeof(component))goto done;
        memcpy(component,path+start,end-start);component[end-start]=0;
        if(!strcmp(component,".")||!strcmp(component,".."))goto done;
        n=snprintf(relative,sizeof(relative),"/proc/self/fd/%d/%s",directory,component);
        if(n<0||(unsigned)n>=sizeof(relative))goto done;
        next=open(relative,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|(end<length?O_DIRECTORY:0));
        if(next<0)goto done;
        memcpy(prefix,path,end);prefix[end]=0;
        if(same_path(next,prefix)){close(next);goto done;}
        if(end==length){fd=next;break;}
        close(directory);directory=next;start=end+1;
    }
    if(fd<0||fstat(fd,&before)||!S_ISREG(before.st_mode)||before.st_nlink!=1||
       (uint64_t)before.st_dev!=expected_device||before.st_size!=(long long)bytes)goto done;
    hb_sha256_init(&hash);
    while(used<bytes) {
        unsigned amount=bytes-used;ssize_t n;if(amount>sizeof(buffer))amount=sizeof(buffer);
        n=read(fd,buffer,amount);if(n<0&&errno==EINTR)continue;
        if(n<=0||(unsigned)n>amount)goto done;
        hb_sha256_update(&hash,buffer,(unsigned)n);used+=(unsigned)n;
    }
    for(;;){ssize_t n=read(fd,buffer,1);if(n<0&&errno==EINTR)continue;if(n)goto done;break;}
    hb_sha256_final(&hash,digest);
    if(memcmp(digest,expected,32)||fstat(fd,&after)||after.st_dev!=before.st_dev||
       after.st_ino!=before.st_ino||after.st_size!=before.st_size||
       after.st_mode!=before.st_mode||after.st_nlink!=1||same_path(fd,path))goto done;
    result=0;
done:
    if(fd>=0&&close(fd))result=-1;
    if(directory>=0&&close(directory))result=-1;
    return result;
}
