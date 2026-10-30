#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_manager.h"
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include "../../store/target_abi.h"
extern int xnow_ipc_sscanf(const char *,const char *,...) __asm__("sscanf");
int xnow_manager_stock_ipc_guard(void *context,enum xnow_session_action action){
    static const char *paths[]={"/tmp/cnmgr_main_req","/tmp/cnmgr_main_res","/tmp/cnmgr_sub_req","/tmp/cnmgr_sub_res","/tmp/cnmgr_event_res"};
    struct stat root,tmp,node;char line[1024],source[256],mount[256],type[64];unsigned found=0;int bad=0;
    (void)context;(void)action;
    if(lstat("/",&root)||lstat("/tmp",&tmp)||!S_ISDIR(tmp.st_mode)||tmp.st_dev==root.st_dev)return -1;
    FILE *file=fopen("/proc/mounts","r");if(!file)return -1;
    while(fgets(line,sizeof(line),file)){
        if(!strchr(line,'\n')||xnow_ipc_sscanf(line,"%255s %255s %63s",source,mount,type)!=3){bad=1;break;}
        if(!strcmp(mount,"/tmp")){found++;if(strcmp(type,"ramfs"))bad=1;}
        else if(!strncmp(mount,"/tmp/",5))bad=1;
    }
    if(ferror(file))bad=1;
    if(fclose(file))bad=1;
    if(bad||found!=1)return -1;
    for(unsigned i=0;i<5;i++)if(lstat(paths[i],&node)||!S_ISFIFO(node.st_mode)||node.st_dev!=tmp.st_dev)return -1;
    return 0;
}
