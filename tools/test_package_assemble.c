#define _XOPEN_SOURCE 700
#include "../runtime/store/package_assemble.h"
#include "../runtime/store/install_posix.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <assert.h>
#include "package_task_fixture.h"
static struct hb_package_download_plan plan;
static struct hb_package_assembly assembly;
static struct hb_bundle workspace;
static void discard(int refusal){
 if(!getenv("HB_ASM_DISCARD"))return;
 assert(assembly.stop);*assembly.stop=1;assert(hb_package_assembly_discard(&assembly)==HB_ASSEMBLE_CANCELLED);*assembly.stop=0;
 int result=hb_package_assembly_discard(&assembly);
 if(refusal)assert(result<0&&assembly.state==HB_ASSEMBLE_REVIEW);
 else assert(!result&&assembly.state==HB_ASSEMBLE_EMPTY);
}
int main(void){
 const char *mode=getenv("HB_ASM_CASE"),*parent=getenv("HB_ASM_PARENT"),*cache=getenv("HB_ASM_CACHE");assert(mode&&parent&&cache);
 assert(!hb_package_download_plan_init(&plan,"demo","https://example.test/apps/demo/0.1.0/",PLAN_MF,sizeof PLAN_MF,PLAN_IX,sizeof PLAN_IX));
 volatile int stop=0;hb_package_assembly_init(&assembly);int result=hb_package_assembly_begin(&assembly,parent,&plan,4096,&stop);
 if(!strcmp(mode,"exists")){assert(result==HB_ASSEMBLE_EXISTS);return 0;}assert(!result);
 assert(hb_package_assembly_finish(&assembly,&workspace)==HB_ASSEMBLE_INCOMPLETE&&assembly.state==HB_ASSEMBLE_OPEN);
 if(!strcmp(mode,"missing")){discard(0);return 0;}
 for(unsigned i=0;i<3;i++){
  struct hb_package_download_file descriptor;assert(!hb_package_download_plan_file(&plan,i,&descriptor)&&!strcmp(descriptor.path,PLAN_PATHS[i]));
  struct hb_download_file file;hb_download_file_init(&file);
  assert(!hb_download_file_begin(&file,cache,descriptor.cache_key,descriptor.bytes,descriptor.digest,4096,&stop));
  assert(!hb_download_stream_push(&file.body,PLAN_BODIES[i],PLAN_SIZES[i])&&!hb_download_file_finish(&file));
  if(!strcmp(mode,"corrupt")&&!i){unsigned char data[128];memcpy(data,PLAN_BODIES[i],PLAN_SIZES[i]);data[0]^=1;int fd=open(file.path,O_WRONLY|O_TRUNC);assert(fd>=0&&write(fd,data,PLAN_SIZES[i])==(ssize_t)PLAN_SIZES[i]&&!close(fd));}
  result=hb_package_assembly_add(&assembly,i,&file);
  if(!strcmp(mode,"corrupt")&&!i){assert(result<0&&assembly.state==HB_ASSEMBLE_REVIEW);assert(!hb_download_file_discard(&file));discard(0);return 0;}
  assert(!result&&file.state==HB_FETCH_READY);
  if(!strcmp(mode,"duplicate")&&!i)assert(hb_package_assembly_add(&assembly,i,&file)==HB_ASSEMBLE_INPUT&&assembly.added==1);
  assert(!hb_download_file_discard(&file));
 }
 if(!strcmp(mode,"extra")){char path[520];assert(snprintf(path,sizeof path,"%s/unknown",assembly.folder)<(int)sizeof path);int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,"KEEP",4)==4&&!close(fd));}
 if(!strcmp(mode,"link")||!strcmp(mode,"oversize")){
  char path[520];assert(snprintf(path,sizeof path,"%s/app",assembly.folder)<(int)sizeof path);
  if(!strcmp(mode,"link")){assert(!unlink(path)&&!symlink("../outside",path));}
  else {int fd=open(path,O_WRONLY|O_APPEND);assert(fd>=0&&write(fd,"X",1)==1&&!close(fd));}
  assert(hb_package_assembly_finish(&assembly,&workspace)<0&&assembly.state==HB_ASSEMBLE_REVIEW);discard(1);return 0;
 }
 result=hb_package_assembly_finish(&assembly,&workspace);
 if(!strcmp(mode,"extra")){assert(result<0&&assembly.state==HB_ASSEMBLE_REVIEW);discard(1);return 0;}
 assert(!result&&assembly.state==HB_ASSEMBLE_READY);
 assert(!hb_store_install_local(getenv("HB_ASM_APPS"),assembly.folder,"demo",4096,&stop));
 discard(0);return 0;
}
