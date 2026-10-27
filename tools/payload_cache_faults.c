/* Test-only unlink failure/exit/cancel injection; never linked into candidates. */
#include "download_file_faults.c"
extern int __real_unlink(const char *);
static unsigned unlink_target,unlink_seen;
static int unlink_mode;
static volatile int *cancel_token;
void hb_cache_unlink_fault(int mode,unsigned target,volatile int *stop){unlink_mode=mode;unlink_target=target;unlink_seen=0;cancel_token=stop;}
int __wrap_unlink(const char *path){
 if(unlink_mode&&++unlink_seen==unlink_target){
  if(unlink_mode==1){errno=EIO;return -1;}
  int result=__real_unlink(path);if(result)return result;
  if(unlink_mode==3)_exit(77);
  if(unlink_mode==4){*cancel_token=1;return 0;}
  errno=EIO;return -1;
 }
 return __real_unlink(path);
}
