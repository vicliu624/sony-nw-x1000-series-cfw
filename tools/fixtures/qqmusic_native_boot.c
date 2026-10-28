#define QQ_ENTRY_BOOT_NO_MAIN
#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "qqmusic_entry_boot.c"
#define main native_application_main
#include "../../runtime/apps/qqmusic/qqmusic_main.c"
#undef main
#include "../../runtime/store/target_abi.h"
void x1000_rt_sigreturn(void){assert(0);}
#ifdef QQ_NATIVE_FULL
static unsigned import_bindings;
extern int __real_qq_runtime_bind_import(struct qq_runtime *,const struct qq_runtime_import_ops *);
int __wrap_qq_runtime_bind_import(struct qq_runtime *runtime,const struct qq_runtime_import_ops *ops){assert(ops&&ops->begin&&ops->poll&&ops->cancel);import_bindings++;return __real_qq_runtime_bind_import(runtime,ops);}
#endif
#ifdef QQ_NATIVE_PREVIEW
#include <sys/mman.h>
extern void *preview_boot_mmap(void *,size_t,int,int,int,long) __asm__("mmap");
static struct {unsigned imports,previews,submissions,closed;long ui_pid;} *preview_observed;
static int (*preview_actual_ui)(void *,const struct qq_preview_client_channels *,volatile int *);
static void *preview_actual_context;
extern int __real_qq_runtime_bind_preview(struct qq_runtime *,const struct qq_runtime_preview_ops *);
int __wrap_qq_runtime_bind_preview(struct qq_runtime *r,const struct qq_runtime_preview_ops *ops){int rc=__real_qq_runtime_bind_preview(r,ops);assert(!rc&&r->ui.preview_enabled);preview_observed->previews++;return rc;}
static int preview_observe_ui(void *context,const struct qq_preview_client_channels *channels,volatile int *stop){
 int rc;(void)context;preview_observed->ui_pid=(long)getpid();rc=preview_actual_ui(preview_actual_context,channels,stop);
 assert(!framebuffer);preview_observed->imports=import_bindings;preview_observed->submissions=submissions;preview_observed->closed=closed;return rc;
}
extern int __real_qq_preview_runtime_run(const struct qq_preview_handoff_policy *,struct qq_workspace *,volatile int *,int (*)(void *,const struct qq_preview_client_channels *,volatile int *),void *);
int __wrap_qq_preview_runtime_run(const struct qq_preview_handoff_policy *policy,struct qq_workspace *workspace,volatile int *stop,int (*ui)(void *,const struct qq_preview_client_channels *,volatile int *),void *context){
 int rc;long root=(long)getpid();preview_actual_ui=ui;preview_actual_context=context;
 preview_observed=preview_boot_mmap(0,sizeof(*preview_observed),PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANONYMOUS,-1,0);assert(preview_observed!=MAP_FAILED);memset(preview_observed,0,sizeof(*preview_observed));
 rc=__real_qq_preview_runtime_run(policy,workspace,stop,preview_observe_ui,0);
 assert((long)getpid()==root&&preview_observed->ui_pid!=root&&preview_observed->previews==1);
 import_bindings=preview_observed->imports;submissions=preview_observed->submissions;closed=preview_observed->closed;assert(!munmap(preview_observed,sizeof(*preview_observed)));return rc;
}
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
#ifdef QQ_PROFILE_GENERATED_IDENTITY
 {
  struct stat s;char comm[1025],qimei[3073],guid[33];volatile int token=0;int directory=__real_open(dirs[6],O_RDONLY|O_DIRECTORY);
  assert(directory>=0&&!fstat(directory,&s));
  assert(!qq_installation_material(directory,(uint64_t)s.st_dev,QQ_PROFILE_COMM,QQ_PROFILE_QIMEI_PAYLOAD,comm,sizeof(comm),qimei,sizeof(qimei),guid,&token));assert(!close(directory));
 }
#endif
 active=1;result=native_application_main(1,native_argv,0);active=0;
 assert(result==(boot_fault?2:0)&&!framebuffer&&!forbid_writes);
 if(boot_fault==3)assert(!submissions&&!closed);else assert(submissions&&closed==2);
#ifdef QQ_NATIVE_FULL
 assert(import_bindings==(boot_fault==3?0:1));
 {char lock[4096];assert(snprintf(lock,sizeof(lock),"%s/.import.lock",dirs[6])>0);if(unlink(lock))assert(errno==ENOENT);}
#endif
#ifdef QQ_PROFILE_GENERATED_IDENTITY
 {char identity[4096];assert(snprintf(identity,sizeof(identity),"%s/installation-id.bin",dirs[6])>0);assert(!unlink(identity));}
#endif
 assert(unlink(font)==0);for(i=count;i>0;i--)assert(rmdir(dirs[i-1])==0);
 return 0;
}
