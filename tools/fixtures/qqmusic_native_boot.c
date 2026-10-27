#define QQ_ENTRY_BOOT_NO_MAIN
#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "qqmusic_entry_boot.c"
#define main native_application_main
#include "../../runtime/apps/qqmusic/qqmusic_main.c"
#undef main
void x1000_rt_sigreturn(void){assert(0);}
#ifdef QQ_NATIVE_FULL
static unsigned import_bindings;
extern int __real_qq_runtime_bind_import(struct qq_runtime *,const struct qq_runtime_import_ops *);
int __wrap_qq_runtime_bind_import(struct qq_runtime *runtime,const struct qq_runtime_import_ops *ops){assert(ops&&ops->begin&&ops->poll&&ops->cancel);import_bindings++;return __real_qq_runtime_bind_import(runtime,ops);}
#endif
int main(int argc,char **argv){
 const char *suffix[]={"contents","contents/HOMEBREW","contents/HOMEBREW/apps","contents/HOMEBREW/apps/qqmusic","contents/HOMEBREW/apps/qqmusic/resources"
#ifdef QQ_NATIVE_FULL
 ,"contents/HOMEBREW/data","contents/HOMEBREW/data/qqmusic","contents/MUSIC"
#endif
 };
 char dirs[8][4096],input[4096],font[4096],capture[4096];unsigned i,count=sizeof(suffix)/sizeof(suffix[0]);int result;
 char *native_argv[]={"/contents/HOMEBREW/apps/qqmusic/app",0};
 /* Keep helper callbacks referenced; the real program supplies actual ones. */
 (void)prepare;(void)start;(void)poll_response;(void)cancel;
 assert(argc==3);base=argv[1];boot_fault=atoi(argv[2]);
 if(!boot_fault){assert(snprintf(capture,sizeof(capture),"%s/frame.rgb565",base)>0);boot_capture=capture;}
 for(i=0;i<count;i++){assert(snprintf(dirs[i],sizeof(dirs[i]),"%s/%s",base,suffix[i])>0);assert(mkdir(dirs[i],0700)==0);}
 assert(snprintf(input,sizeof(input),"%s/font.otf",base)>0&&snprintf(font,sizeof(font),"%s/" QQ_FONT_NAME,dirs[4])>0&&rename(input,font)==0);
#ifdef QQ_NATIVE_FULL
 {
  struct qq_workspace first,second;struct qq_storage_policy policy={"/dev/mock-user","vfat"};volatile int stop=0;char lock[4096],held[4096];int fd;
  assert(snprintf(lock,sizeof(lock),"%s/.import.lock",dirs[6])>0&&snprintf(held,sizeof(held),"%s/.held.lock",dirs[6])>0);
  qq_workspace_init(&first);qq_workspace_init(&second);active=1;readonly_mount=1;
  assert(qq_workspace_open(&first,&policy,&stop));readonly_mount=0;
  assert(!qq_workspace_open(&first,&policy,&stop)&&!qq_workspace_check(&first));
  assert(qq_workspace_open(&second,&policy,&stop)); /* Different open must not share ownership. */
  stop=1;assert(qq_workspace_check(&first));stop=0;
  assert(!rename(lock,held));fd=__real_open(lock,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&!close(fd));
  assert(qq_workspace_check(&first));assert(!qq_workspace_close(&first)&&!unlink(lock)&&!unlink(held));
  assert(!symlink("/tmp/qqmusic-forbidden-lock",lock));assert(qq_workspace_open(&first,&policy,&stop));assert(!unlink(lock));
  active=0;
 }
#endif
 active=1;result=native_application_main(1,native_argv,0);active=0;
 assert(result==(boot_fault?2:0)&&!framebuffer&&!forbid_writes);
 if(boot_fault==3)assert(!submissions&&!closed);else assert(submissions&&closed==2);
#ifdef QQ_NATIVE_FULL
 assert(import_bindings==(boot_fault==3?0:1));
 {char lock[4096];assert(snprintf(lock,sizeof(lock),"%s/.import.lock",dirs[6])>0);if(unlink(lock))assert(errno==ENOENT);}
#endif
 assert(unlink(font)==0);for(i=count;i>0;i--)assert(rmdir(dirs[i-1])==0);
 return 0;
}
