/* Real Sony-loader PID interposition test. No SpiderApp execution. */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
extern void *dlsym(void *,const char *);
struct image_info {const char *name;void *base;const char *symbol;void *address;};
extern int dladdr(const void *,struct image_info *);
int main(int argc,char **argv)
{
    pid_t first=getpid();assert(first>0);
    errno=1234;assert(getpid()==first && errno==1234);
    if (argc>1) {
        struct image_info owner;
        void *pid=dlsym(0,"getpid");
        assert(pid && dladdr(pid,&owner) && strstr(owner.name,"libx1000-player-analysis.so"));
        int (*resolved)(void)=(int (*)(void))dlsym(0,"xw_player_host_pid_resolved");
        int (*active)(void)=(int (*)(void))dlsym(0,"xw_player_host_anchor_ready");
        assert(resolved && active && resolved()==1 && active()==0);
        assert(!strcmp(argv[1],"--preloaded"));
    }
    puts("Original PID behavior preserved; ordinary calls do not activate player host");
    return 0;
}
