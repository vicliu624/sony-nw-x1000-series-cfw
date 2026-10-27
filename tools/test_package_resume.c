#include "../runtime/store/package_resume.h"
#include "../runtime/store/install_posix.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "resume_fixture.h"
static struct hb_package_assembly assembly;
static struct hb_package_download_plan plan;
static struct hb_bundle workspace;
int main(void){
 const char *mode=getenv("HB_RESUME_MODE");assert(mode);volatile int stop=!strcmp(mode,"cancel");
 const unsigned char *mf=!strcmp(mode,"identity")?MF2:MF,*ix=!strcmp(mode,"identity")?IX2:IX;
 unsigned mf_bytes=!strcmp(mode,"identity")?sizeof MF2:sizeof MF,ix_bytes=!strcmp(mode,"identity")?sizeof IX2:sizeof IX;
 assert(!hb_package_download_plan_init(&plan,"demo","https://example.test/demo/",mf,mf_bytes,ix,ix_bytes));hb_package_assembly_init(&assembly);
 int result=hb_package_assembly_reopen(&assembly,getenv("HB_RESUME_PACKAGES"),&plan,&stop,&workspace);
 if(!strcmp(mode,"absent")){assert(result==HB_ASSEMBLY_ABSENT&&assembly.state==HB_ASSEMBLE_EMPTY);return 0;}
 if(!strcmp(mode,"cancel")){assert(result==HB_ASSEMBLE_CANCELLED&&assembly.state==HB_ASSEMBLE_EMPTY);return 0;}
 if(strcmp(mode,"complete")&&strcmp(mode,"discard")&&strcmp(mode,"install")){assert(result<0&&assembly.state==HB_ASSEMBLE_EMPTY);return 0;}
 assert(!result&&assembly.state==HB_ASSEMBLE_READY&&assembly.added==3&&assembly.plan==&plan);
 if(!strcmp(mode,"discard"))assert(!hb_package_assembly_discard(&assembly)&&assembly.state==HB_ASSEMBLE_EMPTY);
 if(!strcmp(mode,"install"))assert(!hb_store_install_local_expected(getenv("HB_RESUME_APPS"),assembly.folder,"demo",4096,&stop,plan.identity));
 return 0;
}
