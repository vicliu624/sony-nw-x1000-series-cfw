#define _XOPEN_SOURCE 700
#include "../../runtime/apps/qqmusic/qqmusic_stage.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../../runtime/store/target_abi.h"
static struct qq_stage_file file,collision;
static struct qq_response response;
static unsigned char data[20000],readback[20000];
static int watched=-1,write_fault,sync_fault;
extern ssize_t __real_write(int,const void *,size_t);
extern int __real_fsync(int);
ssize_t __wrap_write(int fd,const void *p,size_t n) {
 if(fd==watched&&write_fault) {int fault=write_fault;write_fault=0;if(fault==1) return __real_write(fd,p,n/2);errno=fault==2?EINTR:EIO;return -1;}
 return __real_write(fd,p,n);
}
int __wrap_fsync(int fd) {if(fd==watched&&sync_fault) {sync_fault=0;errno=EIO;return -1;}return __real_fsync(fd);}
static const char *identity="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
static const char *nonce="0123456789abcdef";
static void begin(int parent,uint64_t device,volatile int *stop) {
 qq_stage_init(&file);assert(qq_stage_begin(&file,parent,device,identity,nonce,sizeof(data),stop)==0);
 watched=file.fd;assert(qq_response_init_stream(&response,sizeof(data),qq_stage_sink(&file))==0);
 {const char *head="HTTP/1.1 200 OK\r\nContent-Length: 20000\r\n\r\n";
 assert(qq_response_push(&response,(const unsigned char *)head,strlen(head))==0);}
}
int main(int argc,char **argv) {
 int parent,fd,system;struct stat info;uint64_t system_device;volatile int stop=0;unsigned i;
 assert(argc==2);assert(chdir(argv[1])==0);
 parent=open(".",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(parent>=0&&!fstat(parent,&info));
 system=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(system>=0&&qq_stage_system_device(&system_device)==0);
 qq_stage_init(&file);assert(qq_stage_begin(&file,system,system_device,identity,nonce,20000,&stop)<0);assert(close(system)==0);
 /* This requires a real PC test workspace on a distinct filesystem from /.
  * No synthetic st_dev override: on this Windows/WSL setup it is project /mnt/c. */
 assert((uint64_t)info.st_dev!=system_device);
 for(i=0;i<sizeof(data);i++) data[i]=(unsigned char)(i%251);
 begin(parent,(uint64_t)info.st_dev,&stop);write_fault=1;
 assert(qq_response_push(&response,data,sizeof(data))==1&&qq_response_finish(&response)==0&&file.state==QQ_STAGE_READY);
 fd=open(file.path,O_RDONLY|O_NOFOLLOW);assert(fd>=0&&read(fd,readback,sizeof(readback))==(ssize_t)sizeof(readback)&&close(fd)==0&&!memcmp(data,readback,sizeof(data)));
 qq_stage_init(&collision);assert(qq_stage_begin(&collision,parent,(uint64_t)info.st_dev,identity,nonce,sizeof(data),&stop)<0);
 assert(file.state==QQ_STAGE_READY&&qq_stage_discard(&file)==0);
 begin(parent,(uint64_t)info.st_dev,&stop);write_fault=2;assert(qq_response_push(&response,data,sizeof(data))==1&&qq_response_finish(&response)==0);assert(qq_stage_discard(&file)==0);
 begin(parent,(uint64_t)info.st_dev,&stop);write_fault=3;assert(qq_response_push(&response,data,sizeof(data))<0&&file.state==QQ_STAGE_ABORTED);
 begin(parent,(uint64_t)info.st_dev,&stop);assert(qq_response_push(&response,data,sizeof(data))==1);sync_fault=1;
 assert(qq_response_finish(&response)<0&&file.state==QQ_STAGE_ABORTED);
 begin(parent,(uint64_t)info.st_dev,&stop);assert(qq_response_push(&response,data,8000)==0);stop=1;
 assert(qq_response_push(&response,data+8000,12000)<0&&file.state==QQ_STAGE_ABORTED);stop=0;
 begin(parent,(uint64_t)info.st_dev,&stop);
 {char name[128];const char *base=strrchr(file.path,'/')+1;memcpy(name,base,strlen(base)+1);
 fd=open("keep.txt",O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,"keep",4)==4&&close(fd)==0);
 assert(unlink(file.path)==0&&symlink("keep.txt",file.path)==0);
 assert(qq_stage_discard(&file)<0&&file.state==QQ_STAGE_REVIEW);
 fd=open("keep.txt",O_RDONLY);assert(fd>=0&&read(fd,readback,4)==4&&!memcmp(readback,"keep",4)&&close(fd)==0);
 assert(unlink(name)==0&&unlink("keep.txt")==0);}
 /* Replacing a visible directory alias cannot redirect descriptor-anchored
  * writes to /. All created entries remain inside this PC test workspace. */
 assert(mkdir("workspace",0700)==0);
 assert(symlink("workspace","visible")==0);
 fd=open("visible",O_RDONLY|O_DIRECTORY);assert(fd>=0);
 begin(fd,(uint64_t)info.st_dev,&stop);
 assert(unlink("visible")==0&&symlink("/","visible")==0);
 assert(qq_response_push(&response,data,sizeof(data))==1&&qq_response_finish(&response)==0&&file.state==QQ_STAGE_READY);
 assert(qq_stage_discard(&file)==0&&close(fd)==0&&unlink("visible")==0&&rmdir("workspace")==0);
 assert(close(parent)==0);return 0;
}
