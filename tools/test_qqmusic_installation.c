#define _GNU_SOURCE
#include "../runtime/apps/qqmusic/qqmusic_installation.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
static unsigned calls;
int hb_tls_seed(unsigned char out[48],volatile int *stop){if(*stop)return -1;calls++;for(unsigned i=0;i<48;i++)out[i]=(unsigned char)(i+calls);return 0;}
int main(int argc,char **argv){
 if(argc!=2)return 64;int directory=open(argv[1],O_RDONLY|O_DIRECTORY);struct stat st;if(directory<0||fstat(directory,&st))return 1;
 char comm[256],payload[256],id[33],second[33];volatile int stop=0;
 if(qq_installation_material(directory,st.st_dev,"{\"udid\":\"INSTALLATION_ID\"}","{\"androidId\":\"INSTALLATION_ID\"}",comm,sizeof comm,payload,sizeof payload,id,&stop)||strlen(id)!=32||!strstr(comm,id)||!strstr(payload,id)||calls!=1)return 2;
 if(qq_installation_material(directory,st.st_dev,"INSTALLATION_ID","INSTALLATION_ID",comm,sizeof comm,payload,sizeof payload,second,&stop)||strcmp(id,second)||calls!=1)return 3;
 if(!qq_installation_material(directory,(uint64_t)st.st_dev+1,"INSTALLATION_ID","INSTALLATION_ID",comm,sizeof comm,payload,sizeof payload,second,&stop)||second[0])return 4;
 stop=1;if(!qq_installation_material(directory,st.st_dev,"INSTALLATION_ID","INSTALLATION_ID",comm,sizeof comm,payload,sizeof payload,second,&stop))return 5;
 close(directory);puts("Stable per-installation identity, templates, device guard and cancellation passed");return 0;
}
