/* Pinned Japanese1.11 private ports. No hardware ioctl, NVP or flash access.
 * Resource validation is read-only on the system resource file, not user data.
 * This file is linked only by an explicit qualified native-page profile. */
#define _DEFAULT_SOURCE
#include "remote_page_guard.h"
#include "../../store/stock_fs_bridge.h"
#include "../../native/sha256.h"
#include "remote_native_page_profile.h"
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <sys/stat.h>
#if !defined(__arm__)
#error Pinned native page ports require ARM32
#endif
#if XW_REMOTE_RESOURCE_BYTES > 512
#error Resource preflight exceeds bounded page size
#endif
int wr_view_code_valid(void){return xw_player_remote_view_image_valid();}
uintptr_t wr_view_root(void){return ((uintptr_t (*)(void))(uintptr_t)0x2a984u)();}
uintptr_t wr_view_pool(void){return ((uintptr_t (*)(void))(uintptr_t)0x1094f0u)();}
uintptr_t wr_view_active(uintptr_t root,uint32_t control){return ((uintptr_t (*)(uintptr_t,uint32_t))(uintptr_t)0x2a824u)(root,control);}
uintptr_t wr_view_menu_context(void){return ((uintptr_t (*)(void))(uintptr_t)0x736c0u)();}
uint32_t wr_view_menu_state(uintptr_t context){return ((uint32_t (*)(uintptr_t))(uintptr_t)0x17ca18u)(context);}
uint32_t *wr_view_params_get(uintptr_t view,uint32_t *out){return ((uint32_t *(*)(uintptr_t,uint32_t *))(uintptr_t)0x10a118u)(view,out);}
void wr_view_params_set(uintptr_t view,const uint32_t *value){((void (*)(uintptr_t,const uint32_t *))(uintptr_t)0x10a0d4u)(view,value);}
#define SID_WORD (*(volatile uint32_t *)(uintptr_t)(0x4e692cu+29u*132u+26u*4u))
uint32_t wr_view_sid_get(void){return SID_WORD;}
void wr_view_sid_set(uint32_t value){SID_WORD=value;}
void wr_view_counts_get(uint32_t value[3]){
 const volatile uint32_t *p=(const volatile uint32_t *)(uintptr_t)(0x4e692cu+29u*132u);
 value[0]=p[21];value[1]=p[22];value[2]=p[32];
}
void wr_view_counts_set(const uint32_t value[2]){
 volatile uint32_t *p=(volatile uint32_t *)(uintptr_t)(0x4e692cu+29u*132u);
 p[21]=value[0];p[32]=value[1]; /* Keep allocated capacity field22 unchanged. */
}
int wr_view_resource_ready(void){
 static const unsigned char expected[32]=XW_REMOTE_RESOURCE_DIGEST;
 int saved=errno,result=0,fd=-1;
 struct hb_target_stat root,path,opened;
 unsigned char data[XW_REMOTE_RESOURCE_BYTES],extra,digest[32];size_t used=0;
 if(hb_target_lstat("/",&root)||!S_ISDIR(root.st_mode)||
    hb_target_lstat(XW_REMOTE_RESOURCE_PATH,&path)||!S_ISREG(path.st_mode)||
    path.st_nlink!=1||path.st_dev!=root.st_dev||path.st_size!=XW_REMOTE_RESOURCE_BYTES)goto done;
 fd=open(XW_REMOTE_RESOURCE_PATH,O_RDONLY|O_NOFOLLOW);if(fd<0)goto done;
 if(hb_target_fstat(fd,&opened)||!S_ISREG(opened.st_mode)||opened.st_nlink!=1||
    opened.st_dev!=root.st_dev||opened.st_ino!=path.st_ino||opened.st_size!=XW_REMOTE_RESOURCE_BYTES)goto done;
 while(used<sizeof data){
  ssize_t n=read(fd,data+used,sizeof data-used);
  if(n<0&&errno==EINTR)continue;
  if(n<=0)goto done;used+=(size_t)n;
 }
 for(;;){ssize_t n=read(fd,&extra,1);if(n<0&&errno==EINTR)continue;if(n!=0)goto done;break;}
 struct hb_sha256 hash;hb_sha256_init(&hash);hb_sha256_update(&hash,data,sizeof data);hb_sha256_final(&hash,digest);
 unsigned diff=0;for(unsigned i=0;i<32;i++)diff|=digest[i]^expected[i];result=diff==0;
done:
 if(fd>=0&&close(fd))result=0;
 errno=saved;return result;
}
