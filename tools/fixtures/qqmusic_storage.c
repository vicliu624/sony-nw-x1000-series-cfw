#include "../../runtime/apps/qqmusic/qqmusic_storage.h"
#include <assert.h>
#include <string.h>
static const char *mounts="/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n";
static struct qq_storage_policy policy={"/dev/mtdblock/2","vfat"};
static struct qq_storage_directory dirs[]={{"/",1,0040755},{"/contents",2,0040755},{"/contents/HOMEBREW",2,0040755},{"/contents/HOMEBREW/qqmusic",2,0040755}};
static struct qq_storage_plan plan={1000,2000,3000,4000,500,100,8192,4096,100,{1,1,1,1,1,1},0};
static int check(const char *s,uint64_t *required) {return qq_storage_preflight(&policy,s,strlen(s),dirs,4,&plan,required);}
int main(void) {
 uint64_t needed;const char *saved;size_t i;
 assert(check(mounts,&needed)==0&&needed==32768);
 /* Old Linux exposes the persistent rootfs below the actual root mount. */
 assert(check("rootfs / rootfs rw 0 0\n/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime,nodiratime,fmask=0000,dmask=0000 0 0\n",&needed)==0&&needed==32768);
 assert(check("rootfs / rootfs rw 0 0\nrootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\n",&needed)==QQ_STORAGE_MOUNT);
 assert(check("/dev/root / ext2 rw 0 0\n/dev/other / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\n",&needed)==QQ_STORAGE_MOUNT);
 assert(check("/dev/root / ext2 rw 0 0\nrootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\n",&needed)==QQ_STORAGE_MOUNT);
 assert(check("rootfs / rootfs rw 0 0\n/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\n",&needed)==QQ_STORAGE_MOUNT);
 assert(qq_storage_mount_reason(&policy,mounts,strlen(mounts))==QQ_MOUNT_OK);
 assert(check("/dev/root / ext2 rw 0 0\n",&needed)==QQ_STORAGE_MOUNT&&needed==0);
 assert(check("/dev/root / ext2 rw 0 0\n/dev/wrong /contents vfat rw 0 0\n",&needed)==QQ_STORAGE_MOUNT);
 assert(check("/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat ro 0 0\n",&needed)==QQ_STORAGE_MOUNT);
 assert(check("/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents ext2 rw 0 0\n",&needed)==QQ_STORAGE_MOUNT);
 assert(check("/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\n/dev/other /contents/HOMEBREW vfat rw 0 0\n",&needed)==QQ_STORAGE_MOUNT);
 dirs[1].device=1;assert(check(mounts,&needed)==QQ_STORAGE_BOUNDARY);dirs[1].device=2;
 dirs[3].device=1;assert(check(mounts,&needed)==QQ_STORAGE_BOUNDARY);dirs[3].device=2;
 dirs[2].mode=0120777;assert(check(mounts,&needed)==QQ_STORAGE_BOUNDARY);dirs[2].mode=0040755;
 saved=dirs[3].path;
 {const char *bad[]={"/etc/qqmusic","/contents/HOMEBREW/../qqmusic","/contents/HOMEBREW//qqmusic","/contents/HOMEBREW/qqmusic/","/contents/HOMEBREW/a/b"};
 for(i=0;i<5;i++) {dirs[3].path=bad[i];assert(check(mounts,&needed)==QQ_STORAGE_BOUNDARY);}}
 dirs[3].path=saved;
 plan.available_units=7;assert(check(mounts,&needed)==QQ_STORAGE_SPACE&&needed==0);
 plan.available_units=8;assert(check(mounts,&needed)==0&&needed==32768);
 plan.available_units=UINT64_MAX;assert(check(mounts,&needed)==QQ_STORAGE_OVERFLOW);plan.available_units=100;
 plan.source=UINT64_MAX;assert(check(mounts,&needed)==QQ_STORAGE_OVERFLOW);plan.source=1000;
 plan.files[5]=2;assert(check(mounts,&needed)==0&&needed==36864);plan.files[5]=1;
 plan.directory_units=2;assert(check(mounts,&needed)==0&&needed==40960);plan.directory_units=0;
 plan.files[0]=0;assert(check(mounts,&needed)==QQ_STORAGE_INPUT);plan.files[0]=1;
 for(i=0;i<strlen(mounts);i++) assert(qq_storage_preflight(&policy,mounts,i,dirs,4,&plan,&needed)!=0||i==strlen("/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n"));
 return 0;
}
