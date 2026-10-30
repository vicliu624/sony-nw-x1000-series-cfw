#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "../runtime/platform/espnow/xnow_file_check.h"
#include "../runtime/native/sha256.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "../runtime/store/target_abi.h"
int main(void) {
    char folder[]="/tmp/xnow-files-XXXXXX",file[256],linkpath[256],alias[256],fifo[256],path[512];
    unsigned char data[2500],digest[32];struct hb_sha256 hash;struct stat st;int fd;
    assert(mkdtemp(folder));snprintf(file,sizeof(file),"%s/radio.bin",folder);
    snprintf(linkpath,sizeof(linkpath),"%s/link",folder);snprintf(alias,sizeof(alias),"%s/alias",folder);
    snprintf(fifo,sizeof(fifo),"%s/fifo",folder);
    for(unsigned i=0;i<sizeof(data);i++)data[i]=(unsigned char)i;
    hb_sha256_init(&hash);hb_sha256_update(&hash,data,sizeof(data));hb_sha256_final(&hash,digest);
    fd=open(file,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0);
    assert(write(fd,data,sizeof(data))==sizeof(data));assert(!close(fd));assert(!stat(file,&st));
    assert(!xnow_file_check(file,st.st_dev,sizeof(data),digest));
    assert(xnow_file_check(file,st.st_dev+1,sizeof(data),digest));
    assert(xnow_file_check(file,st.st_dev,sizeof(data)-1,digest));
    assert(xnow_file_check(file,st.st_dev,sizeof(data)+1,digest));
    digest[0]^=1;assert(xnow_file_check(file,st.st_dev,sizeof(data),digest));digest[0]^=1;
    assert(!symlink(file,linkpath));assert(xnow_file_check(linkpath,st.st_dev,sizeof(data),digest));
    assert(!unlink(linkpath));assert(!symlink(folder,linkpath));
    snprintf(path,sizeof(path),"%s/radio.bin",linkpath);assert(xnow_file_check(path,st.st_dev,sizeof(data),digest));
    assert(!unlink(linkpath));assert(!link(file,alias));
    assert(xnow_file_check(file,st.st_dev,sizeof(data),digest));assert(!unlink(alias));
    assert(!mkfifo(fifo,0600));assert(xnow_file_check(fifo,st.st_dev,sizeof(data),digest));
    snprintf(path,sizeof(path),"%s/./radio.bin",folder);assert(xnow_file_check(path,st.st_dev,sizeof(data),digest));
    snprintf(path,sizeof(path),"%s//radio.bin",folder);assert(xnow_file_check(path,st.st_dev,sizeof(data),digest));
    fd=open(file,O_WRONLY);assert(fd>=0);data[100]^=1;
    assert(write(fd,data,sizeof(data))==sizeof(data));assert(!close(fd));
    assert(xnow_file_check(file,st.st_dev,sizeof(data),digest));
    assert(!unlink(fifo)&&!unlink(file)&&!rmdir(folder));
    puts("XNOW file preflight: digest, size, device, symlink components, hardlinks, FIFO and path rejection passed");
    return 0;
}
