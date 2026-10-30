/* Read-only original connection-config query. No disconnect/connect/SET API.
 * Potentially sensitive configuration is RAM-only, never printed or persisted.
 */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <sys/stat.h>
#include "../../store/target_abi.h"
extern int probe_sscanf(const char *,const char *,...) __asm__("sscanf");
extern int cnmgr_init(void *,const void *);
extern int cnmgr_get_state(void);
extern int cnmgr_get_target_connect_info(void *);
extern int cnmgr_fin(void);
static int ipc_guard(void){
    static const char *paths[]={"/tmp/cnmgr_main_req","/tmp/cnmgr_main_res","/tmp/cnmgr_sub_req","/tmp/cnmgr_sub_res","/tmp/cnmgr_event_res"};
    struct stat root,tmp,node;char line[1024],source[256],mount[256],type[64];unsigned found=0;int bad=0;
    if(lstat("/",&root)||lstat("/tmp",&tmp)||!S_ISDIR(tmp.st_mode)||tmp.st_dev==root.st_dev)return -1;
    FILE *file=fopen("/proc/mounts","r");if(!file)return -1;
    while(fgets(line,sizeof(line),file)){
        if(!strchr(line,'\n')||probe_sscanf(line,"%255s %255s %63s",source,mount,type)!=3){bad=1;break;}
        if(!strcmp(mount,"/tmp")){found++;if(strcmp(type,"ramfs"))bad=1;}
        else if(!strncmp(mount,"/tmp/",5))bad=1;
    }
    if(ferror(file))bad=1;
    if(fclose(file))bad=1;
    if(bad||found!=1)return -1;
    for(unsigned i=0;i<5;i++)if(lstat(paths[i],&node)||!S_ISFIFO(node.st_mode)||node.st_dev!=tmp.st_dev)return -1;
    return 0;
}
int main(int argc,char **argv){
    if(argc!=2||strcmp(argv[1],"--query")){
        puts("Current Connection Probe0.1.0-dev.1: --query\nOriginal client init/state/config/fin only; no disconnect, connect or radio SET.\nConfiguration is cleared from RAM and never logged.");
        return argc==2&&!strcmp(argv[1],"--help")?0:64;
    }
    if(ipc_guard()){puts("original_ram_ipc_guard=failed; no client initialized");return 69;}
    struct {uint32_t before;union {uint32_t alignment[251];unsigned char bytes[1004];} config;uint32_t after;} saved;
    memset(&saved,0,sizeof(saved));saved.before=0xa5a5a5a5;saved.after=0x5a5a5a5a;
    int rc=cnmgr_init(0,0);printf("client_init_result=%d\n",rc);if(rc)return 69;
    int state=cnmgr_get_state(),query=-1;printf("public_state_before=%d\n",state);
    if(state==4)query=cnmgr_get_target_connect_info(saved.config.bytes);
    int intact=saved.before==0xa5a5a5a5&&saved.after==0x5a5a5a5a;
    printf("current_config_result=%d captured_bytes=%u bounds_intact=%d; contents not logged\n",query,query?0:1004,intact);
    volatile unsigned char *wipe=saved.config.bytes;for(unsigned i=0;i<1004;i++)wipe[i]=0;
    int after=cnmgr_get_state();printf("public_state_after=%d\n",after);
    rc=cnmgr_fin();printf("client_fin_result=%d\n",rc);
    return query||!intact||state!=4||after!=4||rc?69:0;
}
