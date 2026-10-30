/* Read-only native helper: stdout only, no persistent files or radio SETs. */
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/wireless.h>
extern int original_ioctl(int, unsigned long, ...) __asm__("ioctl");
int main(int argc,char **argv,char **env) {
    int fd,result=0; struct iwreq request; struct iw_priv_args entries[256];
    unsigned i;
    (void)env;
    if(argc==2 && !strcmp(argv[1],"--version")) { puts("xnow-inventory 0.1.0");return 0; }
    if(argc!=2 || strcmp(argv[1],"--inventory")) {
        puts("Usage: xnow-inventory --inventory | --version\nRead-only WEXT inventory; stdout only. No hostcmd, SET or persistent writes.");return argc==2&&!strcmp(argv[1],"--help")?0:64;
    }
    if(sizeof(struct iwreq)!=32 || sizeof(struct iw_priv_args)!=24) { puts("ABI mismatch");return 70; }
    fd=socket(AF_INET,SOCK_DGRAM,0);if(fd<0){perror("socket");return 71;}
    memset(&request,0,sizeof(request));strcpy(request.ifr_name,"eth0");
    if(original_ioctl(fd,SIOCGIWMODE,&request)<0){perror("SIOCGIWMODE");result=1;}
    else printf("mode=%u\n",request.u.mode);
    memset(&request,0,sizeof(request));strcpy(request.ifr_name,"eth0");
    memset(entries,0,sizeof(entries));request.u.data.pointer=entries;request.u.data.length=256;
    if(original_ioctl(fd,SIOCGIWPRIV,&request)<0){perror("SIOCGIWPRIV");result=1;}
    else if(request.u.data.length>256){puts("invalid private table length");result=1;}
    else {
        printf("private_records=%u\n",request.u.data.length);
        for(i=0;i<request.u.data.length;i++)printf("command=%08x set=%04x get=%04x name=%.*s\n",entries[i].cmd,entries[i].set_args,entries[i].get_args,16,entries[i].name);
    }
    close(fd);return result;
}
