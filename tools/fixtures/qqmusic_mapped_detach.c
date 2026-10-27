/* Exercise the production child-detach function in an actual fork. */
#include "../../runtime/apps/qqmusic/qqmusic_import_binding.c"
#include <assert.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
extern void *sony_mmap(void *,size_t,int,int,int,long) __asm__("mmap");
extern int __real_munmap(void *,size_t);
static unsigned unmapped;
int __wrap_munmap(void *data,size_t n){unmapped++;return __real_munmap(data,n);}
/* Device close already tested by native-entry fixture. No physical IO here. */
int qq_devices_close(struct qq_devices *d){assert(d->opened);d->opened=0;return 0;}
int main(int argc,char **argv){
 struct qq_import_binding b;struct qq_asset_mapping m={0};struct qq_devices devices;struct qq_runtime *runtime;pid_t pid;int fd,status;
 static const unsigned char digest[32]=QQ_FONT_SHA256;
 assert(argc==2);fd=open(argv[1],O_RDONLY);assert(fd>=0);m.data=sony_mmap(0,QQ_FONT_BYTES,PROT_READ,MAP_PRIVATE,fd,0);assert(m.data!=MAP_FAILED&&!close(fd));m.bytes=QQ_FONT_BYTES;memcpy(m.digest,digest,32);
 assert(!qq_ui_font_mapped(&m));runtime=calloc(1,sizeof(*runtime));assert(runtime);qq_app_init(&runtime->app);runtime->app.login.credential.musicid=123456;strcpy(runtime->app.login.credential.musickey,"synthetic-only");
 memset(&b,0,sizeof(b));memset(&devices,0,sizeof(devices));devices.opened=1;b.attached=1;b.font_mapped=1;b.runtime=runtime;b.devices=&devices;b.font=m.data;b.font_bytes=m.bytes;b.pixels=calloc(QQ_UI_PIXELS,sizeof(*b.pixels));assert(b.pixels);b.pixels[0]=0x1234;b.job.policy_context=&b;
 pid=fork();assert(pid>=0);
 if(!pid){assert(!child_detach(&b.job)&&unmapped==1&&!b.font&&!b.pixels&&!devices.opened&&!runtime->app.login.credential.musicid&&!runtime->app.login.credential.musickey[0]);_exit(0);}
 assert(waitpid(pid,&status,0)==pid&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
 assert(!unmapped&&b.font==m.data&&b.pixels[0]==0x1234&&devices.opened&&runtime->app.login.credential.musicid==123456&&!memcmp(m.data,"OTTO",4));
 assert(!qq_ui_font_mapped(&m));(void)qq_ui_font(0,0);assert(!qq_asset_unmap(&m)&&unmapped==1);free(b.pixels);qq_app_logout(&runtime->app);free(runtime);return 0;
}
