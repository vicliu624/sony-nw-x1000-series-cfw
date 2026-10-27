/* PC-only ARM Linux VFS experiment. Never deploy as a player app. */
#define _GNU_SOURCE
#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <fcntl.h>
#include <sys/mount.h>
#include <sys/mman.h>
static int fail(const char *at){printf("SNAPSHOT_VFS_FAIL %s errno=%d\n",at,errno);return 1;}
int main(void){
 setbuf(stdout,0);
 for(unsigned cycle=0;cycle<32;cycle++){
  if(mount("language-fixture","/contents","tmpfs",0,"size=2m"))return fail("mount");
  int fd=open("/contents/wording.stx",O_RDWR|O_CREAT|O_TRUNC,0600);
  if(fd<0)return fail("open");
  unsigned char block[4096];for(unsigned i=0;i<sizeof block;i++)block[i]=(unsigned char)(i+cycle);
  for(unsigned i=0;i<37;i++)if(write(fd,block,sizeof block)!=sizeof block)return fail("write");
  unsigned n=37*sizeof block;
  void *file=mmap(0,n,PROT_READ,MAP_SHARED,fd,0);if(file==MAP_FAILED)return fail("file-map");
  if(close(fd))return fail("close");
  errno=0;if(umount("/contents")!=-1||errno!=EBUSY)return fail("file-map-must-pin-mount");
  void *ram=mmap(0,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
  if(ram==MAP_FAILED)return fail("anon-map");
  memcpy(ram,file,n);
  if(munmap(file,n))return fail("file-unmap");
  if(umount("/contents"))return fail("detached-ram-must-not-pin-mount");
  for(unsigned i=0;i<n;i++)if(((unsigned char*)ram)[i]!=(unsigned char)((i%4096)+cycle))return fail("snapshot-after-real-unmount");
  if(munmap(ram,n))return fail("snapshot-release");
 }
 puts("SNAPSHOT_VFS_PASS cycles=32 file_mapping_ebusy=32 detached_unmount_success=32 data_verified=32");
 puts("SNAPSHOT_VFS_COMPLETE");for(;;)pause();
}
